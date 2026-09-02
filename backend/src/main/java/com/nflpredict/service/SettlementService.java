package com.nflpredict.service;

import com.nflpredict.dto.GameResult;
import com.nflpredict.model.PredictionRecord;
import com.nflpredict.repository.PredictionRecordRepository;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.Map;
import java.util.logging.Logger;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;

/**
 * Closes the loop on predictions.
 *
 * <p>Predictions are worth recording only if something eventually scores them.
 * Weekly this asks the agent service to re-pull results from ESPN, then marks
 * every stored prediction correct or incorrect against the final score.
 *
 * <p>This is what makes the Injury Impact agent calibratable. It has no
 * historical archive to backtest against, so its weight can only ever come from
 * live predictions that have been settled - which requires this job to actually
 * run.
 */
@Service
public class SettlementService {

    private static final Logger logger = Logger.getLogger(SettlementService.class.getName());

    private final WebClient webClient;
    private final PredictionRecordRepository predictionRepository;
    private final boolean enabled;
    private final Duration refreshTimeout;

    public SettlementService(
            PredictionRecordRepository predictionRepository,
            @Value("${agent.service.url:http://agent-service:8001}") String agentServiceUrl,
            @Value("${prediction.settlement.enabled:true}") boolean enabled,
            @Value("${prediction.settlement.refresh-timeout-ms:120000}") long refreshTimeoutMillis) {
        this.predictionRepository = predictionRepository;
        this.webClient = WebClient.builder().baseUrl(agentServiceUrl).build();
        this.enabled = enabled;
        this.refreshTimeout = Duration.ofMillis(refreshTimeoutMillis);
    }

    /**
     * Tuesday 09:00 - late enough that Monday night is final and ESPN has
     * settled the box scores.
     */
    @Scheduled(cron = "${prediction.settlement.cron:0 0 9 * * TUE}")
    public void weeklySettlement() {
        if (!enabled) {
            logger.info("Settlement job disabled; skipping");
            return;
        }
        Map<String, Object> summary = settleSeason(currentSeason(), true);
        logger.info("Weekly settlement: " + summary);
    }

    /**
     * Refresh results, then settle every unsettled prediction that now has one.
     *
     * @param refreshFirst ask the agent service to re-pull from ESPN first.
     *                     Skip it when results are known to be current.
     */
    @Transactional
    public Map<String, Object> settleSeason(int season, boolean refreshFirst) {
        Map<String, Object> summary = new HashMap<>();
        summary.put("season", season);

        if (refreshFirst) {
            summary.put("refreshed", refreshResults(season));
        }

        List<GameResult> results = fetchResults(season);
        if (results.isEmpty()) {
            summary.put("settled", 0);
            summary.put("note", "No completed games found for " + season);
            return summary;
        }

        Map<Long, String> winnerByGame = new HashMap<>();
        for (GameResult result : results) {
            // A tie leaves winner null - skip rather than scoring it as a loss
            if (result.getGameId() != null && result.getWinner() != null) {
                winnerByGame.put(result.getGameId(), result.getWinner());
            }
        }

        SettleCounts counts = settlePending(winnerByGame);
        int settled = counts.settled();
        int unmatched = counts.unmatched();

        long total = predictionRepository.countSettled();
        long correct = predictionRepository.countCorrect();

        summary.put("pending_before", counts.considered());
        summary.put("settled", settled);
        summary.put("duplicates_skipped", counts.duplicatesSkipped());
        summary.put("still_pending", unmatched);
        summary.put("lifetime_settled", total);
        summary.put("lifetime_accuracy", total > 0 ? (double) correct / total : null);
        return summary;
    }

    private boolean refreshResults(int season) {
        try {
            webClient.post()
                    .uri(uriBuilder -> uriBuilder.path("/games/refresh")
                            .queryParam("season", season)
                            .build())
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(refreshTimeout)
                    .block();
            return true;
        } catch (Exception e) {
            // Settle against whatever is already stored rather than aborting
            logger.warning("Could not refresh results for " + season + ": " + e.getMessage());
            return false;
        }
    }

    private List<GameResult> fetchResults(int season) {
        try {
            GameResult.Response response = webClient.get()
                    .uri(uriBuilder -> uriBuilder.path("/games/results")
                            .queryParam("season", season)
                            .build())
                    .retrieve()
                    .bodyToMono(GameResult.Response.class)
                    .timeout(Duration.ofSeconds(30))
                    .block();
            return response == null || response.getResults() == null
                    ? List.of()
                    : response.getResults();
        } catch (Exception e) {
            logger.warning("Could not fetch results for " + season + ": " + e.getMessage());
            return List.of();
        }
    }

    /** How one settlement pass went. */
    record SettleCounts(int considered, int settled, int unmatched, int duplicatesSkipped) {}

    /**
     * Score every unsettled prediction that now has a result, at most one per
     * game, oldest record first.
     *
     * <p>The two rules here are the ones that were wrong before. Oldest-first
     * means the <em>original</em> pre-kickoff prediction is the one scored, not
     * whichever duplicate a re-run wrote last. And scoring at most one record
     * per game stops a duplicated game being counted several times in the
     * accuracy denominator. The unique constraint makes duplicates impossible
     * going forward; this keeps settlement honest about rows that predate it.
     *
     * <p>Package-private so it can be tested against a real database without
     * standing up the ESPN fetch.
     */
    SettleCounts settlePending(Map<Long, String> winnerByGame) {
        List<PredictionRecord> pending = predictionRepository.findBySettledFalseOrderByPredictedAtAsc();
        Set<Long> scoredGames = new HashSet<>();
        int settled = 0;
        int unmatched = 0;
        int duplicates = 0;

        for (PredictionRecord record : pending) {
            String winner = winnerByGame.get(record.getGameId());
            if (winner == null) {
                unmatched++;      // Game not finished, or a tie
                continue;
            }
            if (!scoredGames.add(record.getGameId())) {
                duplicates++;     // A pre-constraint duplicate; leave it unsettled
                continue;
            }
            record.settle(winner);
            predictionRepository.save(record);
            settled++;
        }
        return new SettleCounts(pending.size(), settled, unmatched, duplicates);
    }

    /**
     * The season currently in play.
     *
     * <p>Not the calendar year. An NFL season runs into the following January
     * and February, so from January the calendar year is one ahead of the season
     * label - season 2026 covers September 2026 through February 2027. Taking
     * the calendar year meant that every January, settlement went looking for
     * results in a season that had not started, found none, and scored nothing.
     * That is precisely the stretch where it matters most: the playoffs.
     */
    public static int currentSeason() {
        return seasonOf(LocalDate.now());
    }

    /** The season a given date falls in. Split out so the boundary is testable. */
    static int seasonOf(LocalDate date) {
        return date.getMonthValue() < 3 ? date.getYear() - 1 : date.getYear();
    }
}

package com.nflpredict.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nflpredict.dto.AgentPredictionsResponse;
import com.nflpredict.dto.ConsensusResult;
import com.nflpredict.dto.GameSummary;
import com.nflpredict.dto.GamesWeekResponse;
import com.nflpredict.model.PredictionRecord;
import com.nflpredict.repository.PredictionRecordRepository;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.logging.Logger;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

/**
 * The gateway's real job: fan out across a week's games, apply the weighted
 * vote to each, cache the answers and persist them for later scoring.
 *
 * <p>The Python service runs the agents; this service decides what their
 * output means. Keeping the vote here means agent weights live in Postgres and
 * every prediction is recorded, which is what will eventually let the two
 * uncalibrated agents earn a measured weight.
 */
@Service
public class PredictionOrchestrator {

    private static final Logger logger = Logger.getLogger(PredictionOrchestrator.class.getName());

    private final WebClient webClient;
    private final ConsensusService consensusService;
    private final PredictionRecordRepository predictionRepository;
    private final Executor fanOutExecutor;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Duration timeout;
    private final int maxRetries;

    public PredictionOrchestrator(
            ConsensusService consensusService,
            PredictionRecordRepository predictionRepository,
            @Qualifier("fanOutExecutor") Executor fanOutExecutor,
            @Value("${agent.service.url:http://agent-service:8001}") String agentServiceUrl,
            @Value("${agent.service.timeout:30000}") int timeoutMillis,
            @Value("${agent.service.retry.max-attempts:3}") int maxRetries) {
        this.consensusService = consensusService;
        this.predictionRepository = predictionRepository;
        this.fanOutExecutor = fanOutExecutor;
        this.webClient = WebClient.builder().baseUrl(agentServiceUrl).build();
        this.timeout = Duration.ofMillis(timeoutMillis);
        this.maxRetries = maxRetries;
    }

    /**
     * Predict one game: call the agents, apply the weighted vote, persist.
     *
     * <p>Cached by game id - agent output for a given matchup is stable over
     * the life of the cache entry, and this is the expensive call.
     */
    @Cacheable(value = "gamePredictions", key = "#gameId", unless = "#result == null")
    public ConsensusResult predictGame(Long gameId, String homeTeam, String awayTeam,
                                       LocalDateTime kickoff) {
        AgentPredictionsResponse agentOutput = callAgents(gameId, homeTeam, awayTeam, kickoff);
        if (agentOutput == null || agentOutput.getAgentPredictions() == null
                || agentOutput.getAgentPredictions().isEmpty()) {
            logger.warning("No agent output for game " + gameId);
            return null;
        }

        ConsensusResult result = consensusService.combine(
                gameId, homeTeam, awayTeam, agentOutput.getAgentPredictions());

        persist(result);
        return result;
    }

    /**
     * Predict every game in a week concurrently.
     *
     * <p>Each game is an independent call to the agent service, so they run in
     * parallel on a bounded pool rather than serially. On Java 21 this pool can
     * be swapped for {@code Executors.newVirtualThreadPerTaskExecutor()} - see
     * AsyncConfig.
     */
    public List<ConsensusResult> predictWeek(int week, Integer season) {
        GamesWeekResponse games = fetchWeek(week, season);
        if (games == null || games.games() == null || games.games().isEmpty()) {
            return List.of();
        }

        List<CompletableFuture<ConsensusResult>> futures = new ArrayList<>();
        for (GameSummary game : games.games()) {
            futures.add(CompletableFuture.supplyAsync(() -> {
                try {
                    return predictGame(
                            game.gameId() == null ? null : game.gameId().longValue(),
                            game.homeTeam(),
                            game.awayTeam(),
                            parseKickoff(game.gameDate()));
                } catch (Exception e) {
                    // One bad game must not sink the whole week
                    logger.warning("Prediction failed for game " + game.gameId()
                            + ": " + e.getMessage());
                    return null;
                }
            }, fanOutExecutor));
        }

        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();

        List<ConsensusResult> results = new ArrayList<>();
        for (CompletableFuture<ConsensusResult> future : futures) {
            ConsensusResult result = future.join();
            if (result != null) {
                results.add(result);
            }
        }
        logger.info("Week " + week + ": " + results.size() + "/"
                + games.games().size() + " games predicted");
        return results;
    }

    /** ESPN stores kickoff as an ISO instant such as 2025-09-05T00:20Z. */
    private LocalDateTime parseKickoff(String gameDate) {
        if (gameDate == null || gameDate.isBlank()) {
            return null;
        }
        try {
            return OffsetDateTime.parse(gameDate).toLocalDateTime();
        } catch (DateTimeParseException e) {
            try {
                return LocalDateTime.parse(gameDate);
            } catch (DateTimeParseException ignored) {
                return null;
            }
        }
    }

    private AgentPredictionsResponse callAgents(Long gameId, String homeTeam,
                                                String awayTeam, LocalDateTime kickoff) {
        Map<String, Object> gameData = new HashMap<>();
        gameData.put("game_id", gameId == null ? 0 : gameId.intValue());
        gameData.put("home_team_name", homeTeam);
        gameData.put("away_team_name", awayTeam);
        gameData.put("game_time", (kickoff == null ? LocalDateTime.now() : kickoff).toString());
        gameData.put("is_dome", false);

        Map<String, Object> request = new HashMap<>();
        request.put("game_data", gameData);
        request.put("include_reasoning", true);
        request.put("confidence_threshold", 0.0);

        Mono<AgentPredictionsResponse> call = webClient.post()
                .uri("/agents/predict-all")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(AgentPredictionsResponse.class)
                .timeout(timeout)
                .retryWhen(Retry.fixedDelay(maxRetries, Duration.ofSeconds(1)));

        try {
            return call.block();
        } catch (Exception e) {
            logger.warning("Agent service call failed for game " + gameId + ": " + e.getMessage());
            return null;
        }
    }

    private GamesWeekResponse fetchWeek(int week, Integer season) {
        try {
            return webClient.get()
                    .uri(uriBuilder -> {
                        uriBuilder.path("/games/week/" + week);
                        if (season != null) {
                            uriBuilder.queryParam("season", season);
                        }
                        return uriBuilder.build();
                    })
                    .retrieve()
                    .bodyToMono(GamesWeekResponse.class)
                    .timeout(timeout)
                    .block();
        } catch (Exception e) {
            logger.warning("Could not fetch week " + week + ": " + e.getMessage());
            return null;
        }
    }

    private void persist(ConsensusResult result) {
        try {
            String detail = serializeAgents(result);
            predictionRepository.save(new PredictionRecord(
                    result.getGameId(),
                    result.getHomeTeam(),
                    result.getAwayTeam(),
                    result.getWinner(),
                    result.getConfidence(),
                    result.getMethod(),
                    detail));
        } catch (Exception e) {
            // Persistence is for later analysis - never fail a prediction over it
            logger.warning("Could not persist prediction for game "
                    + result.getGameId() + ": " + e.getMessage());
        }
    }

    private String serializeAgents(ConsensusResult result) {
        try {
            return objectMapper.writeValueAsString(result.getAgentPredictions());
        } catch (JsonProcessingException e) {
            return "[]";
        }
    }

    /** Settle a finished game so live accuracy can be measured. */
    public boolean settle(Long gameId, String actualWinner) {
        return predictionRepository.findFirstByGameIdOrderByCreatedAtDesc(gameId)
                .map(record -> {
                    record.settle(actualWinner);
                    predictionRepository.save(record);
                    return true;
                })
                .orElse(false);
    }

    /** Accuracy over every settled prediction this gateway has served. */
    public Map<String, Object> liveAccuracy() {
        long settled = predictionRepository.countSettled();
        long correct = predictionRepository.countCorrect();

        Map<String, Object> summary = new HashMap<>();
        summary.put("settled_predictions", settled);
        summary.put("correct", correct);
        summary.put("accuracy", settled > 0 ? (double) correct / settled : null);
        summary.put("note", settled == 0
                ? "No settled predictions yet - accuracy appears once games are scored."
                : "Live accuracy across all settled predictions.");
        return summary;
    }
}

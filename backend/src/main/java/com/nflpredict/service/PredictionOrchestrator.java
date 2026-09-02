package com.nflpredict.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nflpredict.dto.AgentPredictionsResponse;
import com.nflpredict.dto.ConsensusResult;
import com.nflpredict.dto.GameSummary;
import com.nflpredict.dto.GamesWeekResponse;
import com.nflpredict.model.PredictionRecord;
import com.nflpredict.repository.PredictionRecordRepository;
import java.time.Clock;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.logging.Logger;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.dao.DataIntegrityViolationException;
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
    /**
     * UTC, because kickoffs are stored as UTC wall time - the agent service
     * returns ISO instants like 2026-09-10T00:20Z and parseKickoff keeps the
     * UTC side of them. Comparing those against a server-local now() would put
     * the pre-kickoff check hours out on any host not set to UTC. Injected so
     * tests can move it.
     */
    private final Clock clock;

    public PredictionOrchestrator(
            ConsensusService consensusService,
            PredictionRecordRepository predictionRepository,
            @Qualifier("fanOutExecutor") Executor fanOutExecutor,
            Clock clock,
            @Value("${agent.service.url:http://agent-service:8001}") String agentServiceUrl,
            @Value("${agent.service.timeout:30000}") int timeoutMillis,
            @Value("${agent.service.retry.max-attempts:3}") int maxRetries) {
        this.consensusService = consensusService;
        this.predictionRepository = predictionRepository;
        this.fanOutExecutor = fanOutExecutor;
        this.clock = clock;
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
                                       LocalDateTime kickoff, Integer season, Integer week) {
        AgentPredictionsResponse agentOutput = callAgents(gameId, homeTeam, awayTeam, kickoff);
        if (agentOutput == null || agentOutput.getAgentPredictions() == null
                || agentOutput.getAgentPredictions().isEmpty()) {
            logger.warning("No agent output for game " + gameId);
            return null;
        }

        ConsensusResult result = consensusService.combine(
                gameId, homeTeam, awayTeam, agentOutput.getAgentPredictions());

        // Always returns the fresh result to the caller; whether it becomes the
        // official record on file is a separate question, answered below.
        persistOfficial(result, kickoff, season, week);
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
                            parseKickoff(game.gameDate()),
                            game.season(),
                            game.week());
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

    /** Why a prediction was or was not written. Returned for logging and tests. */
    public enum OfficialOutcome {
        /** Written - this is now the official prediction for the game. */
        RECORDED,
        /** A prediction already exists; the original is left untouched. */
        ALREADY_RECORDED,
        /** Kickoff has passed, so this can never be an official prediction. */
        AFTER_KICKOFF,
        /** Kickoff unknown, so it cannot be certified as pre-kickoff. */
        KICKOFF_UNKNOWN,
        /** Nothing usable to key a record on. */
        NOT_PERSISTABLE
    }

    /**
     * Record a prediction as the official one for its game, if it qualifies.
     *
     * <p>Three things have to hold, and each is enforced rather than assumed:
     *
     * <ol>
     *   <li><b>It must be pre-kickoff.</b> A prediction made after the game has
     *       started is not a prediction, and letting one in would quietly
     *       inflate measured accuracy. Kickoff is UTC wall time and so is the
     *       clock - see the field comment.</li>
     *   <li><b>The original wins.</b> If a record exists we keep it and do not
     *       update it. Re-running the weekly endpoint must not restate a pick
     *       made days earlier with better information.</li>
     *   <li><b>One row per game, guaranteed by the database.</b> The
     *       existsByGameId check races: predictWeek fans out over a thread pool
     *       and two callers can both pass it before either inserts. The unique
     *       constraint on game_id is the real guard, and a violation here means
     *       another thread won - which is a success, not an error.</li>
     * </ol>
     *
     * <p>Not private, so the guard can be tested against a real database
     * without standing up the HTTP layer.
     */
    OfficialOutcome persistOfficial(ConsensusResult result, LocalDateTime kickoff,
                                    Integer season, Integer week) {
        if (result == null || result.getGameId() == null) {
            return OfficialOutcome.NOT_PERSISTABLE;
        }
        Long gameId = result.getGameId();

        if (kickoff == null) {
            // Refuse rather than guess. The single-game endpoint has no kickoff
            // to offer, and a record we cannot certify as pre-kickoff would
            // corrupt the only measurement this table exists to support.
            logger.fine("No kickoff for game " + gameId + "; not recording an official prediction");
            return OfficialOutcome.KICKOFF_UNKNOWN;
        }

        LocalDateTime now = LocalDateTime.now(clock);
        if (!now.isBefore(kickoff)) {
            logger.fine("Game " + gameId + " kicked off at " + kickoff
                    + "; not recording an official prediction");
            return OfficialOutcome.AFTER_KICKOFF;
        }

        if (predictionRepository.existsByGameId(gameId)) {
            return OfficialOutcome.ALREADY_RECORDED;
        }

        try {
            predictionRepository.save(new PredictionRecord(
                    gameId,
                    season,
                    week,
                    result.getHomeTeam(),
                    result.getAwayTeam(),
                    result.getWinner(),
                    result.getConfidence(),
                    result.getMethod(),
                    serializeAgents(result),
                    kickoff,
                    now));
            return OfficialOutcome.RECORDED;
        } catch (DataIntegrityViolationException e) {
            // Another thread inserted first. That is the constraint doing its
            // job, so treat it as success rather than noise.
            logger.fine("Game " + gameId + " was recorded concurrently; keeping the first");
            return OfficialOutcome.ALREADY_RECORDED;
        } catch (Exception e) {
            // Persistence is for later analysis - never fail a prediction over it
            logger.warning("Could not persist prediction for game " + gameId + ": " + e.getMessage());
            return OfficialOutcome.NOT_PERSISTABLE;
        }
    }

    private String serializeAgents(ConsensusResult result) {
        try {
            return objectMapper.writeValueAsString(result.getAgentPredictions());
        } catch (JsonProcessingException e) {
            return "[]";
        }
    }

    /**
     * Settle a finished game so live accuracy can be measured.
     *
     * <p>Scores the <em>original</em> prediction. This used to take the newest
     * record for the game, which meant a duplicate written by a re-run - made
     * later, with more information - was the one scored.
     */
    public boolean settle(Long gameId, String actualWinner) {
        return predictionRepository.findFirstByGameIdOrderByPredictedAtAsc(gameId)
                .map(record -> {
                    record.settle(actualWinner);
                    predictionRepository.save(record);
                    return true;
                })
                .orElse(false);
    }

    /** Accuracy over every settled prediction this gateway has served. */
    public Map<String, Object> liveAccuracy() {
        long total = predictionRepository.count();
        long settled = predictionRepository.countSettled();
        long pending = predictionRepository.countBySettledFalse();
        long correct = predictionRepository.countCorrect();

        Map<String, Object> summary = new LinkedHashMap<>();
        // total is the count of official predictions on record. It is also the
        // cheapest way to verify idempotency from outside: run the weekly
        // endpoint twice and this must not move.
        summary.put("total_predictions", total);
        summary.put("settled_predictions", settled);
        summary.put("pending_predictions", pending);
        summary.put("correct", correct);
        summary.put("accuracy", settled > 0 ? (double) correct / settled : null);
        summary.put("note", settled == 0
                ? "No settled predictions yet - accuracy appears once games are scored."
                : "Live accuracy across all settled predictions.");
        return summary;
    }
}

package com.nflpredict.service;

import com.nflpredict.dto.AgentPredictionDto;
import com.nflpredict.dto.ConsensusResult;
import com.nflpredict.model.AgentWeight;
import com.nflpredict.repository.AgentWeightRepository;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

/**
 * Owns the weighted vote.
 *
 * <p>Each agent contributes {@code weight * (confidence - 0.5)} to whichever
 * team it picked; the higher total wins. An agent that could not beat a coin
 * flip in backtest carries weight zero and therefore cannot swing anything,
 * and an agent with no data returns confidence 0.50, contributing nothing
 * without injecting noise.
 *
 * <p>This mirrors {@code agent-service/agents/consensus.py}. The Python copy
 * remains authoritative for the backtest harness; this one serves live traffic
 * and reads its weights from Postgres so recalibrating needs no redeploy.
 */
@Service
public class ConsensusService {

    private static final Logger logger = Logger.getLogger(ConsensusService.class.getName());

    /** Confidence above 0.5 that a maximally confident agent can contribute. */
    private static final double MAX_CONFIDENCE_EDGE = 0.4;

    private final AgentWeightRepository agentWeightRepository;
    private final double defaultWeight;

    public ConsensusService(AgentWeightRepository agentWeightRepository,
                            @Value("${prediction.consensus.default-weight:0.02}") double defaultWeight) {
        this.agentWeightRepository = agentWeightRepository;
        this.defaultWeight = defaultWeight;
    }

    /**
     * Agent weights, cached because they change only on recalibration.
     */
    @Cacheable(value = "agentWeights", unless = "#result == null")
    public Map<String, Double> getWeights() {
        Map<String, Double> weights = new HashMap<>();
        for (AgentWeight row : agentWeightRepository.findAll()) {
            weights.put(row.getAgentName(), Math.max(0.0, row.getWeight()));
        }
        if (weights.isEmpty()) {
            logger.warning("No agent weights in database; every agent falls back to the default");
        }
        return weights;
    }

    @CacheEvict(value = "agentWeights", allEntries = true)
    public void invalidateWeights() {
        logger.info("Agent weight cache cleared");
    }

    private double weightFor(String agentName, Map<String, Double> weights) {
        return Math.max(0.0, weights.getOrDefault(agentName, defaultWeight));
    }

    public ConsensusResult combine(Long gameId, String homeTeam, String awayTeam,
                                   List<AgentPredictionDto> predictions) {
        if (predictions == null || predictions.isEmpty()) {
            throw new IllegalArgumentException("Cannot build a consensus from zero predictions");
        }

        Map<String, Double> weights = getWeights();

        int homeVotes = 0;
        int awayVotes = 0;
        double homeScore = 0.0;
        double awayScore = 0.0;
        double totalWeight = 0.0;

        for (AgentPredictionDto prediction : predictions) {
            String pick = prediction.getPredictedWinner();
            double confidence = prediction.getConfidence() == null ? 0.5 : prediction.getConfidence();
            double weight = weightFor(prediction.getAgentName(), weights);
            double edge = Math.max(0.0, confidence - 0.5);

            totalWeight += weight;

            if (homeTeam.equals(pick)) {
                homeVotes++;
                homeScore += weight * edge;
            } else if (awayTeam.equals(pick)) {
                awayVotes++;
                awayScore += weight * edge;
            }
        }

        ConsensusResult result = new ConsensusResult();
        result.setGameId(gameId);
        result.setHomeTeam(homeTeam);
        result.setAwayTeam(awayTeam);
        result.setHomeVotes(homeVotes);
        result.setAwayVotes(awayVotes);
        result.setAgentPredictions(predictions);
        result.setPredictionTime(LocalDateTime.now());

        Map<String, Double> scores = new LinkedHashMap<>();
        scores.put(homeTeam, round(homeScore));
        scores.put(awayTeam, round(awayScore));
        result.setWeightedScores(scores);

        if (homeScore == awayScore) {
            // No weighted separation - fall back to the raw vote, then to the
            // single most confident agent.
            applyMajorityFallback(result, predictions, homeTeam, awayTeam, homeVotes, awayVotes);
            return result;
        }

        boolean homeWins = homeScore > awayScore;
        String winner = homeWins ? homeTeam : awayTeam;
        double margin = Math.abs(homeScore - awayScore);
        double maxMargin = totalWeight * MAX_CONFIDENCE_EDGE;
        double share = maxMargin > 0 ? margin / maxMargin : 0.0;

        result.setWinner(winner);
        result.setConfidence(round(Math.min(0.90, 0.5 + 0.4 * share)));
        result.setMethod("weighted");

        int winningVotes = homeWins ? homeVotes : awayVotes;
        int total = predictions.size();
        String headline;
        if (winningVotes == total) {
            headline = String.format("Unanimous: all %d agents favor %s. ", total, winner);
        } else if (winningVotes * 2 > total) {
            headline = String.format("Weighted consensus favors %s (%d/%d agents). ",
                    winner, winningVotes, total);
        } else {
            headline = String.format(
                    "Weighted consensus favors %s despite a %d/%d vote split - "
                            + "higher-accuracy agents outweigh the count. ",
                    winner, winningVotes, total);
        }
        result.setReasoning(headline + summarize(predictions));
        return result;
    }

    private void applyMajorityFallback(ConsensusResult result, List<AgentPredictionDto> predictions,
                                       String homeTeam, String awayTeam,
                                       int homeVotes, int awayVotes) {
        result.setMethod("majority-fallback");

        if (homeVotes != awayVotes) {
            String winner = homeVotes > awayVotes ? homeTeam : awayTeam;
            double sum = 0.0;
            int count = 0;
            for (AgentPredictionDto prediction : predictions) {
                if (winner.equals(prediction.getPredictedWinner())) {
                    sum += prediction.getConfidence() == null ? 0.5 : prediction.getConfidence();
                    count++;
                }
            }
            result.setWinner(winner);
            result.setConfidence(round(count > 0 ? sum / count : 0.5));
            result.setReasoning(String.format(
                    "No weighted separation. Majority: %d/%d agents favor %s. ",
                    Math.max(homeVotes, awayVotes), predictions.size(), winner) + summarize(predictions));
            return;
        }

        AgentPredictionDto mostConfident = predictions.get(0);
        for (AgentPredictionDto prediction : predictions) {
            double current = prediction.getConfidence() == null ? 0.5 : prediction.getConfidence();
            double best = mostConfident.getConfidence() == null ? 0.5 : mostConfident.getConfidence();
            if (current > best) {
                mostConfident = prediction;
            }
        }
        double confidence = mostConfident.getConfidence() == null ? 0.5 : mostConfident.getConfidence();
        result.setWinner(mostConfident.getPredictedWinner());
        result.setConfidence(round(confidence * 0.9));
        result.setReasoning(String.format(
                "No weighted separation and a %d-%d vote split, resolved by highest confidence. ",
                homeVotes, awayVotes) + summarize(predictions));
    }

    private String summarize(List<AgentPredictionDto> predictions) {
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < predictions.size(); i++) {
            AgentPredictionDto prediction = predictions.get(i);
            if (i > 0) {
                builder.append(" | ");
            }
            String reasoning = prediction.getReasoning() == null ? "" : prediction.getReasoning();
            builder.append(prediction.getAgentName())
                   .append(": ")
                   .append(reasoning.length() > 40 ? reasoning.substring(0, 40) : reasoning)
                   .append("...");
        }
        return builder.toString();
    }

    private double round(double value) {
        return Math.round(value * 10000.0) / 10000.0;
    }
}

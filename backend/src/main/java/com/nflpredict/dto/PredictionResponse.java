package com.nflpredict.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record PredictionResponse(
        @JsonProperty("game_id") Integer gameId,
        @JsonProperty("overall_winner") String overallWinner,
        @JsonProperty("overall_confidence") Double overallConfidence,
        @JsonProperty("agent_predictions") List<AgentPredictionResponse> agentPredictions,
        @JsonProperty("consensus_reasoning") String consensusReasoning,
        @JsonProperty("prediction_time") String predictionTime) {
}

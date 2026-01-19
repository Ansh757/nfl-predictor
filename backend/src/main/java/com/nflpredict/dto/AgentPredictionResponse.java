package com.nflpredict.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record AgentPredictionResponse(
        @JsonProperty("agent_name") String agentName,
        @JsonProperty("predicted_winner") String predictedWinner,
        @JsonProperty("confidence") Double confidence,
        @JsonProperty("reasoning") String reasoning,
        @JsonProperty("prediction_time") String predictionTime) {
}

package com.nflpredict.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record PredictionRequest(
        @JsonProperty("game_data") GameDataRequest gameData,
        @JsonProperty("include_reasoning") Boolean includeReasoning,
        @JsonProperty("confidence_threshold") Double confidenceThreshold) {
}

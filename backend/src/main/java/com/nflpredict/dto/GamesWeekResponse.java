package com.nflpredict.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record GamesWeekResponse(
        @JsonProperty("games") List<GameSummary> games,
        @JsonProperty("week") Integer week) {
}

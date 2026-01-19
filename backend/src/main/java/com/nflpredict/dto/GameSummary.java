package com.nflpredict.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record GameSummary(
        @JsonProperty("game_id") Integer gameId,
        @JsonProperty("season") Integer season,
        @JsonProperty("week") Integer week,
        @JsonProperty("game_date") String gameDate,
        @JsonProperty("home_team") String homeTeam,
        @JsonProperty("away_team") String awayTeam,
        @JsonProperty("venue") String venue,
        @JsonProperty("is_dome") Boolean isDome,
        @JsonProperty("game_status") String gameStatus) {
}

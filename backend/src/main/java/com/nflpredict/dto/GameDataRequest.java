package com.nflpredict.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record GameDataRequest(
        @JsonProperty("game_id") Integer gameId,
        @JsonProperty("home_team_name") String homeTeamName,
        @JsonProperty("away_team_name") String awayTeamName,
        @JsonProperty("game_time") String gameTime,
        @JsonProperty("venue") String venue,
        @JsonProperty("is_dome") Boolean isDome) {
}

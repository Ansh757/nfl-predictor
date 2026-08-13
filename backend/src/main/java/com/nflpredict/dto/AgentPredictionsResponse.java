package com.nflpredict.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/** Raw, unaggregated agent output for a single game. */
@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentPredictionsResponse {

    @JsonProperty("game_id")
    private Long gameId;

    @JsonProperty("home_team")
    private String homeTeam;

    @JsonProperty("away_team")
    private String awayTeam;

    @JsonProperty("agent_predictions")
    private List<AgentPredictionDto> agentPredictions;

    public Long getGameId() {
        return gameId;
    }

    public void setGameId(Long gameId) {
        this.gameId = gameId;
    }

    public String getHomeTeam() {
        return homeTeam;
    }

    public void setHomeTeam(String homeTeam) {
        this.homeTeam = homeTeam;
    }

    public String getAwayTeam() {
        return awayTeam;
    }

    public void setAwayTeam(String awayTeam) {
        this.awayTeam = awayTeam;
    }

    public List<AgentPredictionDto> getAgentPredictions() {
        return agentPredictions;
    }

    public void setAgentPredictions(List<AgentPredictionDto> agentPredictions) {
        this.agentPredictions = agentPredictions;
    }
}

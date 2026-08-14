package com.nflpredict.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/** A completed game with its final score, from the agent service. */
@JsonIgnoreProperties(ignoreUnknown = true)
public class GameResult {

    @JsonProperty("game_id")
    private Long gameId;

    @JsonProperty("home_team")
    private String homeTeam;

    @JsonProperty("away_team")
    private String awayTeam;

    @JsonProperty("home_score")
    private Integer homeScore;

    @JsonProperty("away_score")
    private Integer awayScore;

    /** Null on a tie - there is nothing to settle a pick against. */
    private String winner;

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

    public Integer getHomeScore() {
        return homeScore;
    }

    public void setHomeScore(Integer homeScore) {
        this.homeScore = homeScore;
    }

    public Integer getAwayScore() {
        return awayScore;
    }

    public void setAwayScore(Integer awayScore) {
        this.awayScore = awayScore;
    }

    public String getWinner() {
        return winner;
    }

    public void setWinner(String winner) {
        this.winner = winner;
    }

    /** Wrapper for the /games/results payload. */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Response {

        private Integer season;
        private Integer count;
        private List<GameResult> results;

        public Integer getSeason() {
            return season;
        }

        public void setSeason(Integer season) {
            this.season = season;
        }

        public Integer getCount() {
            return count;
        }

        public void setCount(Integer count) {
            this.count = count;
        }

        public List<GameResult> getResults() {
            return results;
        }

        public void setResults(List<GameResult> results) {
            this.results = results;
        }
    }
}

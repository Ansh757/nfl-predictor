package com.nflpredict.dto;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/** Outcome of the weighted vote, as served to clients and cached in Redis. */
public class ConsensusResult implements Serializable {

    private static final long serialVersionUID = 1L;

    private Long gameId;
    private String homeTeam;
    private String awayTeam;
    private String winner;
    private Double confidence;
    private String reasoning;
    private String method;
    private int homeVotes;
    private int awayVotes;
    private Map<String, Double> weightedScores;
    private List<AgentPredictionDto> agentPredictions;

    /**
     * Venue context, kept as two independent flags so the stored reasoning
     * stays reproducible. neutralSite explains why no home-field advantage was
     * applied; internationalGame explains the travel wording. A Super Bowl is
     * the first without being the second.
     */
    private Boolean neutralSite;
    private Boolean internationalGame;
    private String venueCountry;
    private String venueTimezone;
    private LocalDateTime predictionTime;

    public ConsensusResult() {
        // Jackson / Redis deserialization
    }

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

    public String getWinner() {
        return winner;
    }

    public void setWinner(String winner) {
        this.winner = winner;
    }

    public Double getConfidence() {
        return confidence;
    }

    public void setConfidence(Double confidence) {
        this.confidence = confidence;
    }

    public String getReasoning() {
        return reasoning;
    }

    public void setReasoning(String reasoning) {
        this.reasoning = reasoning;
    }

    public String getMethod() {
        return method;
    }

    public void setMethod(String method) {
        this.method = method;
    }

    public int getHomeVotes() {
        return homeVotes;
    }

    public void setHomeVotes(int homeVotes) {
        this.homeVotes = homeVotes;
    }

    public int getAwayVotes() {
        return awayVotes;
    }

    public void setAwayVotes(int awayVotes) {
        this.awayVotes = awayVotes;
    }

    public Map<String, Double> getWeightedScores() {
        return weightedScores;
    }

    public void setWeightedScores(Map<String, Double> weightedScores) {
        this.weightedScores = weightedScores;
    }

    public List<AgentPredictionDto> getAgentPredictions() {
        return agentPredictions;
    }

    public void setAgentPredictions(List<AgentPredictionDto> agentPredictions) {
        this.agentPredictions = agentPredictions;
    }

    public LocalDateTime getPredictionTime() {
        return predictionTime;
    }

    public void setPredictionTime(LocalDateTime predictionTime) {
        this.predictionTime = predictionTime;
    }

    public Boolean getNeutralSite() {
        return neutralSite;
    }

    public void setNeutralSite(Boolean neutralSite) {
        this.neutralSite = neutralSite;
    }

    public Boolean getInternationalGame() {
        return internationalGame;
    }

    public void setInternationalGame(Boolean internationalGame) {
        this.internationalGame = internationalGame;
    }

    public String getVenueCountry() {
        return venueCountry;
    }

    public void setVenueCountry(String venueCountry) {
        this.venueCountry = venueCountry;
    }

    public String getVenueTimezone() {
        return venueTimezone;
    }

    public void setVenueTimezone(String venueTimezone) {
        this.venueTimezone = venueTimezone;
    }
}

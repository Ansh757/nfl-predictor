package com.nflpredict.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** One agent's pick, as returned by the Python service's /agents/predict-all. */
public class AgentPredictionDto {

    @JsonProperty("agent_name")
    private String agentName;

    @JsonProperty("predicted_winner")
    private String predictedWinner;

    private Double confidence;

    private String reasoning;

    private String source;

    public String getAgentName() {
        return agentName;
    }

    public void setAgentName(String agentName) {
        this.agentName = agentName;
    }

    public String getPredictedWinner() {
        return predictedWinner;
    }

    public void setPredictedWinner(String predictedWinner) {
        this.predictedWinner = predictedWinner;
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

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }
}

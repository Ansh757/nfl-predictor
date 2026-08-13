package com.nflpredict.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/**
 * How much influence one agent has in the weighted consensus.
 *
 * <p>A weight is the agent's measured edge over a coin flip, taken from the
 * Python backtest harness ({@code agent-service/backtest.py}) and floored at
 * zero, so an agent that cannot beat 50% contributes nothing. Storing these in
 * the database rather than in code means recalibrating after a season does not
 * require a redeploy.
 */
@Entity
@Table(name = "agent_weights")
public class AgentWeight {

    @Id
    @Column(name = "agent_name", nullable = false, length = 100)
    private String agentName;

    @Column(nullable = false)
    private Double weight;

    /** Accuracy the weight was derived from, for auditability. */
    @Column(name = "measured_accuracy")
    private Double measuredAccuracy;

    /** Seasons the measurement covers, e.g. "2021-2024". */
    @Column(name = "calibration_window", length = 50)
    private String calibrationWindow;

    /** False when no historical data exists to backtest the agent against. */
    @Column(name = "is_calibrated", nullable = false)
    private Boolean calibrated = Boolean.FALSE;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    protected AgentWeight() {
        // JPA
    }

    public AgentWeight(String agentName, Double weight, Double measuredAccuracy,
                       String calibrationWindow, Boolean calibrated) {
        this.agentName = agentName;
        this.weight = weight;
        this.measuredAccuracy = measuredAccuracy;
        this.calibrationWindow = calibrationWindow;
        this.calibrated = calibrated;
        this.updatedAt = LocalDateTime.now();
    }

    public String getAgentName() {
        return agentName;
    }

    public Double getWeight() {
        return weight;
    }

    public void setWeight(Double weight) {
        this.weight = weight;
        this.updatedAt = LocalDateTime.now();
    }

    public Double getMeasuredAccuracy() {
        return measuredAccuracy;
    }

    public void setMeasuredAccuracy(Double measuredAccuracy) {
        this.measuredAccuracy = measuredAccuracy;
    }

    public String getCalibrationWindow() {
        return calibrationWindow;
    }

    public void setCalibrationWindow(String calibrationWindow) {
        this.calibrationWindow = calibrationWindow;
    }

    public Boolean getCalibrated() {
        return calibrated;
    }

    public void setCalibrated(Boolean calibrated) {
        this.calibrated = calibrated;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }
}

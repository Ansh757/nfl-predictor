package com.nflpredict.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/**
 * A prediction as it was made, kept so accuracy can be measured continuously
 * rather than only in the offline backtest.
 *
 * <p>This is what eventually lets the two uncalibrated agents (Market Odds and
 * Injury Impact) earn a real weight: neither can be backtested, but once a
 * season of live predictions has been recorded and settled against results,
 * their edge can be measured the same way every other agent's was.
 */
@Entity
@Table(
    name = "predictions",
    indexes = {
        @Index(name = "idx_predictions_game", columnList = "game_id"),
        @Index(name = "idx_predictions_settled", columnList = "settled")
    }
)
public class PredictionRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "game_id", nullable = false)
    private Long gameId;

    @Column(name = "home_team", nullable = false, length = 100)
    private String homeTeam;

    @Column(name = "away_team", nullable = false, length = 100)
    private String awayTeam;

    @Column(name = "predicted_winner", nullable = false, length = 100)
    private String predictedWinner;

    @Column(nullable = false)
    private Double confidence;

    @Column(name = "consensus_method", length = 30)
    private String consensusMethod;

    /** Per-agent picks as JSON, so a prediction can be audited after the fact. */
    @Column(name = "agent_detail", columnDefinition = "TEXT")
    private String agentDetail;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    // --- Filled in once the game finishes

    @Column(name = "actual_winner", length = 100)
    private String actualWinner;

    @Column(name = "was_correct")
    private Boolean wasCorrect;

    @Column(nullable = false)
    private Boolean settled = Boolean.FALSE;

    protected PredictionRecord() {
        // JPA
    }

    public PredictionRecord(Long gameId, String homeTeam, String awayTeam,
                            String predictedWinner, Double confidence,
                            String consensusMethod, String agentDetail) {
        this.gameId = gameId;
        this.homeTeam = homeTeam;
        this.awayTeam = awayTeam;
        this.predictedWinner = predictedWinner;
        this.confidence = confidence;
        this.consensusMethod = consensusMethod;
        this.agentDetail = agentDetail;
        this.createdAt = LocalDateTime.now();
        this.settled = Boolean.FALSE;
    }

    /** Record the final result and whether the pick was right. */
    public void settle(String actualWinner) {
        this.actualWinner = actualWinner;
        this.wasCorrect = this.predictedWinner.equals(actualWinner);
        this.settled = Boolean.TRUE;
    }

    public Long getId() {
        return id;
    }

    public Long getGameId() {
        return gameId;
    }

    public String getHomeTeam() {
        return homeTeam;
    }

    public String getAwayTeam() {
        return awayTeam;
    }

    public String getPredictedWinner() {
        return predictedWinner;
    }

    public Double getConfidence() {
        return confidence;
    }

    public String getConsensusMethod() {
        return consensusMethod;
    }

    public String getAgentDetail() {
        return agentDetail;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public String getActualWinner() {
        return actualWinner;
    }

    public Boolean getWasCorrect() {
        return wasCorrect;
    }

    public Boolean getSettled() {
        return settled;
    }
}

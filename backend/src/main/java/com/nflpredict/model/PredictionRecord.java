package com.nflpredict.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.LocalDateTime;

/**
 * A prediction as it was made, kept so accuracy can be measured continuously
 * rather than only in the offline backtest.
 *
 * <p>This is what eventually lets the two uncalibrated agents (Market Odds and
 * Injury Impact) earn a real weight: neither can be backtested, but once a
 * season of live predictions has been recorded and settled against results,
 * their edge can be measured the same way every other agent's was.
 *
 * <p><strong>Exactly one record per game.</strong> A record is the
 * <em>official</em> prediction: the one made before kickoff, which is the only
 * kind that means anything for accuracy. Re-running the weekly endpoint used to
 * insert a second row per game, so a repeat call inflated the table and
 * settlement scored the newest copy rather than the original call. The unique
 * constraint below is what actually prevents that - an application-side
 * existence check cannot, because the week fans out across a thread pool and
 * two callers can pass the check before either has inserted.
 */
@Entity
@Table(
    name = "predictions",
    uniqueConstraints = {
        @UniqueConstraint(name = "uq_predictions_game", columnNames = "game_id")
    },
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

    /**
     * Season and week the game belongs to. Nullable because rows written before
     * this column existed cannot be backfilled reliably; every record written
     * from now on carries both.
     */
    @Column(name = "season")
    private Integer season;

    @Column(name = "week")
    private Integer week;

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

    /**
     * When the prediction was made. Renamed from created_at: what matters about
     * this timestamp is that it precedes kickoff, not that a row was inserted.
     */
    @Column(name = "predicted_at", nullable = false)
    private LocalDateTime predictedAt;

    /**
     * Kickoff, as UTC wall time - the agent service returns ISO instants such
     * as 2026-09-10T00:20Z. Stored so that "was this made before kickoff?" is
     * answerable from the row itself rather than by re-fetching the schedule.
     */
    @Column(name = "kickoff_at")
    private LocalDateTime kickoffAt;

    /**
     * Venue context as it was understood when the prediction was made.
     *
     * <p>Two independent facts, never collapsed. {@code neutralSite} says the
     * designated home team was not at its own ground, which is why no
     * home-field advantage was applied; {@code internationalGame} says the
     * venue was outside the United States, which is what enabled the travel
     * adjustment and its wording. A Super Bowl is the first without being the
     * second.
     *
     * <p>Nullable, because rows written before these columns existed have no
     * answer and defaulting them to false would assert something never
     * computed.
     */
    @Column(name = "neutral_site")
    private Boolean neutralSite;

    @Column(name = "international_game")
    private Boolean internationalGame;

    @Column(name = "venue_country", length = 64)
    private String venueCountry;

    @Column(name = "venue_timezone", length = 64)
    private String venueTimezone;

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

    /**
     * Without venue context - for a caller that has none to offer. The four
     * fields stay null rather than defaulting to false, because "not recorded"
     * and "not a neutral site" are different claims.
     */
    public PredictionRecord(Long gameId, Integer season, Integer week,
                            String homeTeam, String awayTeam,
                            String predictedWinner, Double confidence,
                            String consensusMethod, String agentDetail,
                            LocalDateTime kickoffAt, LocalDateTime predictedAt) {
        this(gameId, season, week, homeTeam, awayTeam, predictedWinner, confidence,
             consensusMethod, agentDetail, kickoffAt, predictedAt, null, null, null, null);
    }

    public PredictionRecord(Long gameId, Integer season, Integer week,
                            String homeTeam, String awayTeam,
                            String predictedWinner, Double confidence,
                            String consensusMethod, String agentDetail,
                            LocalDateTime kickoffAt, LocalDateTime predictedAt,
                            Boolean neutralSite, Boolean internationalGame,
                            String venueCountry, String venueTimezone) {
        this.gameId = gameId;
        this.season = season;
        this.week = week;
        this.homeTeam = homeTeam;
        this.awayTeam = awayTeam;
        this.predictedWinner = predictedWinner;
        this.confidence = confidence;
        this.consensusMethod = consensusMethod;
        this.agentDetail = agentDetail;
        this.kickoffAt = kickoffAt;
        this.predictedAt = predictedAt;
        this.neutralSite = neutralSite;
        this.internationalGame = internationalGame;
        this.venueCountry = venueCountry;
        this.venueTimezone = venueTimezone;
        this.settled = Boolean.FALSE;
    }

    /**
     * Record the final result and whether the pick was right.
     *
     * <p>Deliberately refuses to re-settle. Settlement runs weekly over
     * everything unsettled, and an already-scored record must not be rewritten
     * by a later pass - that would let a re-run change history.
     */
    public void settle(String actualWinner) {
        if (Boolean.TRUE.equals(this.settled)) {
            return;
        }
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

    public LocalDateTime getPredictedAt() {
        return predictedAt;
    }

    public LocalDateTime getKickoffAt() {
        return kickoffAt;
    }

    public Boolean getNeutralSite() {
        return neutralSite;
    }

    public Boolean getInternationalGame() {
        return internationalGame;
    }

    public String getVenueCountry() {
        return venueCountry;
    }

    public String getVenueTimezone() {
        return venueTimezone;
    }

    public Integer getSeason() {
        return season;
    }

    public Integer getWeek() {
        return week;
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

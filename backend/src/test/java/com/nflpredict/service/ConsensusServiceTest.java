package com.nflpredict.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

import com.nflpredict.dto.AgentPredictionDto;
import com.nflpredict.dto.ConsensusResult;
import com.nflpredict.model.AgentWeight;
import com.nflpredict.repository.AgentWeightRepository;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * ConsensusService decides every prediction the gateway serves, and it mirrors
 * agents/consensus.py. The two can drift apart silently, so the important cases
 * are pinned here - particularly the ones that were bugs in the Python original.
 */
@ExtendWith(MockitoExtension.class)
class ConsensusServiceTest {

    private static final String HOME = "Kansas City Chiefs";
    private static final String AWAY = "Buffalo Bills";

    // Mirrors the calibrated weights in AgentWeightSeeder
    private static final double MARKET = 0.164;
    private static final double BASIC = 0.121;
    private static final double ELO = 0.115;
    private static final double REST = 0.022;
    private static final double NEWS = 0.0;
    private static final double DEFAULT_WEIGHT = 0.02;

    @Mock
    private AgentWeightRepository repository;

    private ConsensusService service;

    @BeforeEach
    void setUp() {
        service = new ConsensusService(repository, DEFAULT_WEIGHT);
    }

    private void givenCalibratedWeights() {
        when(repository.findAll()).thenReturn(List.of(
                new AgentWeight("Market Odds", MARKET, 0.664, "2021-2024", true),
                new AgentWeight("Basic Predictor", BASIC, 0.621, "2021-2024", true),
                new AgentWeight("Elo Ratings", ELO, 0.615, "2021-2024", true),
                new AgentWeight("Rest & Travel", REST, 0.522, "2021-2024", true),
                new AgentWeight("News Sentiment", NEWS, 0.497, "2021-2024", true)));
    }

    private AgentPredictionDto prediction(String agent, String winner, double confidence) {
        AgentPredictionDto dto = new AgentPredictionDto();
        dto.setAgentName(agent);
        dto.setPredictedWinner(winner);
        dto.setConfidence(confidence);
        dto.setReasoning(agent + " reasoning");
        return dto;
    }

    @Test
    @DisplayName("A numerical majority of low-weight agents loses to one high-weight agent")
    void weightBeatsHeadcount() {
        givenCalibratedWeights();

        // 3 votes for AWAY from agents with almost no measured edge,
        // 1 vote for HOME from the strongest agent
        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("Market Odds", HOME, 0.80),
                prediction("News Sentiment", AWAY, 0.90),
                prediction("Rest & Travel", AWAY, 0.70),
                prediction("Weather Impact", AWAY, 0.70)));

        assertEquals(HOME, result.getWinner());
        assertEquals(1, result.getHomeVotes());
        assertEquals(3, result.getAwayVotes());
        assertEquals("weighted", result.getMethod());
        assertTrue(result.getReasoning().contains("despite a 1/4 vote split"),
                "Reasoning should be explicit that the count was overridden");
    }

    @Test
    @DisplayName("A zero-weight agent cannot change the outcome however confident it is")
    void zeroWeightAgentCannotSwingResult() {
        givenCalibratedWeights();

        ConsensusResult withoutNews = service.combine(1L, HOME, AWAY, List.of(
                prediction("Basic Predictor", HOME, 0.70)));
        ConsensusResult withNews = service.combine(1L, HOME, AWAY, List.of(
                prediction("Basic Predictor", HOME, 0.70),
                prediction("News Sentiment", AWAY, 0.90)));

        assertEquals(HOME, withoutNews.getWinner());
        assertEquals(HOME, withNews.getWinner());
        assertEquals(0.0, withNews.getWeightedScores().get(AWAY),
                "A zero weight must contribute exactly zero");
    }

    @Test
    @DisplayName("Confidence of exactly 0.50 contributes nothing - the inert-agent contract")
    void neutralConfidenceContributesNothing() {
        givenCalibratedWeights();

        // Market Odds with no market available returns 0.50 by contract
        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("Elo Ratings", AWAY, 0.65),
                prediction("Market Odds", HOME, 0.50)));

        assertEquals(AWAY, result.getWinner());
        assertEquals(0.0, result.getWeightedScores().get(HOME),
                "0.50 confidence scores zero, so it neither helps nor hurts");
    }

    @Test
    @DisplayName("Weighted score is weight x (confidence - 0.5)")
    void weightedScoreFormula() {
        givenCalibratedWeights();

        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("Market Odds", HOME, 0.80),
                prediction("Elo Ratings", AWAY, 0.70)));

        // 0.164 * 0.30 = 0.0492 ; 0.115 * 0.20 = 0.023
        assertEquals(0.0492, result.getWeightedScores().get(HOME), 1e-6);
        assertEquals(0.0230, result.getWeightedScores().get(AWAY), 1e-6);
        assertEquals(HOME, result.getWinner());
    }

    @Test
    @DisplayName("Unanimous agreement is reported as such")
    void unanimousAgreement() {
        givenCalibratedWeights();

        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("Market Odds", HOME, 0.75),
                prediction("Basic Predictor", HOME, 0.70),
                prediction("Elo Ratings", HOME, 0.65)));

        assertEquals(HOME, result.getWinner());
        assertEquals(3, result.getHomeVotes());
        assertTrue(result.getReasoning().startsWith("Unanimous: all 3 agents favor"));
    }

    @Test
    @DisplayName("When every agent carries the same weight, aggregate confidence decides")
    void equalWeightsMeanConfidenceDecides() {
        // No agent is in the table, so all fall back to the same default weight
        when(repository.findAll()).thenReturn(List.of());

        // 3-2 on the count for HOME, but the two AWAY agents are far more
        // confident: 0.02*(0.38+0.36) = 0.0148 against 0.02*(0.10+0.08+0.05) = 0.0046
        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("a1", HOME, 0.60),
                prediction("a2", HOME, 0.58),
                prediction("a3", HOME, 0.55),
                prediction("a4", AWAY, 0.88),
                prediction("a5", AWAY, 0.86)));

        assertEquals(3, result.getHomeVotes());
        assertEquals(2, result.getAwayVotes());
        assertEquals(AWAY, result.getWinner(),
                "Equal weights leave confidence to decide, and AWAY is far more confident");
        assertEquals("weighted", result.getMethod());
    }

    @Test
    @DisplayName("A 3-2 split with no weighted separation goes to the majority, not the loudest")
    void majorityFallbackRespectsThreeTwoSplit() {
        // Zero-weighted agents produce identical scores, forcing the fallback -
        // which is exactly the case the Python original got wrong. It only
        // handled N-0 and (N-1)-1 splits and fell through to "most confident
        // agent wins" for everything else, so a 3-2 returned the losing side.
        when(repository.findAll()).thenReturn(List.of(
                new AgentWeight("News Sentiment", 0.0, 0.497, "2021-2024", true)));

        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("News Sentiment", HOME, 0.60),
                prediction("News Sentiment", HOME, 0.58),
                prediction("News Sentiment", HOME, 0.55),
                prediction("News Sentiment", AWAY, 0.88),
                prediction("News Sentiment", AWAY, 0.86)));

        assertEquals(3, result.getHomeVotes());
        assertEquals(2, result.getAwayVotes());
        assertEquals(HOME, result.getWinner(),
                "The 3-vote majority must win even though AWAY is more confident");
        assertEquals("majority-fallback", result.getMethod());
    }

    @Test
    @DisplayName("A genuine dead heat falls back to the vote count")
    void deadHeatFallsBackToVoteCount() {
        // All agents zero-weighted, so no weighted separation is possible
        when(repository.findAll()).thenReturn(List.of(
                new AgentWeight("News Sentiment", 0.0, 0.497, "2021-2024", true)));

        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("News Sentiment", HOME, 0.80),
                prediction("News Sentiment", HOME, 0.70),
                prediction("News Sentiment", AWAY, 0.90)));

        assertEquals(HOME, result.getWinner(), "2-1 on votes when scores cannot separate");
        assertEquals("majority-fallback", result.getMethod());
        assertTrue(result.getReasoning().contains("No weighted separation"));
    }

    @Test
    @DisplayName("A tied vote with no separation goes to the most confident, discounted 10%")
    void tiedVoteBreaksOnConfidence() {
        when(repository.findAll()).thenReturn(List.of(
                new AgentWeight("News Sentiment", 0.0, 0.497, "2021-2024", true)));

        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("News Sentiment", HOME, 0.60),
                prediction("News Sentiment", AWAY, 0.80)));

        assertEquals(AWAY, result.getWinner());
        assertEquals(0.72, result.getConfidence(), 1e-6, "0.80 discounted by 10%");
        assertEquals("majority-fallback", result.getMethod());
    }

    @Test
    @DisplayName("An agent missing from the weight table gets the default, not zero and not one")
    void unknownAgentUsesDefaultWeight() {
        givenCalibratedWeights();

        // "Injury Impact" is deliberately absent from the seeded table
        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("Injury Impact", HOME, 0.75)));

        // 0.02 * 0.25 = 0.005
        assertEquals(0.005, result.getWeightedScores().get(HOME), 1e-6);
        assertEquals(HOME, result.getWinner());
    }

    @Test
    @DisplayName("A pick for neither listed team is ignored rather than counted")
    void unrecognisedPickIsIgnored() {
        givenCalibratedWeights();

        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("Basic Predictor", HOME, 0.70),
                prediction("Elo Ratings", "Denver Broncos", 0.95)));

        assertEquals(HOME, result.getWinner());
        assertEquals(1, result.getHomeVotes());
        assertEquals(0, result.getAwayVotes());
    }

    @Test
    @DisplayName("Confidence is capped at 0.90 and floored at 0.50")
    void confidenceStaysInRange() {
        givenCalibratedWeights();

        ConsensusResult lopsided = service.combine(1L, HOME, AWAY, List.of(
                prediction("Market Odds", HOME, 0.90)));

        assertTrue(lopsided.getConfidence() <= 0.90,
                "Confidence must never exceed 0.90, was " + lopsided.getConfidence());
        assertTrue(lopsided.getConfidence() >= 0.50,
                "Confidence must never fall below 0.50, was " + lopsided.getConfidence());
    }

    @Test
    @DisplayName("An empty prediction list is rejected rather than silently defaulting")
    void emptyPredictionsRejected() {
        assertThrows(IllegalArgumentException.class,
                () -> service.combine(1L, HOME, AWAY, List.of()));
        assertThrows(IllegalArgumentException.class,
                () -> service.combine(1L, HOME, AWAY, null));
    }

    @Test
    @DisplayName("A null confidence is treated as neutral, not as zero")
    void nullConfidenceTreatedAsNeutral() {
        givenCalibratedWeights();

        AgentPredictionDto missing = prediction("Market Odds", AWAY, 0.0);
        missing.setConfidence(null);

        ConsensusResult result = service.combine(1L, HOME, AWAY, List.of(
                prediction("Basic Predictor", HOME, 0.60),
                missing));

        assertEquals(HOME, result.getWinner());
        assertEquals(0.0, result.getWeightedScores().get(AWAY), 1e-6,
                "Null confidence must behave like 0.50 - contributing nothing");
    }

    @Test
    @DisplayName("Parity with the Python implementation on the same inputs")
    void matchesPythonConsensusOnSharedFixture() {
        givenCalibratedWeights();

        // The same seven-agent fixture used against agents/consensus.py:
        // Seahawks/Patriots, where Weather dissents and everything else agrees.
        ConsensusResult result = service.combine(1L, "Seattle Seahawks", "New England Patriots",
                List.of(
                        prediction("Basic Predictor", "Seattle Seahawks", 0.900),
                        prediction("Weather Impact", "New England Patriots", 0.550),
                        prediction("News Sentiment", "Seattle Seahawks", 0.510),
                        prediction("Market Odds", "Seattle Seahawks", 0.636),
                        prediction("Elo Ratings", "Seattle Seahawks", 0.726),
                        prediction("Rest & Travel", "Seattle Seahawks", 0.521),
                        prediction("Injury Impact", "Seattle Seahawks", 0.512)));

        assertEquals("Seattle Seahawks", result.getWinner());
        assertEquals(6, result.getHomeVotes());
        assertEquals(1, result.getAwayVotes());
        assertEquals("weighted", result.getMethod());
    }
}

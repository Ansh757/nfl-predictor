"""
Tests for the weighted vote.

consensus.py decides every prediction the service serves and is mirrored by
ConsensusService.java for live gateway traffic. The two can drift apart
silently, so the cases pinned here match backend/src/test/.../ConsensusServiceTest
one for one - if a change breaks one suite it should break the other.

These replaced the news-sentiment tests, which went when that agent was retired.
"""
import pytest

from agents.consensus import AGENT_WEIGHTS, DEFAULT_WEIGHT, build_consensus

HOME = "Kansas City Chiefs"
AWAY = "Buffalo Bills"


def pred(winner, confidence, reasoning="reasoning"):
    return {"winner": winner, "confidence": confidence, "reasoning": reasoning}


class TestWeightedVoting:

    def test_weight_beats_headcount(self):
        """Three near-zero-weight agents lose to one strong agent."""
        result = build_consensus(
            [pred(HOME, 0.80), pred(AWAY, 0.90), pred(AWAY, 0.70), pred(AWAY, 0.70)],
            ["Market Odds", "Injury Impact", "Rest & Travel", "Unknown Agent"],
            HOME, AWAY,
        )

        assert result["winner"] == HOME
        assert result["home_votes"] == 1
        assert result["away_votes"] == 3
        assert "despite a 1/4 vote split" in result["reasoning"]

    def test_weighted_score_formula(self):
        """Score is weight x (confidence - 0.5)."""
        result = build_consensus(
            [pred(HOME, 0.80), pred(AWAY, 0.70)],
            ["Market Odds", "Elo Ratings"],
            HOME, AWAY,
        )

        assert result["weighted_scores"][HOME] == pytest.approx(0.164 * 0.30, abs=1e-4)
        assert result["weighted_scores"][AWAY] == pytest.approx(0.116 * 0.20, abs=1e-4)
        assert result["winner"] == HOME

    def test_neutral_confidence_contributes_nothing(self):
        """0.50 is the 'no data' contract - it must not tilt the result."""
        result = build_consensus(
            [pred(AWAY, 0.65), pred(HOME, 0.50)],
            ["Elo Ratings", "Market Odds"],
            HOME, AWAY,
        )

        assert result["winner"] == AWAY
        assert result["weighted_scores"][HOME] == 0.0

    def test_unknown_agent_gets_default_weight(self):
        """A new agent must not arrive with full influence, nor with none."""
        result = build_consensus(
            [pred(HOME, 0.75)], ["Brand New Agent"], HOME, AWAY,
        )

        assert result["weighted_scores"][HOME] == pytest.approx(DEFAULT_WEIGHT * 0.25, abs=1e-5)
        assert result["winner"] == HOME

    def test_unanimous_is_reported(self):
        result = build_consensus(
            [pred(HOME, 0.75), pred(HOME, 0.70), pred(HOME, 0.65)],
            ["Market Odds", "Basic Predictor", "Elo Ratings"],
            HOME, AWAY,
        )

        assert result["winner"] == HOME
        assert result["reasoning"].startswith("Unanimous: all 3 agents favor")

    def test_pick_for_neither_team_is_ignored(self):
        result = build_consensus(
            [pred(HOME, 0.70), pred("Denver Broncos", 0.95)],
            ["Basic Predictor", "Elo Ratings"],
            HOME, AWAY,
        )

        assert result["winner"] == HOME
        assert result["home_votes"] == 1
        assert result["away_votes"] == 0

    def test_confidence_stays_in_range(self):
        result = build_consensus([pred(HOME, 0.90)], ["Market Odds"], HOME, AWAY)
        assert 0.50 <= result["confidence"] <= 0.90


class TestMajorityFallback:

    def test_three_two_split_respects_the_majority(self):
        """
        The bug this suite exists for.

        The original counter only handled N-0 and (N-1)-1 splits and fell through
        to "most confident agent wins" for anything else, so a 3-2 returned the
        losing side as soon as a fifth agent was added.
        """
        zero = {"Zero Weight": 0.0}
        result = build_consensus(
            [pred(HOME, 0.60), pred(HOME, 0.58), pred(HOME, 0.55),
             pred(AWAY, 0.88), pred(AWAY, 0.86)],
            ["Zero Weight"] * 5,
            HOME, AWAY, weights=zero,
        )

        assert result["home_votes"] == 3
        assert result["away_votes"] == 2
        assert result["winner"] == HOME, "The majority must win despite lower confidence"

    def test_tied_vote_breaks_on_confidence_discounted(self):
        zero = {"Zero Weight": 0.0}
        result = build_consensus(
            [pred(HOME, 0.60), pred(AWAY, 0.80)],
            ["Zero Weight"] * 2,
            HOME, AWAY, weights=zero,
        )

        assert result["winner"] == AWAY
        assert result["confidence"] == pytest.approx(0.80 * 0.9, abs=1e-4)

    def test_majority_method_ignores_weights_entirely(self):
        result = build_consensus(
            [pred(HOME, 0.51), pred(HOME, 0.52), pred(AWAY, 0.90)],
            ["Injury Impact", "Injury Impact", "Market Odds"],
            HOME, AWAY, method="majority",
        )

        assert result["winner"] == HOME, "One agent, one vote under the majority method"
        assert result["method"] == "majority"


class TestGuards:

    def test_empty_predictions_rejected(self):
        with pytest.raises(ValueError):
            build_consensus([], [], HOME, AWAY)

    def test_unknown_method_rejected(self):
        with pytest.raises(ValueError):
            build_consensus([pred(HOME, 0.6)], ["Market Odds"], HOME, AWAY, method="vibes")

    def test_retired_agents_carry_no_weight(self):
        """Weather and News were removed from the ensemble; nothing should re-add them."""
        assert "News Sentiment" not in AGENT_WEIGHTS
        assert "Weather Impact" not in AGENT_WEIGHTS

    def test_every_weight_is_non_negative(self):
        assert all(weight >= 0 for weight in AGENT_WEIGHTS.values())

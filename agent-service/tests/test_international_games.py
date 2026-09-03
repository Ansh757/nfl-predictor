"""
International-game handling.

Two flags, deliberately independent everywhere:

  neutral_site       - the designated home team is not at its own ground.
                       Controls home-field advantage. True for a Super Bowl,
                       which is domestic.
  international_game - the venue is outside the United States. Controls the
                       travel adjustment and the wording. Never inferred from
                       neutral_site, nor neutral_site from it.

Collapsing them would give a domestic Super Bowl international wording, or give
an international game home-field advantage. Both are asserted below.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.consensus import AGENT_WEIGHTS, build_consensus  # noqa: E402
from agents.elo_agent import EloRatingAgent  # noqa: E402
from agents.rest_travel_agent import (  # noqa: E402
    INTL_FAMILIARITY_BONUS, INTL_MAX_AGENT_EDGE, RestTravelAgent,
)
from utils.elo import DEFAULT_HOME_ADVANTAGE, NEUTRAL_SITE_ADVANTAGE, EloRatingSystem  # noqa: E402
from utils.venues import game_context  # noqa: E402


class Game:
    def __init__(self, home, away, venue, game_time="2026-10-18T13:30Z",
                 neutral_site=None, venue_country=None):
        self.game_id = 4242
        self.home_team_name = home
        self.away_team_name = away
        self.venue = venue
        self.game_time = game_time
        self.is_dome = False
        self.neutral_site = neutral_site
        self.venue_country = venue_country


def elo(game):
    return asyncio.run(EloRatingAgent("Elo Ratings").predict_game(game, {}))


def travel(game):
    return asyncio.run(RestTravelAgent("Rest & Travel").predict_game(game, {}))


class TestFlagsAreIndependent:
    def test_a_domestic_home_game_is_neither(self):
        context = game_context("Buffalo Bills", "Highmark Stadium")
        assert context["neutral_site"] is False
        assert context["international_game"] is False

    def test_a_domestic_neutral_site_is_neutral_but_not_international(self):
        # A Super Bowl. Home-field advantage goes, international wording does not
        # arrive.
        context = game_context("Kansas City Chiefs", "State Farm Stadium")
        assert context["neutral_site"] is True
        assert context["international_game"] is False

    def test_an_international_venue_is_both(self):
        context = game_context("Jacksonville Jaguars", "Wembley Stadium")
        assert context["neutral_site"] is True
        assert context["international_game"] is True
        assert context["venue_country"] == "England"
        assert context["venue_timezone"] == "Europe/London"

    def test_international_is_not_inferred_from_neutral(self):
        # ESPN says neutral, and says the country is the USA. That is a domestic
        # neutral game and must not acquire international handling.
        context = game_context("Chicago Bears", "Some Relocation Venue",
                               espn_neutral=True, espn_country="USA")
        assert context["neutral_site"] is True
        assert context["international_game"] is False

    def test_neutral_is_not_inferred_from_international(self):
        # Contrived, but the point is that the country alone never sets neutral.
        # Only the metadata or ESPN does.
        context = game_context("Chicago Bears", "Unknown Overseas Ground",
                               espn_neutral=False, espn_country="Canada")
        assert context["international_game"] is True
        assert context["neutral_site"] is False


class TestHomeFieldAdvantage:
    def test_a_domestic_game_keeps_the_normal_home_field_calculation(self):
        system = EloRatingSystem()
        assert system.expected_score(1500, 1500, neutral=False) == pytest.approx(
            1 / (1 + 10 ** (-DEFAULT_HOME_ADVANTAGE / 400)), abs=1e-9)

    def test_a_london_game_removes_it_entirely(self):
        system = EloRatingSystem()
        assert system.expected_score(1500, 1500, neutral=True) == pytest.approx(0.5, abs=1e-9)
        assert NEUTRAL_SITE_ADVANTAGE == 0.0

    def test_the_elo_agent_applies_it_by_venue(self):
        home = elo(Game("Jacksonville Jaguars", "Houston Texans", "EverBank Stadium"))
        away_venue = elo(Game("Jacksonville Jaguars", "Houston Texans", "Wembley Stadium"))
        # Same two teams, same ratings; only the venue differs.
        assert home["home_win_probability"] > away_venue["home_win_probability"]
        assert home["neutral_site"] is False
        assert away_venue["neutral_site"] is True

    def test_the_domestic_reasoning_never_mentions_international(self):
        for venue in ["EverBank Stadium", "State Farm Stadium"]:
            reasoning = elo(Game("Kansas City Chiefs", "Philadelphia Eagles", venue))["reasoning"]
            assert "International" not in reasoning
            assert "nternational" not in reasoning


class TestTravelDirectionAndDistance:
    def test_west_coast_to_london_is_penalised_more_than_east_coast(self):
        # Both fly east; Seattle crosses more time zones and more miles, so the
        # edge against it must be larger.
        west = travel(Game("New England Patriots", "Seattle Seahawks", "Wembley Stadium"))
        east = travel(Game("New England Patriots", "Miami Dolphins", "Wembley Stadium"))

        west_detail = west["international_detail"]
        east_detail = east["international_detail"]
        assert west_detail["away_timezones"] > east_detail["away_timezones"]
        assert west_detail["away_travel_miles"] > east_detail["away_travel_miles"]
        # Positive edge favours the home team, so the western visitor concedes more
        assert west_detail["applied_edge"] > east_detail["applied_edge"]

    def test_eastward_costs_more_than_westward(self):
        from agents.rest_travel_agent import INTL_TZ_EAST_PENALTY, INTL_TZ_WEST_PENALTY
        assert INTL_TZ_EAST_PENALTY > INTL_TZ_WEST_PENALTY

    def test_two_similarly_situated_teams_get_almost_nothing(self):
        # Houston and Jacksonville both fly to London from comparable zones.
        result = travel(Game("Jacksonville Jaguars", "Houston Texans", "Wembley Stadium"))
        assert abs(result["international_detail"]["applied_edge"]) <= 0.01
        assert "neither side gains a travel advantage" in result["reasoning"]


class TestTheCap:
    def test_the_agent_edge_is_clamped(self):
        # Fabricate the most lopsided journey the schedule could produce.
        result = travel(Game("New England Patriots", "Seattle Seahawks",
                             "Melbourne Cricket Ground"))
        assert abs(result["international_detail"]["applied_edge"]) <= INTL_MAX_AGENT_EDGE

    def test_the_cap_translates_to_under_1_5_points_of_final_probability(self):
        """
        The budget is defined at the ensemble level, so it has to be asserted
        there. Converting the agent's capped edge through its actual weight is
        what keeps the guarantee true if the weight is ever re-derived.
        """
        home, away = "Jacksonville Jaguars", "Houston Texans"
        names = ["Market Odds", "Basic Predictor", "Elo Ratings",
                 "Rest & Travel", "Injury Impact"]

        def ensemble(rest_confidence, rest_pick):
            predictions = [
                {"winner": home, "confidence": 0.58, "reasoning": ""},
                {"winner": home, "confidence": 0.60, "reasoning": ""},
                {"winner": home, "confidence": 0.62, "reasoning": ""},
                {"winner": rest_pick, "confidence": rest_confidence, "reasoning": ""},
                {"winner": home, "confidence": 0.50, "reasoning": ""},
            ]
            return build_consensus(predictions, names, home, away)["confidence"]

        # The agent's confidence is 0.50 + |edge| * 2.0, so the cap maps to this
        neutral_conf = 0.50
        capped_conf = min(0.70, 0.50 + INTL_MAX_AGENT_EDGE * 2.0)

        baseline = ensemble(neutral_conf, home)
        most_favourable = ensemble(capped_conf, home)
        most_adverse = ensemble(capped_conf, away)

        assert abs(most_favourable - baseline) <= 0.015, "international effect exceeds 1.5 points"
        assert abs(most_adverse - baseline) <= 0.015, "international effect exceeds 1.5 points"
        assert AGENT_WEIGHTS["Rest & Travel"] < 0.05, "cap assumes a small weight"

    def test_familiarity_is_off_until_it_is_measured(self):
        # 24 historical games give z = 0.44. Shipping a non-zero number here
        # would dress noise up as a finding.
        assert INTL_FAMILIARITY_BONUS == 0.0


class TestFailsSafe:
    def test_missing_metadata_does_not_invent_an_international_game(self):
        context = game_context("Buffalo Bills", "Some Unlisted Stadium")
        assert context["international_game"] is False
        assert context["neutral_site"] is False

    def test_a_missing_venue_is_a_normal_home_game(self):
        context = game_context("Buffalo Bills", None)
        assert context["international_game"] is False
        assert context["neutral_site"] is False

    def test_a_renamed_home_stadium_keeps_home_field(self):
        # The dangerous inference is "not their listed stadium, so they are away".
        # A sponsor rename would otherwise strip home-field advantage from every
        # home game that team plays.
        context = game_context("Kansas City Chiefs", "GEHA Field at Arrowhead Stadium")
        assert context["neutral_site"] is False

    def test_a_domestic_game_produces_no_international_payload(self):
        result = travel(Game("Buffalo Bills", "Miami Dolphins", "Highmark Stadium"))
        assert result["international_game"] is False
        assert result["international_detail"] is None
        assert "nternational" not in result["reasoning"]

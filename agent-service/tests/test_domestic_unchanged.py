"""
Domestic games must be untouched.

The international work is additive by construction, but "by construction" is a
claim, not evidence. This compares a full slate of ordinary domestic games
against output captured from the code as it behaved before any of it - so a
regression shows up as a diff rather than as a plausible-looking number.
"""
import asyncio
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.elo_agent import EloRatingAgent  # noqa: E402
from agents.rest_travel_agent import RestTravelAgent  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "domestic_golden.json")


class Game:
    def __init__(self, game_id, home, away, venue, game_time):
        self.game_id = game_id
        self.home_team_name = home
        self.away_team_name = away
        self.venue = venue
        self.game_time = game_time
        self.is_dome = False
        self.neutral_site = None
        self.venue_country = None


def domestic_slate(limit=40):
    """A fixed slate of ordinary home games, oldest first for determinism."""
    conn = sqlite3.connect(os.path.join(ROOT, "nfl_schedule.db"))
    rows = conn.execute("""
        SELECT game_id, home_team, away_team, venue, game_date
        FROM games
        WHERE season = 2024 AND season_type = 'regular'
          AND COALESCE(neutral_site, 0) = 0
          AND venue IS NOT NULL
        ORDER BY game_date, game_id
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [Game(*row) for row in rows]


def fingerprint():
    """The parts of each agent's output a user would actually see."""
    elo_agent = EloRatingAgent("Elo Ratings")
    travel_agent = RestTravelAgent("Rest & Travel")
    out = {}
    for game in domestic_slate():
        elo = asyncio.run(elo_agent.predict_game(game, {}))
        travel = asyncio.run(travel_agent.predict_game(game, {}))
        out[str(game.game_id)] = {
            "elo_winner": elo["winner"],
            "elo_confidence": elo["confidence"],
            "elo_home_win_probability": elo["home_win_probability"],
            "elo_reasoning": elo["reasoning"],
            "travel_winner": travel["winner"],
            "travel_confidence": travel["confidence"],
            "travel_miles": travel["travel_miles"],
            "travel_reasoning": travel["reasoning"],
        }
    return out


# Captured from the code as it stood before any international work, so these
# comparisons are against real prior behaviour rather than against the new code
# describing itself.
BASELINE_NOTE = "pre-international-games baseline"

# Correcting historical neutral-site Elo necessarily moves ratings: a team that
# played in London in 2022 carries a slightly different rating into every later
# game. Domestic *logic* is untouched, but domestic *numbers* shift a little as
# a result, so byte-identity is asserted where it is genuinely expected and
# bounded drift where it is not.
MAX_ELO_DRIFT = 0.01     # one point of win probability


@pytest.mark.skipif(not os.path.exists(GOLDEN), reason="golden file not generated")
class TestDomesticIsUnchanged:

    @pytest.fixture(scope="class")
    def comparison(self):
        with open(GOLDEN) as handle:
            expected = json.load(handle)
        return expected, fingerprint()

    def test_rest_and_travel_is_byte_identical(self, comparison):
        """
        Strict. Travel depends on venues and the calendar, not on ratings, so
        there is no legitimate reason for a single domestic value to move.
        """
        expected, actual = comparison
        fields = ["travel_winner", "travel_confidence", "travel_miles", "travel_reasoning"]
        differences = {
            game_id: {field: (expected[game_id][field], actual[game_id][field])
                      for field in fields if expected[game_id][field] != actual[game_id][field]}
            for game_id in actual
            if any(expected[game_id][field] != actual[game_id][field] for field in fields)
        }
        assert not differences, f"domestic travel output changed: {differences}"

    def test_no_domestic_game_loses_home_field_advantage(self, comparison):
        _, actual = comparison
        for game_id, fields in actual.items():
            assert "Home field is worth 65 Elo points" in fields["elo_reasoning"], game_id

    def test_no_domestic_game_gains_international_wording(self, comparison):
        _, actual = comparison
        for game_id, fields in actual.items():
            assert "nternational" not in fields["elo_reasoning"], game_id
            assert "nternational" not in fields["travel_reasoning"], game_id
            assert "eutral site" not in fields["elo_reasoning"], game_id

    def test_no_domestic_prediction_changes_side(self, comparison):
        expected, actual = comparison
        flips = [game_id for game_id in actual
                 if expected[game_id]["elo_winner"] != actual[game_id]["elo_winner"]]
        assert not flips, f"the corrected ratings flipped a domestic pick: {flips}"

    def test_elo_drift_is_small_and_attributable(self, comparison):
        """
        The only permitted domestic change: ratings corrected upstream, because
        neutral-site games no longer credit a home advantage that did not exist.
        Bounded so a genuine regression cannot hide inside it.
        """
        expected, actual = comparison
        drifts = {game_id: abs(actual[game_id]["elo_home_win_probability"]
                               - expected[game_id]["elo_home_win_probability"])
                  for game_id in actual}
        worst = max(drifts.values())
        assert worst <= MAX_ELO_DRIFT, (
            f"domestic Elo moved by {worst*100:.2f} points, beyond what the "
            f"neutral-site correction explains")


def test_the_slate_is_actually_domestic():
    # If this ever picks up a neutral-site game the comparison above stops
    # testing what it claims to.
    conn = sqlite3.connect(os.path.join(ROOT, "nfl_schedule.db"))
    ids = [game.game_id for game in domestic_slate()]
    placeholders = ",".join("?" * len(ids))
    neutral = conn.execute(
        f"SELECT COUNT(*) FROM games WHERE game_id IN ({placeholders}) AND neutral_site = 1",
        ids).fetchone()[0]
    conn.close()
    assert neutral == 0
    assert len(ids) == 40

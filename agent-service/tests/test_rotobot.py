"""
Rotobot's score model: anchored to the market, honest about its spread.

The properties pinned here are the ones a reader relies on - the expected score
is the market's, a stronger favourite wins more often, the ranges mean what
they say - plus the order in which a line is chosen when the market is missing.
"""
import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotobot import live  # noqa: E402
from rotobot import score as rs  # noqa: E402
from utils.odds_client import OddsClient  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestScoreModel:
    @pytest.mark.parametrize("spread,total", [(-3.5, 47.5), (7.0, 41.0), (-13.5, 52.5), (0.0, 44.0)])
    def test_expected_points_are_the_markets(self, spread, total):
        line = rs.GameLine(spread, total)
        dist = rs.simulate(line)
        assert rs.expected_points(dist.marginal("home")) == pytest.approx(line.home_points, abs=0.3)
        assert rs.expected_points(dist.marginal("away")) == pytest.approx(line.away_points, abs=0.3)

    def test_it_is_a_distribution(self):
        assert sum(rs.simulate(rs.GameLine(-3.5, 47.5)).joint.values()) == pytest.approx(1.0)

    def test_a_pick_em_is_a_coin_flip(self):
        p = rs.summarize(rs.simulate(rs.GameLine(0.0, 44.0)), rs.GameLine(0.0, 44.0))["probabilities"]
        assert p["home_win"] == pytest.approx(p["away_win"], abs=1e-6)

    def test_a_bigger_favourite_wins_more_often(self):
        probs = [rs.summarize(rs.simulate(rs.GameLine(s, 44.0)), rs.GameLine(s, 44.0))["probabilities"]["home_win"]
                 for s in (-1.0, -3.0, -7.0, -14.0)]
        assert probs == sorted(probs)

    def test_scores_are_football_scores(self):
        # Built from 3s and 7s. In real games 2021-2024 a team scored 20 7.5% of
        # the time, 19 3.2% and 18 1.1%; the model gives 7.3%, 3.2% and 0.3%.
        home = rs.simulate(rs.GameLine(0.0, 40.0)).marginal("home")
        assert home[17] > 3 * home[18]
        assert home[20] > 2 * home[19] > home[18]

    def test_ties_are_rare_but_possible(self):
        p = rs.summarize(rs.simulate(rs.GameLine(0.0, 44.0)), rs.GameLine(0.0, 44.0))["probabilities"]
        assert 0.0 < p["tie"] < 0.01

    def test_win_probability_round_trips_through_a_spread(self):
        assert rs.spread_from_win_probability(0.5) == pytest.approx(0.0, abs=0.1)
        assert rs.spread_from_win_probability(0.7) < -5      # home favoured by about 6.6


class TestOdds:
    def test_live_feed_reads_the_total(self):
        event = {
            "home_team": "Buffalo Bills", "away_team": "Los Angeles Rams",
            "bookmakers": [{"markets": [
                {"key": "h2h", "outcomes": [{"name": "Buffalo Bills", "price": -170},
                                            {"name": "Los Angeles Rams", "price": 145}]},
                {"key": "spreads", "outcomes": [{"name": "Buffalo Bills", "point": -3.5}]},
                {"key": "totals", "outcomes": [{"name": "Over", "point": 47.5},
                                               {"name": "Under", "point": 47.5}]},
            ]}],
        }
        parsed = OddsClient(api_key="test")._parse_event(event)
        assert parsed["total"] == 47.5
        assert parsed["home_spread"] == -3.5


class FakeOdds:
    def __init__(self, market=None, enabled=True):
        self.market, self.enabled = market, enabled

    async def get_game_odds(self, home, away):
        return self.market


class FakeElo:
    async def predict_game(self, game_data, context):
        return {"home_win_probability": 0.70}


class FakeClosing:
    def __init__(self, line):
        self.line = line

    def get(self, season, home, away):
        return self.line


GAME = {"game_id": 1, "season": 2026, "home_team": "Buffalo Bills", "away_team": "Los Angeles Rams",
        "home_score": None, "away_score": None}
PLAYED = {**GAME, "home_score": 34, "away_score": 37}


def _resolve(monkeypatch, market=None, closing=None, game=GAME):
    monkeypatch.setattr(live, "_historical", FakeClosing(closing))
    return asyncio.run(live.resolve_line(game, FakeOdds(market), FakeElo()))


class TestLineSource:
    def test_live_market_first(self, monkeypatch):
        line, source = _resolve(monkeypatch, market={"home_spread": -3.5, "total": 47.5},
                                closing={"home_spread": -1.0, "total": 40.0})
        assert (line.home_spread, line.total) == (-3.5, 47.5)
        assert source == {"spread": "live_market", "total": "live_market"}

    def test_closing_line_fills_only_what_the_market_lacks(self, monkeypatch):
        line, source = _resolve(monkeypatch, market={"home_spread": -3.5, "total": None},
                                closing={"home_spread": -1.0, "total": 40.0})
        assert (line.home_spread, line.total) == (-3.5, 40.0)
        # Not played yet, so nflverse's line is current, not closing
        assert source == {"spread": "live_market", "total": "nflverse_line"}

    def test_a_played_game_uses_its_closing_line(self, monkeypatch):
        line, source = _resolve(monkeypatch, market=None, closing={"home_spread": -6.0, "total": 43.5},
                                game=PLAYED)
        assert (line.home_spread, line.total) == (-6.0, 43.5)
        assert source == {"spread": "closing_line", "total": "closing_line"}

    def test_no_market_at_all_is_labelled_as_a_fallback(self, monkeypatch):
        line, source = _resolve(monkeypatch, market=None, closing=None)
        assert line.home_spread < 0                       # Elo has the home side at 70%
        assert line.total == rs.LEAGUE_AVERAGE_TOTAL
        assert source == {"spread": "elo_fallback", "total": "league_average"}


class TestEndpoint:
    @pytest.fixture
    def client(self):
        from main import app
        return TestClient(app)

    def test_unknown_game_is_a_404(self, client):
        assert client.get("/games/99999999/rotobot").status_code == 404

    def test_a_played_game_reports_its_anchor_and_result(self, client, monkeypatch):
        import main
        import sqlite3
        conn = sqlite3.connect(os.path.join(ROOT, "nfl_schedule.db"))
        game_id = conn.execute(
            "SELECT game_id FROM games WHERE season = 2025 AND season_type = 'regular' "
            "AND home_score IS NOT NULL LIMIT 1").fetchone()[0]
        conn.close()
        monkeypatch.setattr(main.market_agent, "client", FakeOdds(enabled=False))
        monkeypatch.setattr(live, "_historical", FakeClosing({"home_spread": -3.0, "total": 45.0}))

        body = client.get(f"/games/{game_id}/rotobot").json()

        assert body["source"] == {"spread": "closing_line", "total": "closing_line"}
        assert body["anchor"]["home_implied_points"] == 24.0
        assert body["final"] is not None
        assert body["interval"]["level"] == 0.8


@pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "historical_odds.csv")),
                    reason="nflverse closing lines not downloaded")
def test_held_out_2025_ranges_mean_what_they_say():
    """The calibrated 80% range must hold the real score ~80% of the time on a
    season the parameters never saw."""
    from backtest_rotobot import load_games
    games = load_games([2025])
    hits = 0
    for g in games:
        line = rs.GameLine(g["home_spread"], g["total"])
        iv = rs.summarize(rs.simulate(line), line)["interval"]
        hits += iv["total"][0] <= g["home_score"] + g["away_score"] <= iv["total"][1]
    assert 0.75 <= hits / len(games) <= 0.85

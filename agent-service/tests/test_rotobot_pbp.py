"""
The play-by-play engine: properties every simulated game must satisfy.

Each test plays many random games and checks something that must hold in all of
them - a box score that adds up, a clock that ends, overtime by the rules - plus
the service rules around it: same inputs, same answer; changed inputs, a new
run; and the CPU-heavy precompute endpoint closed to anyone without the token.
"""
import json
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotobot.pbp.engine import (ATT, INT, PASSTD, PASSYD, RECTD, RECYD, RUSHTD, RUSHYD, Game,  # noqa: E402
                                Role, Side)
from rotobot.pbp import service  # noqa: E402
from rotobot.pbp.simulate import calibrate, ppr, roles_from_projection, simulate  # noqa: E402
from rotobot.score import GameLine  # noqa: E402

MODEL = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "rotobot", "pbp", "league_model.json")))


def _sides():
    home = Side("HOM", qb="qb_h", roles=[
        Role("wr_h", target=0.3), Role("te_h", target=0.18), Role("rb_h", target=0.1, carry=0.65, goal_line=0.7)])
    away = Side("AWY", qb="qb_a", roles=[Role("wr_a", target=0.35), Role("rb_a", target=0.08, carry=0.7, goal_line=0.6)])
    return home, away


def _games(n=300, seed=1):
    rng = random.Random(seed)
    for _ in range(n):
        home, away = _sides()
        game = Game(MODEL, home, away, rng)
        box, players = game.play()
        yield game, box, players


def test_every_game_ends():
    for game, box, _ in _games(500):
        assert game.clock <= 0 or game.overtime


def test_a_box_score_adds_up():
    """A receiver's touchdown is his quarterback's touchdown and his team's six points."""
    for _, box, players in _games(300):
        for i, team in enumerate(players):
            qb = team.get("qb_h" if i == 0 else "qb_a")
            catchers = [s for pid, s in team.items() if not pid.startswith("qb")]
            # Named receivers can account for no more than the quarterback threw
            assert sum(s[RECYD] for s in catchers) <= qb[PASSYD] + 1e-9
            assert sum(s[RECTD] for s in catchers) <= qb[PASSTD]
            assert qb[PASSTD] == box[i]["pass_td"]
            assert qb[PASSYD] == box[i]["pass_yds"]
            assert qb[INT] == box[i]["int"]
            assert qb[ATT] == box[i]["pass_att"]
            # Rushing is shared with 'someone else', so named rushers stay within the team total
            assert sum(s[RUSHTD] for s in team.values()) <= box[i]["rush_td"]
            # Points are built from scores, never anything else
            touchdowns = box[i]["td"]
            assert box[i]["points"] >= 6 * touchdowns


def test_ties_are_rare_and_overtime_follows_the_rules():
    games = list(_games(2000, seed=7))
    overtime = [b for g, b, _ in games if g.overtime]
    ties = [b for b in overtime if b[0]["points"] == b[1]["points"]]
    assert 0.03 < len(overtime) / len(games) < 0.12
    assert len(ties) / len(games) < 0.01
    for g, b, _ in games:
        if g.overtime and b[0]["points"] != b[1]["points"]:
            # A decided overtime means both teams had the ball
            assert min(g.ot_completed) >= 1


def test_the_same_seed_gives_the_same_game():
    home, away = _sides()
    a = Game(MODEL, home, away, random.Random(42)).play()[0]
    home, away = _sides()
    b = Game(MODEL, home, away, random.Random(42)).play()[0]
    assert a == b


def test_calibration_hits_the_markets_points():
    home, away = _sides()
    calibrate(MODEL, home, away, 27.5, 17.0, seed=3)
    result = simulate(MODEL, home, away, seed=3, runs=2000)
    assert result["mean"]["home"] == pytest.approx(27.5, abs=1.5)
    assert result["mean"]["away"] == pytest.approx(17.0, abs=1.5)
    assert result["probabilities"]["home_win"] > 0.7


def test_a_quarterback_and_his_receiver_move_together():
    home, away = _sides()
    result = simulate(MODEL, home, away, seed=5, runs=2000)
    wr = next(p for p in result["players"] if p["player_id"] == "wr_h")
    rb_opp = next(p for p in result["players"] if p["player_id"] == "rb_a")
    assert wr["correlation"]["own_qb"] > 0.2
    # Nothing ties a running back to the other team's quarterback but the game itself
    assert abs(rb_opp["correlation"]["opposing_qb"] or 0) < 0.25
    stack = next(s for s in result["stacks"] if s["player_id"] == "wr_h")
    assert stack["both_above_median"] > 0.25            # more than if their games were unrelated


def test_ranges_bracket_the_median():
    home, away = _sides()
    result = simulate(MODEL, home, away, seed=9, runs=1000)
    for p in result["players"]:
        assert p["ppr"]["p10"] <= p["ppr"]["p50"] <= p["ppr"]["p90"]
    iv = result["interval"]
    assert iv["home"][0] <= result["median"]["home"] <= iv["home"][1]


def test_ppr_scoring_of_a_simulated_line():
    line = [0.0] * 12
    line[RECYD], line[RECTD], line[1] = 80, 1, 6       # 1 = receptions
    assert ppr(line) == pytest.approx(8 + 6 + 6)


def test_roles_come_from_the_projection():
    players = [
        {"player_id": "q", "position": "QB", "starter": True,
         "stats": {"targets": 0, "receptions": 0, "receiving_yards": 0, "carries": 4, "rushing_yards": 20, "rushing_tds": 0.2}},
        {"player_id": "w", "position": "WR", "starter": None,
         "stats": {"targets": 9, "receptions": 6, "receiving_yards": 80, "carries": 0, "rushing_yards": 0, "rushing_tds": 0}},
    ]
    line = {"targets": 30, "carries": 25, "completions": 20, "passing_yards": 230, "rushing_yards": 110}
    qb, roles, positions = roles_from_projection(players, line)
    assert qb == "q"
    w = next(r for r in roles if r.player_id == "w")
    assert w.target == pytest.approx(0.3)
    assert positions == {"q": "QB", "w": "WR"}
    # Half a quarterback's carries are scrambles, which pass plays already give him
    assert next(r for r in roles if r.player_id == "q").carry == pytest.approx(2 / 25)


class TestService:
    GAME = {"game_id": 1, "home_team": "Buffalo Bills", "away_team": "Los Angeles Rams"}
    PLAYERS = {"home": {"out": [], "players": [{"player_id": "a", "stats": {"targets": 8.0, "carries": 0.0}}]},
               "away": {"out": [], "players": []}}

    def test_the_fingerprint_changes_when_an_input_does(self):
        base = service.fingerprint(self.GAME, GameLine(-3.5, 47.5), self.PLAYERS)
        assert base == service.fingerprint(self.GAME, GameLine(-3.5, 47.5), self.PLAYERS)
        assert base != service.fingerprint(self.GAME, GameLine(-4.5, 47.5), self.PLAYERS)
        injured = {**self.PLAYERS, "home": {**self.PLAYERS["home"], "out": ["Josh Allen"]}}
        assert base != service.fingerprint(self.GAME, GameLine(-3.5, 47.5), injured)


class TestPrecompute:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_fails_closed_without_a_configured_token(self, client, monkeypatch):
        monkeypatch.delenv("ROTOBOT_TOKEN", raising=False)
        assert client.post("/rotobot/precompute?season=2026&week=10").status_code == 503

    def test_rejects_the_wrong_token(self, client, monkeypatch):
        monkeypatch.setenv("ROTOBOT_TOKEN", "right")
        response = client.post("/rotobot/precompute?season=2026&week=10", headers={"X-Rotobot-Token": "wrong"})
        assert response.status_code == 401

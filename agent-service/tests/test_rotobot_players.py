"""
Rotobot's player layer: the rules a reader would notice breaking.

Built on a small hand-made league so the rules are tested without downloading
anything: player lines add up to the team's, an Out player's share goes to his
teammates, a backup QB starts when the starter is out, and a player who has
since moved teams is not projected for his old one.
"""
import asyncio
import os
import sys
from collections import defaultdict

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotobot import live_players  # noqa: E402
from rotobot import players as rp  # noqa: E402
from rotobot.player_data import NUMERIC, TEAM_SUMS, PlayerStats, fantasy_points  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _row(pid, name, pos, **stats):
    row = {k: 0.0 for k in NUMERIC}
    row.update(stats)
    row.update(player_id=pid, name=name, position=pos, headshot=None)
    return row


def _league() -> PlayerStats:
    """Team AAA plays weeks 1-3 against BBB; WR1 gets half the targets, WR2 a third."""
    ps = PlayerStats.__new__(PlayerStats)
    ps.player_games = defaultdict(list)
    ps.team_totals, ps.opponent, ps.game_id = {}, {}, {}
    ps.team_schedule, ps.season_type = defaultdict(list), {}
    for week in (1, 2, 3):
        ps.player_games[(2026, week, "AAA")] = [
            _row("qb1", "Starter Quarterback", "QB", attempts=30, completions=20, passing_yards=240, passing_tds=2),
            _row("wr1", "Lead Receiver", "WR", targets=12, receptions=8, receiving_yards=110, receiving_tds=1),
            _row("wr2", "Second Receiver", "WR", targets=8, receptions=5, receiving_yards=60),
            _row("te1", "Tight End", "TE", targets=4, receptions=3, receiving_yards=30, receiving_tds=1),
            _row("rb1", "Lead Back", "RB", carries=20, rushing_yards=90, rushing_tds=1),
        ]
        if week == 3:
            ps.player_games[(2026, week, "AAA")].append(
                _row("qb2", "Backup Quarterback", "QB", attempts=2, completions=1, passing_yards=8))
        ps.player_games[(2026, week, "BBB")] = [_row("bqb", "Other QB", "QB", attempts=30, passing_yards=200)]
        ps.opponent[(2026, week, "AAA")], ps.opponent[(2026, week, "BBB")] = "BBB", "AAA"
        ps.season_type[(2026, week)] = "REG"
    for key, rows in ps.player_games.items():
        ps.team_totals[key] = {s: sum(r[s] for r in rows) for s in TEAM_SUMS}
        ps.team_schedule[key[2]].append((key[0], key[1]))
    return ps


MODEL = {
    "league": {s: 20.0 for s in rp.TEAM_STATS},
    "position_rates": {p: {"ypt": 8.0, "catch": 0.65, "rec_td": 0.05, "ypc": 4.3,
                           "rush_td": 0.03, "fumble": 0.005} for p in ("QB", "RB", "FB", "WR", "TE")},
    # Team line = the team's recent average, so the arithmetic is easy to follow
    "team": {s: [0.0, 1.0, 0.0, 0.0, 0.0] for s in rp.TEAM_STATS},
    "ranges": {p: {"ppr": [-1.5, 2.0]} for p in ("QB", "RB", "WR", "TE")},
}
TEAM_LINE = {"attempts": 32.0, "completions": 21.0, "passing_yards": 250.0, "passing_tds": 2.0,
             "passing_interceptions": 1.0, "carries": 25.0, "rushing_yards": 110.0,
             "rushing_tds": 1.0, "targets": 30.0}


def _project(ps, out=()):
    return {p["player_id"]: p for p in rp.project_players(
        ps, MODEL, rp.player_index(ps), "AAA", 2026, 4, TEAM_LINE, set(out))}


def test_player_lines_add_up_to_the_team():
    players = _project(_league())
    total = lambda stat: sum(p["stats"][stat] for p in players.values())
    assert total("receiving_yards") == pytest.approx(TEAM_LINE["passing_yards"])
    assert total("receiving_tds") == pytest.approx(TEAM_LINE["passing_tds"])
    assert total("rushing_yards") == pytest.approx(TEAM_LINE["rushing_yards"])
    assert total("targets") == pytest.approx(TEAM_LINE["targets"])


def test_the_starter_takes_the_passing_line_and_the_backup_is_left_out():
    players = _project(_league())
    assert players["qb1"]["stats"]["passing_yards"] == TEAM_LINE["passing_yards"]
    assert players["qb1"]["starter"] is True
    assert "qb2" not in players


def test_an_out_starter_hands_the_offence_to_the_backup():
    players = _project(_league(), out={"qb1"})
    assert "qb1" not in players
    assert players["qb2"]["stats"]["passing_yards"] == TEAM_LINE["passing_yards"]


def test_an_out_receiver_shares_go_to_his_teammates():
    before, after = _project(_league()), _project(_league(), out={"wr1"})
    assert "wr1" not in after
    assert after["wr2"]["stats"]["targets"] > before["wr2"]["stats"]["targets"]
    assert after["te1"]["stats"]["targets"] > before["te1"]["stats"]["targets"]
    # Nothing disappears with him
    assert sum(p["stats"]["targets"] for p in after.values()) == pytest.approx(TEAM_LINE["targets"])


def test_a_player_who_moved_teams_is_not_projected_for_his_old_one():
    ps = _league()
    ps.player_games[(2026, 3, "BBB")].append(_row("wr1", "Lead Receiver", "WR", targets=6))
    ps.team_totals[(2026, 3, "BBB")] = {s: sum(r[s] for r in ps.player_games[(2026, 3, "BBB")]) for s in TEAM_SUMS}
    assert "wr1" not in _project(ps)


def test_the_weekly_roster_removes_a_player_who_has_left():
    # Played for AAA last week, absent from this week's roster: offseason
    # departure or injured reserve, which no injury report would show
    ps = _league()
    index = rp.player_index(ps)
    roster = {"qb1", "qb2", "wr2", "te1", "rb1"}
    players = rp.project_players(ps, MODEL, index, "AAA", 2026, 4, TEAM_LINE, set(), roster)
    assert "wr1" not in {p["player_id"] for p in players}


def test_a_missing_players_share_is_only_partly_handed_on():
    """Most of a departed player's share goes to players the model cannot name -
    rookies, signings - so the ones still projected must not absorb all of it."""
    ps = _league()
    index = rp.player_index(ps)
    full = {p["player_id"]: p for p in rp.project_players(
        ps, {**MODEL, "redistribute": 1.0}, index, "AAA", 2026, 4, TEAM_LINE, {"wr1"})}
    partial = {p["player_id"]: p for p in rp.project_players(
        ps, {**MODEL, "redistribute": 0.25}, index, "AAA", 2026, 4, TEAM_LINE, {"wr1"})}
    assert partial["wr2"]["stats"]["targets"] < full["wr2"]["stats"]["targets"]
    # The unassigned remainder is real: projected targets fall short of the team's
    assert sum(p["stats"]["targets"] for p in partial.values()) < TEAM_LINE["targets"]


def test_the_bigger_role_projects_more_points():
    players = _project(_league())
    assert players["wr1"]["fantasy"]["ppr"] > players["wr2"]["fantasy"]["ppr"]


def test_ranges_bracket_the_projection():
    p = rp.with_ranges(list(_project(_league()).values()), MODEL)[0]
    lo, hi = p["ranges"]["ppr"]
    assert lo <= p["fantasy"]["ppr"] <= hi


def test_ppr_scoring():
    stats = {"receptions": 5, "receiving_yards": 80, "receiving_tds": 1, "rushing_yards": 10}
    assert fantasy_points(stats) == pytest.approx(5 + 8 + 6 + 1)
    assert fantasy_points(stats, ppr=0.0) == pytest.approx(8 + 6 + 1)


class TestLive:
    @pytest.mark.parametrize("espn,nflverse", [
        ("Kenneth Walker III", "Kenneth Walker"),
        ("D.J. Moore", "DJ Moore"),
        ("Amon-Ra St. Brown", "Amon-Ra St Brown"),
        ("Marvin Harrison Jr.", "Marvin Harrison"),
    ])
    def test_names_match_across_sources(self, espn, nflverse):
        assert live_players.normalise_name(espn) == live_players.normalise_name(nflverse)

    def test_playoff_weeks_continue_from_the_regular_season(self):
        assert live_players.nflverse_week({"season_type": "playoffs", "week": 1}) == 19
        assert live_players.nflverse_week({"season_type": "regular", "week": 7}) == 7

    def test_every_team_has_a_current_code(self):
        assert len(live_players.ABBREVIATION) == 32
        assert live_players.ABBREVIATION["Los Angeles Rams"] == "LA"

    def test_live_out_list_removes_injured_reserve(self):
        ps = _league()

        class Injuries:
            async def get_team_injuries(self, team):
                return [{"player": "Lead Receiver", "status": "Injured Reserve", "position": "WR"},
                        {"player": "Tight End", "status": "Questionable", "position": "TE"},
                        {"player": "Some Guard", "status": "Out", "position": "G"}]

        result = asyncio.run(live_players._out_ids(
            {"home_score": None}, "AAA", "Team A", ps, rp.player_index(ps), 2026, 4, Injuries()))
        assert result["ids"] == {"wr1"}          # questionable plays; IR does not
        assert result["names"] == ["Lead Receiver"]   # the guard is out, but not a fantasy name
        assert result["source"] == "espn_live"


def test_a_player_failure_does_not_take_the_score_down(monkeypatch):
    import main
    import sqlite3
    from fastapi.testclient import TestClient
    from rotobot import live

    class NoMarket:
        enabled = False

    class Closing:
        def get(self, *args):
            return {"home_spread": -3.0, "total": 45.0}

    async def broken(*args, **kwargs):
        raise RuntimeError("stats download failed")

    conn = sqlite3.connect(os.path.join(ROOT, "nfl_schedule.db"))
    game_id = conn.execute("SELECT game_id FROM games WHERE season = 2025 AND season_type = 'regular' "
                           "AND home_score IS NOT NULL LIMIT 1").fetchone()[0]
    conn.close()
    monkeypatch.setattr(main.market_agent, "client", NoMarket())
    monkeypatch.setattr(live, "_historical", Closing())
    monkeypatch.setattr(main, "rotobot_project_players", broken)

    body = TestClient(main.app).get(f"/games/{game_id}/rotobot").json()
    assert body["median"]["home"] > 0
    assert body["players"] == {"available": False, "reason": "Player projections unavailable."}


@pytest.mark.skipif(not all(os.path.exists(os.path.join(ROOT, f"stats_player_week_{y}.csv"))
                            for y in range(2020, 2027)),
                    reason="nflverse player stats not downloaded")
def test_held_out_2025_beats_the_season_average(monkeypatch, capsys):
    """The reason the player layer exists. If a change makes projections worse
    than each player's season average on a season the model never saw, it is
    not an improvement, whatever else it does."""
    monkeypatch.chdir(ROOT)
    import backtest_rotobot_players as bt
    summary = bt.evaluate(bt.Context(), rp.load_model(), 2025)
    for pos, result in summary.items():
        assert result["model"] < result["season"], pos
        assert 0.72 <= result["coverage"] <= 0.88, pos

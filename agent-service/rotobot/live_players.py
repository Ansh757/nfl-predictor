"""
live_players.py - Rotobot's player projections for one game, as served.

Player history comes from the nflverse weekly stats for this season and last
(downloaded on demand, refreshed every 12 hours for the season in progress).
Who can play comes from that week's nflverse roster when it has been published
(see rosters.py) - it removes offseason departures and injured reserve. Who is
out depends on whether the game has been played:

  * upcoming: ESPN's live injury report - Out, Doubtful, Injured Reserve and
    Suspension all remove a player. The live feed carries injured reserve,
    which the historical reports do not, so live projections avoid the
    backtest's biggest blind spot (a starter moved to IR during the week).
  * played: nflverse's report for that week, filed before kickoff - the same
    source the backtest uses. Today's live report would be an anachronism.

ESPN does not use nflverse player ids, so live injuries are matched by name.
"""
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from rotobot import players as rp
from rotobot.player_data import PlayerStats, fantasy_points
from rotobot.rosters import Rosters
from rotobot.score import GameLine
from utils.historical_injuries import HistoricalInjuryLookup
from utils.historical_odds import NFLVERSE_TEAM_NAMES

logger = logging.getLogger("rotobot.live_players")

REFRESH_SECONDS = 12 * 3600
FANTASY_POSITIONS = {"QB", "RB", "FB", "WR", "TE"}
LIVE_OUT = {"out", "doubtful", "injured reserve", "suspension"}
HISTORICAL_OUT = {"out", "doubtful"}

# Current codes only - the table also carries pre-relocation aliases
ABBREVIATION = {}
for code, name in NFLVERSE_TEAM_NAMES.items():
    if code not in ("OAK", "SD", "STL", "LAR", "WSH"):
        ABBREVIATION[name] = code

_cache: Dict[str, Any] = {"season": None, "built": 0.0, "ps": None, "index": None, "rosters": None}
_model: Optional[Dict] = None
_injury_history: Dict[int, HistoricalInjuryLookup] = {}


def _stats(season: int):
    stale = time.time() - _cache["built"] > REFRESH_SECONDS
    if _cache["ps"] is None or _cache["season"] != season or stale:
        ps = PlayerStats([season - 1, season], current_season=season)
        _cache.update(season=season, built=time.time(), ps=ps, index=rp.player_index(ps),
                      rosters=Rosters([season], current_season=season))
    return _cache["ps"], _cache["index"]


def _player_model() -> Dict:
    global _model
    if _model is None:
        _model = rp.load_model()
    return _model


def normalise_name(name: str) -> str:
    """'Kenneth Walker III' and 'Kenneth Walker' should match; so should 'D.J.' and 'DJ'."""
    name = re.sub(r"[.'’]", "", name.lower())
    name = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", name)
    return " ".join(name.split())


def nflverse_week(game: Dict[str, Any]) -> int:
    """The schedule database numbers playoff rounds 1-4; nflverse continues from 19."""
    if game.get("season_type") == "playoffs":
        return 18 + int(game["week"])
    return int(game["week"])


async def _out_ids(game, team_code, team_name, ps, index, season, week, injury_client) -> Dict[str, Any]:
    played = game.get("home_score") is not None
    if played:
        lookup = _injury_history.get(season)
        if lookup is None:
            lookup = _injury_history[season] = HistoricalInjuryLookup(season)
        kickoff = _kickoff(game)
        entries = lookup.for_team_week(week, team_name, before=kickoff)
        ids = {e["player_id"] for e in entries if e["player_id"] and e["status"].lower() in HISTORICAL_OUT}
        return {"ids": ids,
                "names": sorted(e["player"] for e in entries
                                if e["player_id"] in ids and e["position"] in FANTASY_POSITIONS),
                "source": "nflverse_report"}

    try:
        report = await injury_client.get_team_injuries(team_name)
    except Exception as exc:
        logger.warning("Live injuries unavailable for %s: %s", team_name, exc)
        return {"ids": set(), "names": [], "source": "unavailable"}
    out_names = {normalise_name(e["player"]): e["player"] for e in report
                 if e["status"].lower() in LIVE_OUT}
    ids: Set[str] = set()
    for key in ps.recent_games(team_code, season, week, rp.WINDOW):
        for row in ps.player_games[key]:
            if normalise_name(row["name"]) in out_names:
                ids.add(row["player_id"])
    # The list shown to a reader is fantasy-relevant positions only; a lineman
    # being out still matters to the agents, not to a fantasy line
    shown = sorted(e["player"] for e in report
                   if e["status"].lower() in LIVE_OUT and e.get("position") in FANTASY_POSITIONS)
    return {"ids": ids, "names": shown, "source": "espn_live"}


def _kickoff(game) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(game["game_date"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None


async def project_game(game: Dict[str, Any], line: GameLine, injury_client) -> Dict[str, Any]:
    season, week = int(game["season"]), nflverse_week(game)
    ps, index = _stats(season)
    model = _player_model()
    codes = {side: ABBREVIATION.get(game[f"{side}_team"]) for side in ("home", "away")}
    if not all(codes.values()):
        return {"available": False, "reason": "Unknown team."}

    spreads = {"home": line.home_spread, "away": -line.home_spread}
    points = {"home": line.home_points, "away": line.away_points}
    out: Dict[str, Any] = {"available": True}
    for side, other in (("home", "away"), ("away", "home")):
        f_team = rp.team_features(ps, codes[side], season, week, model["league"])
        f_opp = rp.team_features(ps, codes[other], season, week, model["league"])
        if not f_team or not f_opp:
            out[side] = {"players": [], "out": [], "injury_source": None}
            continue
        team_line = rp.team_projection(model, f_team, f_opp, spreads[side], points[side])
        injured = await _out_ids(game, codes[side], game[f"{side}_team"], ps, index,
                                 season, week, injury_client)
        # The week's roster, when nflverse has published it - usually mid-week
        roster = _cache["rosters"].eligible(season, week, codes[side]) if _cache["rosters"] else None
        players = rp.with_ranges(
            rp.project_players(ps, model, index, codes[side], season, week, team_line,
                               injured["ids"], roster),
            model)

        # A played game shows what actually happened next to each projection
        actual = {r["player_id"]: r for r in ps.player_games.get((season, week, codes[side]), [])}
        for p in players:
            row = actual.get(p["player_id"])
            p["actual_ppr"] = round(fantasy_points(row), 1) if row else None

        out[side] = {
            "roster_checked": roster is not None,
            "team_line": {k: round(v, 1) for k, v in team_line.items()},
            "players": players,
            "out": injured["names"],
            "injury_source": injured["source"],
        }
    return out

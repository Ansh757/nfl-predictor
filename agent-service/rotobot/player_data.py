"""
player_data.py - nflverse weekly player stats, indexed for point-in-time use.

One CSV per season (stats_player_week_<season>.csv, ~4 MB, gitignored), from
the nflverse-data `stats_player` release. Rows carry nflverse's game_id
("2026_08_BAL_BUF"), the same key as the closing-lines file, so a backtest joins
a player's game to its line without matching team names.

Everything is keyed by (season, week, team). Postseason weeks are numbered
19-22, so (season, week) orders games in time across the whole history.
"""
import csv
import logging
import os
import time
import urllib.request
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("rotobot.player_data")

RELEASE_URL = ("https://github.com/nflverse/nflverse-data/releases/download/"
               "stats_player/stats_player_week_{season}.csv")
# The in-progress season is republished as games are played
CURRENT_SEASON_TTL_SECONDS = 12 * 3600

OFFENSE = {"QB", "RB", "FB", "WR", "TE"}
NUMERIC = (
    "completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions",
    "sacks_suffered", "carries", "rushing_yards", "rushing_tds", "receptions", "targets",
    "receiving_yards", "receiving_tds", "rushing_fumbles_lost", "receiving_fumbles_lost",
    "sack_fumbles_lost", "passing_2pt_conversions", "rushing_2pt_conversions",
    "receiving_2pt_conversions",
)
TEAM_SUMS = ("attempts", "completions", "passing_yards", "passing_tds", "passing_interceptions",
             "carries", "rushing_yards", "rushing_tds", "targets", "receptions")

GameKey = Tuple[int, int, str]          # (season, week, team)


def _path(season: int, cache_dir: str) -> str:
    return os.path.join(cache_dir, f"stats_player_week_{season}.csv")


def ensure_downloaded(season: int, cache_dir: str = ".", current_season: Optional[int] = None) -> bool:
    path = _path(season, cache_dir)
    stale = (season == current_season and os.path.exists(path)
             and time.time() - os.path.getmtime(path) > CURRENT_SEASON_TTL_SECONDS)
    if os.path.exists(path) and not stale:
        return True
    try:
        tmp = path + ".part"
        urllib.request.urlretrieve(RELEASE_URL.format(season=season), tmp)
        os.replace(tmp, path)
        logger.info("Downloaded player stats for %s", season)
        return True
    except Exception as exc:
        logger.warning("Could not download player stats for %s: %s", season, exc)
        return os.path.exists(path)          # a stale copy beats none


def _num(value) -> float:
    try:
        return float(value) if value not in ("", "NA", None) else 0.0
    except ValueError:
        return 0.0


class PlayerStats:
    """Offensive player-games and the team totals they add up to."""

    def __init__(self, seasons: Iterable[int], cache_dir: str = ".", current_season: Optional[int] = None):
        self.player_games: Dict[GameKey, List[Dict]] = defaultdict(list)
        self.team_totals: Dict[GameKey, Dict[str, float]] = {}
        self.opponent: Dict[GameKey, str] = {}
        self.game_id: Dict[GameKey, str] = {}
        self.team_schedule: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        self.season_type: Dict[Tuple[int, int], str] = {}

        for season in seasons:
            if ensure_downloaded(season, cache_dir, current_season):
                self._load(_path(season, cache_dir))

        for key, rows in self.player_games.items():
            self.team_totals[key] = {stat: sum(r[stat] for r in rows) for stat in TEAM_SUMS}
            self.team_schedule[key[2]].append((key[0], key[1]))
        for team in self.team_schedule:
            self.team_schedule[team].sort()

    def _load(self, path: str):
        with open(path, newline="") as handle:
            for row in csv.DictReader(handle):
                season, week, team = int(row["season"]), int(row["week"]), row["team"]
                key = (season, week, team)
                self.opponent[key] = row["opponent_team"]
                self.game_id[key] = row["game_id"]
                self.season_type[(season, week)] = row["season_type"]
                position = row.get("position") or ""
                touched = _num(row["attempts"]) or _num(row["carries"]) or _num(row["targets"])
                if position not in OFFENSE and not touched:
                    continue
                entry = {stat: _num(row.get(stat)) for stat in NUMERIC}
                entry.update(player_id=row["player_id"], name=row["player_display_name"],
                             position=position if position in OFFENSE else "OTHER",
                             headshot=row.get("headshot_url") or None)
                self.player_games[key].append(entry)

    def recent_games(self, team: str, season: int, week: int, n: int) -> List[GameKey]:
        """The team's last n games strictly before (season, week), newest first."""
        games = [g for g in self.team_schedule.get(team, []) if g < (season, week)]
        return [(s, w, team) for s, w in reversed(games[-n:])]

    def allowed(self, key: GameKey) -> Optional[Dict[str, float]]:
        """What the opponent's offence produced in this game - i.e. what this team allowed."""
        season, week, team = key
        return self.team_totals.get((season, week, self.opponent.get(key, "")))


def fantasy_points(stats: Dict[str, float], ppr: float = 1.0) -> float:
    """Standard scoring: 0.04/pass yd, 4/pass TD, -2/INT, 0.1/rush-rec yd, 6/TD, -2/fumble lost."""
    return (
        0.04 * stats.get("passing_yards", 0) + 4 * stats.get("passing_tds", 0)
        - 2 * stats.get("passing_interceptions", 0)
        + 0.1 * (stats.get("rushing_yards", 0) + stats.get("receiving_yards", 0))
        + 6 * (stats.get("rushing_tds", 0) + stats.get("receiving_tds", 0))
        + ppr * stats.get("receptions", 0)
        - 2 * stats.get("fumbles_lost", stats.get("rushing_fumbles_lost", 0)
                        + stats.get("receiving_fumbles_lost", 0) + stats.get("sack_fumbles_lost", 0))
        + 2 * (stats.get("passing_2pt_conversions", 0) + stats.get("rushing_2pt_conversions", 0)
               + stats.get("receiving_2pt_conversions", 0))
    )

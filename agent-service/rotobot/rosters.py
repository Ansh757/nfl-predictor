"""
rosters.py - Who is on each team, each week (nflverse weekly rosters).

The player model infers who plays from who played recently, and that inference
fails in two predictable ways: a player who left in the offseason still looks
like part of his old team in week 1, and a player moved to injured reserve
during the week never appears on the injury report as Out. Together they were
most of the backtest's "projected but did not play" errors.

The weekly roster answers both. A player is eligible only if that week's roster
lists him on the team as active (ACT). Game-day inactives (INA) are announced
about 90 minutes before kickoff, so treating them as out would be lookahead:
they stay eligible, exactly as a pick recorded the morning of the game would
see them.

One file per season (~15 MB, gitignored), republished weekly for the season in
progress - the upcoming week usually appears mid-week.
"""
import csv
import logging
import os
import time
import urllib.request
from collections import defaultdict
from typing import Dict, Iterable, Optional, Tuple

logger = logging.getLogger("rotobot.rosters")

RELEASE_URL = ("https://github.com/nflverse/nflverse-data/releases/download/"
               "weekly_rosters/roster_weekly_{season}.csv")
CURRENT_SEASON_TTL_SECONDS = 12 * 3600
ELIGIBLE = {"ACT", "INA"}       # INA is a game-day decision; see the module docstring


def _path(season: int, cache_dir: str) -> str:
    return os.path.join(cache_dir, f"roster_weekly_{season}.csv")


def _ensure(season: int, cache_dir: str, current_season: Optional[int]) -> bool:
    path = _path(season, cache_dir)
    stale = (season == current_season and os.path.exists(path)
             and time.time() - os.path.getmtime(path) > CURRENT_SEASON_TTL_SECONDS)
    if os.path.exists(path) and not stale:
        return True
    try:
        urllib.request.urlretrieve(RELEASE_URL.format(season=season), path + ".part")
        os.replace(path + ".part", path)
        return True
    except Exception as exc:
        logger.warning("Could not download rosters for %s: %s", season, exc)
        return os.path.exists(path)


class Rosters:
    def __init__(self, seasons: Iterable[int], cache_dir: str = ".", current_season: Optional[int] = None):
        # (season, week, team) -> {gsis_id: status}
        self.by_week: Dict[Tuple[int, int, str], Dict[str, str]] = defaultdict(dict)
        for season in seasons:
            if _ensure(season, cache_dir, current_season):
                self._load(_path(season, cache_dir))

    def _load(self, path: str):
        with open(path, newline="") as handle:
            for row in csv.DictReader(handle):
                pid = row.get("gsis_id")
                if not pid:
                    continue
                try:
                    key = (int(row["season"]), int(row["week"]), row["team"])
                except (KeyError, ValueError):
                    continue
                self.by_week[key][pid] = row.get("status") or ""

    def eligible(self, season: int, week: int, team: str) -> Optional[set]:
        """Player ids who may play, or None when there is no roster for that week."""
        roster = self.by_week.get((season, week, team))
        if not roster:
            return None
        return {pid for pid, status in roster.items() if status in ELIGIBLE}

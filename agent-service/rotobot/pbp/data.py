"""
data.py - nflverse play-by-play, cut down to what the engine fits on.

The full file is 372 columns and ~95 MB a season. The engine needs about sixty,
so each season is extracted once to pbp_extract_<season>.csv (gitignored) and
read from there. Fitting never runs in the service: it produces the JSON tables
in rotobot/pbp/, which are committed. The service only needs the current
season's plays for team adjustments, and reads the same extract.
"""
import csv
import gzip
import logging
import os
import time
import urllib.request
from typing import Dict, Iterator, List, Optional

logger = logging.getLogger("rotobot.pbp.data")

RELEASE_URL = ("https://github.com/nflverse/nflverse-data/releases/download/"
               "pbp/play_by_play_{season}.csv.gz")
CURRENT_SEASON_TTL_SECONDS = 12 * 3600

TEXT = ("game_id", "season_type", "posteam", "defteam", "home_team", "away_team", "play_type",
        "field_goal_result", "extra_point_result", "two_point_conv_result", "penalty_team",
        "receiver_player_id", "rusher_player_id", "passer_player_id", "timeout_team")
NUMBER = ("season", "week", "qtr", "game_seconds_remaining", "half_seconds_remaining", "down",
          "ydstogo", "yardline_100", "score_differential", "posteam_timeouts_remaining",
          "defteam_timeouts_remaining", "pass_attempt", "rush_attempt", "sack", "complete_pass",
          "interception", "fumble_lost", "yards_gained", "air_yards", "yards_after_catch",
          "touchdown", "pass_touchdown", "rush_touchdown", "return_touchdown", "kick_distance",
          "two_point_attempt", "penalty", "penalty_yards", "first_down_penalty", "qb_scramble",
          "out_of_bounds", "timeout", "qb_kneel", "qb_spike", "touchback", "return_yards",
          "drive", "safety", "total_home_score", "total_away_score", "shotgun", "no_huddle")
COLUMNS = TEXT + NUMBER


def _paths(season: int, cache_dir: str):
    return (os.path.join(cache_dir, f"play_by_play_{season}.csv.gz"),
            os.path.join(cache_dir, f"pbp_extract_{season}.csv"))


def ensure_extract(season: int, cache_dir: str = ".", current_season: Optional[int] = None) -> Optional[str]:
    raw, extract = _paths(season, cache_dir)
    stale = (season == current_season and os.path.exists(extract)
             and time.time() - os.path.getmtime(extract) > CURRENT_SEASON_TTL_SECONDS)
    if os.path.exists(extract) and not stale:
        return extract
    if not os.path.exists(raw) or stale:
        try:
            urllib.request.urlretrieve(RELEASE_URL.format(season=season), raw + ".part")
            os.replace(raw + ".part", raw)
        except Exception as exc:
            logger.warning("Could not download play-by-play for %s: %s", season, exc)
            return extract if os.path.exists(extract) else None
    with gzip.open(raw, "rt", newline="") as source, open(extract + ".part", "w", newline="") as out:
        reader = csv.DictReader(source)
        writer = csv.writer(out)
        writer.writerow(COLUMNS)
        for row in reader:
            writer.writerow([row.get(c, "") for c in COLUMNS])
    os.replace(extract + ".part", extract)
    return extract


def _num(value: str) -> Optional[float]:
    if value in ("", "NA"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def plays(seasons, cache_dir: str = ".", current_season: Optional[int] = None) -> Iterator[Dict]:
    """Every play of the given seasons, typed. Numbers are None where nflverse has NA."""
    for season in seasons:
        path = ensure_extract(season, cache_dir, current_season)
        if not path:
            continue
        with open(path, newline="") as handle:
            for row in csv.DictReader(handle):
                play = {c: row[c] for c in TEXT}
                for c in NUMBER:
                    play[c] = _num(row[c])
                yield play


def by_game(seasons, **kwargs) -> Dict[str, List[Dict]]:
    games: Dict[str, List[Dict]] = {}
    for play in plays(seasons, **kwargs):
        games.setdefault(play["game_id"], []).append(play)
    return games

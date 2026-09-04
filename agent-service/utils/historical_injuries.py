"""
historical_injuries.py - Free historical injury reports, for backtesting the injury agent.

InjuryImpactAgent shipped at an unmeasured default weight because ESPN's injury
endpoint returns only *current* status - there is no way to ask it what a team's
report looked like in week 6 of 2023. That is a limitation of ESPN, not of the
world: nflverse publishes the official weekly injury reports back to 2009, which
closes the gap the same way utils/historical_odds.py closed it for the market
agent.

No lookahead. The report this reads is the one filed before the game - the
practice-participation and game-status designations a team publishes during the
week. Rows are keyed by (season, week, team), so a week 6 prediction can only
ever see week 6's report, and `date_modified` is checked against kickoff for
the small number of rows that are amended late.

Source: https://github.com/nflverse/nflverse-data (injuries release, CC-BY)
"""
import csv
import logging
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from utils.historical_odds import NFLVERSE_TEAM_NAMES
from utils.injury_client import SEVERITY

NFLVERSE_INJURY_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"
)
DEFAULT_CACHE_DIR = "."

logger = logging.getLogger("utils.historical_injuries")

# nflverse reports two things per player per week. `report_status` is the game
# designation (Out / Doubtful / Questionable) and is what the live ESPN feed is
# equivalent to; `practice_status` is the midweek participation note, present on
# thousands of rows that carry no game designation at all.
#
# Only the game designation is used. A player limited in practice on Wednesday
# who carries no Friday designation is, by the league's own reporting, expected
# to play - treating that as an injury would inflate every team's burden and
# measure the agent against a signal the live version never sees.
PRACTICE_ONLY_IS_NOT_AN_INJURY = True


def _cache_path(season: int, cache_dir: str) -> str:
    return os.path.join(cache_dir, f"historical_injuries_{season}.csv")


def _download(season: int, path: str) -> bool:
    url = NFLVERSE_INJURY_URL.format(season=season)
    try:
        logger.info(f"Downloading nflverse injury report for {season}")
        urllib.request.urlretrieve(url, path)
        return True
    except Exception as exc:
        logger.error(f"Could not download injuries for {season}: {exc}")
        return False


def _parse_modified(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class HistoricalInjuryLookup:
    """
    Weekly injury reports for one season, keyed by (week, team name).

    Team names are translated to the schedule database's full names via the
    same abbreviation table the odds lookup uses - the two nflverse datasets
    share a convention, including the LA/LAC trap for the Rams.
    """

    def __init__(self, season: int, cache_dir: str = DEFAULT_CACHE_DIR,
                 download_if_missing: bool = True):
        self.season = season
        self.by_week: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
        self.rows_loaded = 0
        self.rows_skipped = 0

        path = _cache_path(season, cache_dir)
        if not os.path.exists(path) and download_if_missing:
            _download(season, path)

        if os.path.exists(path):
            self._load(path)
        else:
            logger.warning(f"No historical injuries available for {season}")

    def _load(self, path: str):
        with open(path, newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("game_type") != "REG":
                    continue

                status = (row.get("report_status") or "").strip()
                severity = SEVERITY.get(status.lower(), 0.0)
                if severity <= 0:
                    # Practice-only rows and "Note" entries carry no game
                    # designation. See PRACTICE_ONLY_IS_NOT_AN_INJURY.
                    self.rows_skipped += 1
                    continue

                team = NFLVERSE_TEAM_NAMES.get((row.get("team") or "").strip())
                if not team:
                    self.rows_skipped += 1
                    continue

                try:
                    week = int(row["week"])
                except (KeyError, ValueError):
                    self.rows_skipped += 1
                    continue

                self.by_week.setdefault((week, team), []).append({
                    "player": row.get("full_name") or "Unknown",
                    "position": (row.get("position") or "").strip(),
                    "status": status,
                    "severity": severity,
                    "detail": (row.get("report_primary_injury") or "")[:160],
                    "modified": _parse_modified(row.get("date_modified")),
                })
                self.rows_loaded += 1

        logger.info(
            f"Injury reports for {self.season}: {self.rows_loaded} designations "
            f"over {len(self.by_week)} team-weeks ({self.rows_skipped} rows skipped)"
        )

    def for_team_week(self, week: int, team: str,
                      before: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        One team's designations for one week.

        `before` filters on the report's own timestamp. Almost every row
        predates kickoff by design - the final report is filed on Friday for a
        Sunday game - but a handful are amended afterwards, and those would be
        information the live agent could not have had.
        """
        entries = self.by_week.get((week, team), [])
        if before is None:
            return entries
        return [entry for entry in entries
                if entry["modified"] is None or entry["modified"] < before]

    @property
    def available(self) -> bool:
        return bool(self.by_week)


def reports_by_game(lookup: HistoricalInjuryLookup,
                    games: List[Dict[str, Any]]) -> Dict[int, Dict[str, List[Dict[str, Any]]]]:
    """
    Build every game's injury report up front, keyed by game id.

    Deliberately not a client that is mutated per prediction. The backtest runs
    twelve games concurrently and they are not in the same week, so a client
    holding "the current week" would hand one game another week's report - the
    same race that produced limited lookahead in the Basic Predictor and had to
    be corrected. Precomputing means nothing is mutated after the run starts,
    matching how `pregame_ratings` and `pregame_rest` already work.

    Each game sees only its own week's designations, filtered to those filed
    before its kickoff.
    """
    by_game: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}
    for game in games:
        week = game.get("week")
        if week is None:
            continue
        kickoff = game.get("kickoff") or _parse_modified(game.get("game_date"))
        report: Dict[str, List[Dict[str, Any]]] = {}
        for (report_week, team), entries in lookup.by_week.items():
            if report_week != week:
                continue
            usable = [entry for entry in entries
                      if kickoff is None or entry["modified"] is None
                      or entry["modified"] < kickoff]
            if usable:
                report[team] = usable
        by_game[game["game_id"]] = report
    return by_game

"""
historical_odds.py - Free historical closing lines, for backtesting the market agent.

The Odds API's historical endpoint is paid-only, which is why MarketOddsAgent
originally shipped with an unmeasured weight. nflverse publishes closing
moneylines and spreads for every game as a public CSV, which closes that gap:
the market agent can now be scored on the same seasons as every other agent.

No lookahead. A closing line is fixed before kickoff, so using it to predict the
game it prices is legitimate - the same information a bettor had.

Source: https://github.com/nflverse/nfldata (CC-BY, updated weekly)
"""
import csv
import logging
import os
import urllib.request
from typing import Any, Dict, Optional, Tuple

from utils.odds_client import american_to_probability, remove_vig

NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
DEFAULT_CACHE = "historical_odds.csv"

logger = logging.getLogger("utils.historical_odds")

# nflverse uses its own abbreviations. Note LA (Rams) vs LAC (Chargers) - the
# usual trap, since most other sources call the Rams LAR.
NFLVERSE_TEAM_NAMES: Dict[str, str] = {
    "ARI": "Arizona Cardinals",      "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",       "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",      "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",     "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",         "DEN": "Denver Broncos",
    "DET": "Detroit Lions",          "GB": "Green Bay Packers",
    "HOU": "Houston Texans",         "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",   "KC": "Kansas City Chiefs",
    "LA": "Los Angeles Rams",        "LAC": "Los Angeles Chargers",
    "LV": "Las Vegas Raiders",       "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",      "NE": "New England Patriots",
    "NO": "New Orleans Saints",      "NYG": "New York Giants",
    "NYJ": "New York Jets",          "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",     "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",       "WAS": "Washington Commanders",
    # Pre-relocation codes, harmless to keep for older seasons
    "OAK": "Las Vegas Raiders",      "SD": "Los Angeles Chargers",
    "STL": "Los Angeles Rams",       "LAR": "Los Angeles Rams",
    "WSH": "Washington Commanders",
}


def _download(cache_path: str) -> bool:
    try:
        logger.info(f"Downloading historical odds to {cache_path}")
        urllib.request.urlretrieve(NFLVERSE_GAMES_URL, cache_path)
        return True
    except Exception as exc:
        logger.error(f"Could not download nflverse games.csv: {exc}")
        return False


class HistoricalOddsLookup:
    """
    Closing lines keyed by (season, home team, away team).

    Both team names are used rather than a game id because the schedule database
    and nflverse are populated independently and share no identifier.
    """

    def __init__(self, cache_path: str = DEFAULT_CACHE, download_if_missing: bool = True):
        self.cache_path = cache_path
        self.by_matchup: Dict[Tuple[int, str, str], Dict[str, Any]] = {}

        if not os.path.exists(cache_path) and download_if_missing:
            _download(cache_path)

        if os.path.exists(cache_path):
            self._load()
        else:
            logger.warning(f"No historical odds available at {cache_path}")

    def _load(self):
        skipped = 0
        with open(self.cache_path, newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("game_type") != "REG":
                    continue

                home_ml, away_ml = row.get("home_moneyline"), row.get("away_moneyline")
                if not home_ml or not away_ml:
                    skipped += 1
                    continue

                home = NFLVERSE_TEAM_NAMES.get(row["home_team"])
                away = NFLVERSE_TEAM_NAMES.get(row["away_team"])
                if not home or not away:
                    skipped += 1
                    continue

                try:
                    season = int(row["season"])
                    home_prob = american_to_probability(float(home_ml))
                    away_prob = american_to_probability(float(away_ml))
                except (TypeError, ValueError):
                    skipped += 1
                    continue

                spread = row.get("spread_line")
                self.by_matchup[(season, home, away)] = {
                    "home_win_probability": round(remove_vig(home_prob, away_prob), 4),
                    # nflverse states the spread from the home team's perspective
                    # with the opposite sign convention to The Odds API, so flip
                    # it to match what the live agent produces.
                    "home_spread": -float(spread) if spread else None,
                    "overround": round(home_prob + away_prob, 4),
                    # nflverse publishes a single consensus line, not per-book
                    "book_count": None,
                    "source": "nflverse",
                }

        logger.info(
            f"Loaded historical odds for {len(self.by_matchup)} games "
            f"({skipped} rows skipped)"
        )

    def get(self, season: int, home_team: str, away_team: str) -> Optional[Dict[str, Any]]:
        return self.by_matchup.get((season, home_team, away_team))

    def coverage(self, season: int) -> int:
        return sum(1 for key in self.by_matchup if key[0] == season)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    lookup = HistoricalOddsLookup()
    for year in range(2021, 2026):
        print(f"{year}: {lookup.coverage(year)} games with closing lines")

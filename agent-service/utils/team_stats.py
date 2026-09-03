"""
team_stats.py - Team form rebuilt from the local game log.

Single source of truth for the statistics the Basic Predictor scores on, used
by both the live agent and the backtest harness. That shared use is the whole
point: previously the backtest computed real form from the game log while the
live agent invented it, so measured accuracy described code that never ran in
production.

What the live agent used to produce, per team, on every prediction:

    point_differential   0        -- ESPN's team endpoint returns no points
                                    data, so this defaulted to 20 - 20
    recent_form          random.uniform() around the win rate
    home_win_rate        random.uniform() around the win rate
    away_win_rate        random.uniform() around the win rate
    strength_of_schedule 0.5      -- constant

Those fields carry 65% of the strength score, so most of a live prediction was
noise. All of them now come from real results.
"""
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("utils.team_stats")

# Games of history behind each profile. Roughly one season, so it reaches back
# into the previous year during the opening weeks rather than judging a team on
# two games.
FORM_WINDOW = 17

# Used only when a team has no history at all
NEUTRAL_PROFILE = {
    "win_rate": 0.5, "point_differential": 0.0, "recent_form": [1, 0, 1, 0],
    "home_win_rate": 0.5, "away_win_rate": 0.5, "strength_of_schedule": 0.5,
    "points_per_game": 22.0, "points_allowed_per_game": 22.0,
}


def load_game_log(db_path: str,
                  seasons: Optional[Sequence[int]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Per-team chronological log of completed games.

    Pass `seasons` to restrict the range (the backtest uses the tested season
    and the one before it). Omit it to load everything, which is what the live
    agent wants: a rolling window that walks backwards from today.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
        SELECT game_date, home_team, away_team, home_score, away_score
        FROM games
        WHERE home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND home_team IS NOT NULL
          AND away_team IS NOT NULL
          -- Invented results are not form. See utils/elo.py for the same guard;
          -- both agents read this table and both were learning from the same
          -- fabricated game.
          AND COALESCE(is_synthetic, 0) = 0
    """
    params: List[Any] = []
    if seasons:
        placeholders = ",".join("?" for _ in seasons)
        query += f" AND season IN ({placeholders})"
        params.extend(seasons)
    query += " ORDER BY game_date"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    log: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for game_date, home, away, home_score, away_score in rows:
        log[home].append({
            "date": game_date, "is_home": True, "points_for": home_score,
            "points_against": away_score, "won": 1 if home_score > away_score else 0,
        })
        log[away].append({
            "date": game_date, "is_home": False, "points_for": away_score,
            "points_against": home_score, "won": 1 if away_score > home_score else 0,
        })
    return log


def team_stats_as_of(log: Dict[str, List[Dict]], team: str, cutoff: str,
                     window: int = FORM_WINDOW) -> Dict[str, Any]:
    """
    Rebuild a team profile from its last `window` games before `cutoff`.

    `cutoff` is an ISO timestamp. Only games that kicked off strictly before it
    are used, which is what keeps the backtest honest and, live, simply means
    "everything played so far".
    """
    history = [game for game in log.get(team, []) if game["date"] < cutoff][-window:]

    if not history:
        return {
            "team": team, **NEUTRAL_PROFILE,
            "last_updated": datetime.now(), "games_used": 0,
            "source": "no_history",
        }

    games = len(history)
    wins = sum(game["won"] for game in history)
    points_for = sum(game["points_for"] for game in history)
    points_against = sum(game["points_against"] for game in history)

    home_games = [game for game in history if game["is_home"]]
    away_games = [game for game in history if not game["is_home"]]
    win_rate = wins / games

    home_win_rate = (sum(g["won"] for g in home_games) / len(home_games)) if home_games else win_rate
    away_win_rate = (sum(g["won"] for g in away_games) / len(away_games)) if away_games else win_rate

    recent = [game["won"] for game in history[-4:]]
    while len(recent) < 4:                 # pad a short history with the mean outcome
        recent.insert(0, 1 if win_rate >= 0.5 else 0)

    return {
        "team": team,
        "win_rate": round(win_rate, 3),
        "point_differential": round((points_for - points_against) / games, 2),
        "recent_form": recent,
        "home_win_rate": round(home_win_rate, 3),
        "away_win_rate": round(away_win_rate, 3),
        "strength_of_schedule": 0.5,
        "points_per_game": round(points_for / games, 1),
        "points_allowed_per_game": round(points_against / games, 1),
        "last_updated": datetime.now(),
        "games_used": games,
        "source": "game_log",
    }

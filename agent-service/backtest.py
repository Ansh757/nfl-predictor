"""
backtest.py - Walk-forward accuracy test of the prediction ensemble.

For every completed regular-season game in the schedule database, this replays
the same four agents and the same voting logic used by POST /predict, then
compares the pick to the final score.

Point-in-time discipline
------------------------
Team statistics are rebuilt from the game log using only games that kicked off
BEFORE the game being predicted (a rolling window of the team's most recent
`FORM_WINDOW` games, which spans the previous season early in the year). The
live ESPN endpoint is never called during a backtest, because it returns
*current* standings - using it would leak the final results of the very season
being tested.

Two agents cannot be replayed faithfully against historical games:
  * Weather   - the free endpoints serve current conditions only, so there is
                no way to fetch the weather at a 2025 kickoff today. The agent
                falls back to its own seasonal simulation, keyed to the real
                month of the game.
  * News      - RSS feeds carry today's headlines, not the ones published in
                the game week, so the agent runs in simulated-scenario mode.

Market Intelligence generates synthetic betting data in production as well, so
it is replayed unchanged.

Usage:
    python backtest.py --season 2025 --runs 10
"""
import argparse
import asyncio
import json
import logging
import random
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.basic_predictor import BasicPredictorAgent
from agents.consensus import build_consensus
from agents.data_collector import DataCollectorAgent
from agents.market_intelligence_agent import MarketIntelligenceAgent
from agents.news_sentiment_agent import NewsSentimentAgent
from agents.weather_agent import WeatherImpactAgent

# Silence agent chatter; the backtest prints its own report
logging.basicConfig(level=logging.ERROR)

FORM_WINDOW = 17          # games of history used to build each team's profile
CONCURRENCY = 12          # games predicted in parallel


class GameStub:
    """Stands in for the GameData pydantic model the agents expect."""

    def __init__(self, game_id: int, home_team_name: str, away_team_name: str,
                 game_time: datetime, venue: Optional[str], is_dome: bool):
        self.game_id = game_id
        self.home_team_name = home_team_name
        self.away_team_name = away_team_name
        self.game_time = game_time
        self.venue = venue
        self.is_dome = is_dome


class OfflineWeatherAgent(WeatherImpactAgent):
    """Weather agent that simulates conditions for the month the game was played."""

    def __init__(self, name: str):
        super().__init__(name)
        self.game_months: Dict[str, int] = {}
        self.current_month = datetime.now().month

    async def _get_weather(self, venue: str) -> Dict[str, Any]:
        venue_info = self.nfl_venues.get(venue, {})

        if venue_info.get("dome"):
            return {
                "venue": venue,
                "is_dome": True,
                "temperature": 72,
                "conditions": "controlled",
                "wind_speed": 0,
                "precipitation": 0,
                "source": "dome"
            }

        # _simulate_weather() keys off datetime.now(); pin it to the game's month
        return self._simulate_weather_for_month(venue, venue_info, self.current_month)

    def _simulate_weather_for_month(self, venue: str, venue_info: Dict, month: int) -> Dict[str, Any]:
        if venue_info.get("state") in ["NY", "WI", "IL", "MA", "MN"]:       # Northern
            temps = [25, 30, 40, 55, 65, 75, 80, 78, 70, 55, 40, 30]
        elif venue_info.get("state") in ["FL", "TX", "LA"]:                 # Southern
            temps = [60, 65, 70, 75, 80, 85, 88, 88, 85, 78, 70, 65]
        else:                                                               # Moderate
            temps = [40, 45, 50, 60, 68, 75, 78, 76, 70, 60, 50, 45]

        temp = temps[month - 1] + random.randint(-5, 5)
        wind = random.randint(5, 20)
        precip = random.uniform(0, 0.3) if month in [4, 5, 10, 11] else 0

        return {
            "venue": venue,
            "is_dome": False,
            "temperature": temp,
            "feels_like": temp,
            "conditions": "partly cloudy" if precip == 0 else "rain",
            "wind_speed": wind,
            "precipitation": round(precip, 2),
            "humidity": 65,
            "source": "simulated"
        }


def load_games(db_path: str, season: int) -> List[Dict[str, Any]]:
    """Load every completed regular-season game, oldest first."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT game_id, season, week, game_date, home_team, away_team,
               venue, is_dome, home_score, away_score
        FROM games
        WHERE season = ?
          AND season_type = 'regular'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND home_team IS NOT NULL
          AND away_team IS NOT NULL
        ORDER BY game_date
    ''', (season,))
    columns = [desc[0] for desc in cursor.description]
    games = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return games


def load_game_log(db_path: str, season: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build a per-team chronological game log covering the tested season and the
    one before it, so week 1 still has a full history window to draw on.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT game_date, home_team, away_team, home_score, away_score
        FROM games
        WHERE season IN (?, ?)
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND home_team IS NOT NULL
          AND away_team IS NOT NULL
        ORDER BY game_date
    ''', (season - 1, season))
    rows = cursor.fetchall()
    conn.close()

    log: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for game_date, home, away, home_score, away_score in rows:
        log[home].append({
            "date": game_date, "is_home": True, "points_for": home_score,
            "points_against": away_score, "won": 1 if home_score > away_score else 0
        })
        log[away].append({
            "date": game_date, "is_home": False, "points_for": away_score,
            "points_against": home_score, "won": 1 if away_score > home_score else 0
        })
    return log


def team_stats_as_of(log: Dict[str, List[Dict]], team: str, cutoff: str) -> Dict[str, Any]:
    """Rebuild a team profile from the last FORM_WINDOW games before `cutoff`."""
    history = [g for g in log.get(team, []) if g["date"] < cutoff][-FORM_WINDOW:]

    if not history:
        # No prior information at all - a neutral, league-average profile
        return {
            "team": team, "win_rate": 0.5, "point_differential": 0.0,
            "recent_form": [1, 0, 1, 0], "home_win_rate": 0.5, "away_win_rate": 0.5,
            "strength_of_schedule": 0.5, "points_per_game": 22.0,
            "points_allowed_per_game": 22.0, "last_updated": datetime.now(),
            "source": "backtest_neutral"
        }

    games = len(history)
    wins = sum(g["won"] for g in history)
    points_for = sum(g["points_for"] for g in history)
    points_against = sum(g["points_against"] for g in history)

    home_games = [g for g in history if g["is_home"]]
    away_games = [g for g in history if not g["is_home"]]
    win_rate = wins / games

    home_win_rate = (sum(g["won"] for g in home_games) / len(home_games)) if home_games else win_rate
    away_win_rate = (sum(g["won"] for g in away_games) / len(away_games)) if away_games else win_rate

    recent = [g["won"] for g in history[-4:]]
    while len(recent) < 4:                      # pad short histories with the mean outcome
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
        "source": "backtest_pointintime"
    }


async def predict_one(game: Dict, agents: Dict, log: Dict) -> Dict[str, Any]:
    """Run the full ensemble on a single game and score it against the result."""
    basic, weather, news, market, collector = (
        agents["basic"], agents["weather"], agents["news"],
        agents["market"], agents["collector"]
    )

    home, away = game["home_team"], game["away_team"]
    cutoff = game["game_date"]

    stub = GameStub(
        game_id=game["game_id"],
        home_team_name=home,
        away_team_name=away,
        game_time=datetime.now(),
        venue=game["venue"],
        is_dome=bool(game["is_dome"])
    )

    # Inject point-in-time stats so the basic predictor never calls ESPN
    basic.stats_cache[f"{home}_stats"] = (team_stats_as_of(log, home, cutoff), datetime.now())
    basic.stats_cache[f"{away}_stats"] = (team_stats_as_of(log, away, cutoff), datetime.now())

    # Pin simulated weather to the month the game was actually played
    weather.current_month = datetime.fromisoformat(
        cutoff.replace("Z", "+00:00")
    ).month

    context = await collector.collect_game_data(stub)
    # The weather agent reads the home team name out of the context
    context["home_team_stats"]["team"] = home

    basic_pred = await basic.predict_game(stub, context)
    weather_pred = await weather.predict_game(stub, context)
    news_pred = await news.predict_game(stub, context)
    market_pred = await market.predict_game(stub, context)

    predictions = [basic_pred, weather_pred, news_pred, market_pred]
    names = [basic.name, weather.name, news.name, market.name]
    consensus = build_consensus(predictions, names, home, away)

    actual_winner = home if game["home_score"] > game["away_score"] else away
    tie = game["home_score"] == game["away_score"]

    return {
        "game_id": game["game_id"],
        "week": game["week"],
        "matchup": f"{away} @ {home}",
        "actual_winner": actual_winner,
        "tie": tie,
        "ensemble": consensus["winner"],
        "ensemble_correct": consensus["winner"] == actual_winner,
        "confidence": consensus["confidence"],
        "picked_home": consensus["winner"] == home,
        "agents": {
            names[i]: {
                "pick": p["winner"],
                "correct": p["winner"] == actual_winner,
                "confidence": p["confidence"]
            }
            for i, p in enumerate(predictions)
        }
    }


async def run_once(games: List[Dict], log: Dict) -> List[Dict[str, Any]]:
    """One full pass over the season."""
    agents = {
        "basic": BasicPredictorAgent("Basic Predictor"),
        "weather": OfflineWeatherAgent("Weather Impact"),
        # Real RSS carries today's news, not the game week's - use simulation
        "news": NewsSentimentAgent("News Sentiment", use_real_news=False),
        "market": MarketIntelligenceAgent("Market Intelligence"),
        "collector": DataCollectorAgent("Data Collector"),
    }

    results: List[Dict[str, Any]] = []
    for start in range(0, len(games), CONCURRENCY):
        batch = games[start:start + CONCURRENCY]
        results.extend(await asyncio.gather(*(predict_one(g, agents, log) for g in batch)))
    return results


def summarize(all_runs: List[List[Dict]], agent_names: List[str]) -> Dict[str, Any]:
    """Aggregate per-week and per-agent accuracy across every run."""
    weeks = sorted({r["week"] for r in all_runs[0]})

    weekly: Dict[int, Dict[str, Any]] = {}
    for week in weeks:
        per_run_correct, per_run_total = [], None
        for run in all_runs:
            week_games = [r for r in run if r["week"] == week]
            per_run_correct.append(sum(1 for r in week_games if r["ensemble_correct"]))
            per_run_total = len(week_games)
        weekly[week] = {
            "games": per_run_total,
            "mean_correct": statistics.mean(per_run_correct),
            "best_correct": max(per_run_correct),
            "worst_correct": min(per_run_correct),
            "mean_accuracy": statistics.mean(per_run_correct) / per_run_total
        }

    season_accuracies = [
        sum(1 for r in run if r["ensemble_correct"]) / len(run) for run in all_runs
    ]
    home_rates = [
        sum(1 for r in run if r["picked_home"]) / len(run) for run in all_runs
    ]

    agent_summary = {}
    for name in agent_names:
        accs = [
            sum(1 for r in run if r["agents"][name]["correct"]) / len(run)
            for run in all_runs
        ]
        agent_summary[name] = {
            "mean_accuracy": statistics.mean(accs),
            "stdev": statistics.stdev(accs) if len(accs) > 1 else 0.0
        }

    # Baselines for context
    home_baseline = sum(
        1 for r in all_runs[0]
        if r["actual_winner"] == r["matchup"].split(" @ ")[1]
    ) / len(all_runs[0])

    return {
        "weekly": weekly,
        "season_mean_accuracy": statistics.mean(season_accuracies),
        "season_stdev": statistics.stdev(season_accuracies) if len(season_accuracies) > 1 else 0.0,
        "season_best": max(season_accuracies),
        "season_worst": min(season_accuracies),
        "mean_home_pick_rate": statistics.mean(home_rates),
        "home_team_baseline": home_baseline,
        "agents": agent_summary,
        "total_games": len(all_runs[0])
    }


def print_report(summary: Dict[str, Any], season: int, runs: int):
    print(f"\nNFL Prediction Backtest - {season} regular season")
    print(f"{summary['total_games']} games, {runs} independent runs\n")

    print("| Week | Games | Mean Correct | Accuracy | Best | Worst |")
    print("|------|-------|--------------|----------|------|-------|")
    for week, data in summary["weekly"].items():
        print(f"| {week} | {data['games']} | {data['mean_correct']:.1f} | "
              f"{data['mean_accuracy']:.1%} | {data['best_correct']} | {data['worst_correct']} |")

    print(f"\nSeason accuracy : {summary['season_mean_accuracy']:.1%} "
          f"(+/- {summary['season_stdev']:.1%}), "
          f"range {summary['season_worst']:.1%} - {summary['season_best']:.1%}")
    print(f"Home picks      : {summary['mean_home_pick_rate']:.1%}")
    print(f"Always-home     : {summary['home_team_baseline']:.1%} (baseline)")

    print("\nPer-agent accuracy:")
    for name, data in summary["agents"].items():
        print(f"  {name:22s} {data['mean_accuracy']:.1%} (+/- {data['stdev']:.1%})")


async def main():
    parser = argparse.ArgumentParser(description="Backtest the NFL prediction ensemble.")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--runs", type=int, default=10,
                        help="Independent passes to average over (3 of 4 agents are stochastic).")
    parser.add_argument("--db-path", default="nfl_schedule.db")
    parser.add_argument("--output", default="backtest_results.json")
    args = parser.parse_args()

    games = load_games(args.db_path, args.season)
    if not games:
        raise SystemExit(f"No completed regular-season games found for {args.season}.")
    log = load_game_log(args.db_path, args.season)

    print(f"Backtesting {len(games)} games over {args.runs} runs...")
    all_runs = []
    for run_index in range(args.runs):
        random.seed(1000 + run_index)
        all_runs.append(await run_once(games, log))
        print(f"  run {run_index + 1}/{args.runs} complete")

    agent_names = list(all_runs[0][0]["agents"].keys())
    summary = summarize(all_runs, agent_names)
    print_report(summary, args.season, args.runs)

    with open(args.output, "w") as handle:
        json.dump({"season": args.season, "runs": args.runs, "summary": summary},
                  handle, indent=2, default=str)
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    asyncio.run(main())

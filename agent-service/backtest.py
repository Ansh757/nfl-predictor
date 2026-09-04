"""
backtest.py - Walk-forward accuracy test of the prediction ensemble.

For every completed regular-season game in the schedule database, this replays
the same agents and the same voting logic used by POST /predict, then
compares the pick to the final score.

Point-in-time discipline
------------------------
Team statistics are rebuilt from the game log using only games that kicked off
BEFORE the game being predicted (a rolling window of the team's most recent
`FORM_WINDOW` games, which spans the previous season early in the year). The
same utils/team_stats.py helpers back the live agent, so both paths compute
form the same way. The
live ESPN endpoint is never called during a backtest, because it returns
*current* standings - using it would leak the final results of the very season
being tested.

Market Odds is replayed against real closing lines from nflverse (the free
Odds API tier has no historical endpoint), driving the real agent through
HistoricalOddsClient rather than a stub.

Injury Impact cannot be replayed at all - ESPN publishes no historical injury
archive - so it runs as an InertAgent, contributing nothing to the vote.

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
from agents.elo_agent import EloRatingAgent
from agents.injury_agent import InjuryImpactAgent
from agents.odds_agent import MarketOddsAgent
from agents.rest_travel_agent import RestTravelAgent
from utils.elo import EloRatingSystem
from utils.team_stats import FORM_WINDOW, load_game_log, team_stats_as_of
from utils.historical_odds import HistoricalOddsLookup
from utils.historical_injuries import HistoricalInjuryLookup, reports_by_game


class HistoricalOddsClient:
    """
    Drop-in replacement for OddsClient backed by nflverse closing lines.

    Feeding this to the real MarketOddsAgent means the backtest exercises the
    agent's actual decision logic - de-vigged probability, confidence, reasoning
    - rather than a reimplementation of it. Season is fixed for a whole backtest
    run, so holding it on the client is safe under concurrency.
    """

    def __init__(self, season: int, lookup: HistoricalOddsLookup):
        self.season = season
        self.lookup = lookup
        self.api_key = "historical"
        self.quota_remaining = None

    @property
    def enabled(self) -> bool:
        return True

    async def get_all_odds(self):
        return []

    async def get_game_odds(self, home_team: str, away_team: str):
        return self.lookup.get(self.season, home_team, away_team)


class InertAgent:
    """
    Stands in for an agent whose data cannot be replayed historically.

    Returns confidence exactly 0.50, which contributes nothing under weighted
    consensus (it scores on confidence - 0.5). Using today's odds or today's
    injury report to predict a 2025 game would be an anachronism, so these
    agents are measured as what they are in backtest: absent.
    """

    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason

    async def predict_game(self, game_data, game_context):
        return {
            "winner": game_data.home_team_name,
            "confidence": 0.50,
            "reasoning": self.reason,
            "source": "inert"
        }


# Silence agent chatter; the backtest prints its own report
logging.basicConfig(level=logging.ERROR)

CONCURRENCY = 12          # games predicted in parallel


class GameStub:
    """Stands in for the GameData pydantic model the agents expect."""

    def __init__(self, game_id: int, home_team_name: str, away_team_name: str,
                 game_time: datetime, venue: Optional[str], is_dome: bool,
                 neutral_site: Optional[bool] = None,
                 venue_country: Optional[str] = None):
        self.game_id = game_id
        self.home_team_name = home_team_name
        self.away_team_name = away_team_name
        self.game_time = game_time
        self.venue = venue
        self.is_dome = is_dome
        # Carried so the backtest exercises the same venue resolution the live
        # agents do, rather than a different one.
        self.neutral_site = neutral_site
        self.venue_country = venue_country


def load_games(db_path: str, season: int) -> List[Dict[str, Any]]:
    """Load every completed regular-season game, oldest first."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT game_id, season, week, game_date, home_team, away_team,
               venue, is_dome, home_score, away_score, neutral_site, venue_country
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


async def predict_one(game: Dict, agents: Dict, log: Dict, method: str = "weighted") -> Dict[str, Any]:
    """Run the full ensemble on a single game and score it against the result."""
    basic, market, elo, rest, injury = (
        agents["basic"], agents["market"], agents["elo"],
        agents["rest"], agents["injury"]
    )

    home, away = game["home_team"], game["away_team"]
    cutoff = game["game_date"]
    kickoff = datetime.fromisoformat(cutoff.replace("Z", "+00:00")).replace(tzinfo=None)

    stub = GameStub(
        game_id=game["game_id"],
        home_team_name=home,
        away_team_name=away,
        game_time=kickoff,
        venue=game["venue"],
        is_dome=bool(game["is_dome"]),
        neutral_site=None if game["neutral_site"] is None else bool(game["neutral_site"]),
        venue_country=game["venue_country"]
    )

    # Point-in-time stats, keyed by game so concurrent games cannot overwrite
    # each other's. The live agent reads the same helper with a cutoff of now.
    basic.pregame_stats[game["game_id"]] = {
        home: team_stats_as_of(log, home, cutoff),
        away: team_stats_as_of(log, away, cutoff),
    }

    context = {}

    basic_pred = await basic.predict_game(stub, context)
    market_pred = await market.predict_game(stub, context)
    elo_pred = await elo.predict_game(stub, context)
    rest_pred = await rest.predict_game(stub, context)
    injury_pred = await injury.predict_game(stub, context)

    predictions = [basic_pred, market_pred, elo_pred, rest_pred, injury_pred]
    names = [basic.name, market.name, elo.name, rest.name, injury.name]
    consensus = build_consensus(predictions, names, home, away, method=method)

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


async def run_once(games: List[Dict], log: Dict, method: str = "weighted",
                   elo_system=None, db_path: str = "nfl_schedule.db",
                   season: int = None, odds_lookup=None,
                   injury_reports: Dict[int, Any] = None) -> List[Dict[str, Any]]:
    """One full pass over the season."""
    if odds_lookup is not None and season is not None:
        market_agent = MarketOddsAgent(
            "Market Odds", client=HistoricalOddsClient(season, odds_lookup))
    else:
        market_agent = InertAgent("Market Odds", "No historical odds available.")

    elo_agent = EloRatingAgent("Elo Ratings", db_path=db_path, rating_system=elo_system)
    if elo_system is not None:
        # Ratings as they stood before each kickoff - recorded during build()
        elo_agent.pregame_ratings = elo_system.pregame_ratings

    # Real weekly injury reports from nflverse, fed in per game. Falls back to
    # inert only when the download failed - an unavailable feed must not be
    # silently scored as a signal.
    if injury_reports:
        injury_agent = InjuryImpactAgent("Injury Impact")
        injury_agent.pregame_reports = injury_reports
    else:
        injury_agent = InertAgent("Injury Impact", "No historical injury data available.")

    agents = {
        "basic": BasicPredictorAgent("Basic Predictor"),
        # Real closing lines from nflverse
        "market": market_agent,
        "injury": injury_agent,
        "elo": elo_agent,
        "rest": RestTravelAgent("Rest & Travel", db_path=db_path),
    }

    results: List[Dict[str, Any]] = []
    for start in range(0, len(games), CONCURRENCY):
        batch = games[start:start + CONCURRENCY]
        results.extend(await asyncio.gather(*(predict_one(g, agents, log, method) for g in batch)))
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
        inert = all(
            r["agents"][name]["confidence"] == 0.5
            for run in all_runs for r in run
        )
        agent_summary[name] = {
            "mean_accuracy": statistics.mean(accs),
            "stdev": statistics.stdev(accs) if len(accs) > 1 else 0.0,
            "inert": inert
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


def print_report(summary: Dict[str, Any], season: int, runs: int, method: str = "weighted"):
    print(f"\nNFL Prediction Backtest - {season} regular season")
    print(f"{summary['total_games']} games, {runs} independent runs, {method} voting\n")

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
        note = "  [inert - no historical data, contributes nothing]" if data.get("inert") else ""
        print(f"  {name:22s} {data['mean_accuracy']:.1%} (+/- {data['stdev']:.1%}){note}")


async def main():
    parser = argparse.ArgumentParser(description="Backtest the NFL prediction ensemble.")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--runs", type=int, default=10,
                        help="Independent passes to average over (3 of 4 agents are stochastic).")
    parser.add_argument("--method", default="weighted", choices=["weighted", "majority"],
                        help="Consensus voting method to evaluate.")
    parser.add_argument("--db-path", default="nfl_schedule.db")
    parser.add_argument("--output", default="backtest_results.json")
    args = parser.parse_args()

    games = load_games(args.db_path, args.season)
    if not games:
        raise SystemExit(f"No completed regular-season games found for {args.season}.")
    # Same function the live agent uses, so backtest and production compute
    # team form identically. Restricted to the tested season and the one
    # before it to keep the window point-in-time.
    log = load_game_log(args.db_path, [args.season - 1, args.season])
    # Elo walks the log forward and records pre-kickoff ratings per game,
    # so this is point-in-time even though it is built once up front.
    elo_system = EloRatingSystem.from_database(args.db_path, through_season=args.season)
    # Closing lines are fixed before kickoff, so using them is not lookahead
    odds_lookup = HistoricalOddsLookup()
    coverage = odds_lookup.coverage(args.season)
    print(f"Historical odds: {coverage} games with closing lines for {args.season}")

    # Weekly injury reports, precomputed per game so nothing is mutated once the
    # concurrent run starts. Each game sees only its own week, filtered to
    # designations filed before its kickoff.
    injury_lookup = HistoricalInjuryLookup(args.season)
    injury_reports = reports_by_game(injury_lookup, games) if injury_lookup.available else {}
    covered = sum(1 for report in injury_reports.values() if report)
    print(f"Historical injuries: {covered} games with a week's report for {args.season}")

    print(f"Backtesting {len(games)} games over {args.runs} runs...")
    all_runs = []
    for run_index in range(args.runs):
        random.seed(1000 + run_index)
        all_runs.append(await run_once(games, log, args.method, elo_system,
                                       args.db_path, args.season, odds_lookup,
                                       injury_reports))
        print(f"  run {run_index + 1}/{args.runs} complete")

    agent_names = list(all_runs[0][0]["agents"].keys())
    summary = summarize(all_runs, agent_names)
    print_report(summary, args.season, args.runs, args.method)

    with open(args.output, "w") as handle:
        json.dump({"season": args.season, "runs": args.runs, "summary": summary},
                  handle, indent=2, default=str)
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    asyncio.run(main())

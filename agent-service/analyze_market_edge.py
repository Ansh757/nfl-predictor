"""
analyze_market_edge.py - Does the ensemble know anything the market does not?

Straight-up accuracy is close to a solved problem: read the closing moneyline,
pick the shorter price, and you are at ~66% without a model. The ensemble is
currently *below* that, so its only claim to existing is being right where it
disagrees with the market. This measures whether it is.

Two questions:

  1. Disagreement. On games where the ensemble and Market Odds pick different
     winners, who is right more often? If that is a coin flip, the four
     non-market agents are decoration.

  2. Against the spread. Straight-up favours are priced in; the spread is where
     a real edge has to show up. Break-even at standard -110 juice is 52.38%,
     so anything below that loses money however good it looks.

Usage:
    python analyze_market_edge.py --seasons 2021-2025
"""
import argparse
import asyncio
import csv
import logging
import os
import random
import statistics
from math import sqrt
from typing import Any, Dict, List, Optional, Tuple

from backtest import load_games, run_once
from utils.elo import EloRatingSystem
from utils.historical_odds import DEFAULT_CACHE, NFLVERSE_TEAM_NAMES, HistoricalOddsLookup
from utils.team_stats import load_game_log

logging.basicConfig(level=logging.ERROR)

# A -110 bet must win 11/21 of the time to break even
BREAK_EVEN_ATS = 11 / 21


def load_spreads(cache_path: str = DEFAULT_CACHE) -> Dict[Tuple[int, str, str], float]:
    """
    Closing spread per matchup, from the home team's perspective.

    nflverse states spread_line positively when the home team is favoured, so
    the home side covers when (home_score - away_score) > spread_line.
    """
    spreads: Dict[Tuple[int, str, str], float] = {}
    if not os.path.exists(cache_path):
        return spreads

    with open(cache_path, newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("game_type") != "REG" or not row.get("spread_line"):
                continue
            home = NFLVERSE_TEAM_NAMES.get(row["home_team"])
            away = NFLVERSE_TEAM_NAMES.get(row["away_team"])
            if not home or not away:
                continue
            try:
                spreads[(int(row["season"]), home, away)] = float(row["spread_line"])
            except (TypeError, ValueError):
                continue
    return spreads


def home_probability(pick: str, confidence: float, home_team: str) -> float:
    """An agent's pick plus confidence, expressed as P(home wins)."""
    return confidence if pick == home_team else 1.0 - confidence


async def collect(season: int, db_path: str) -> List[Dict[str, Any]]:
    """Run the season once and pull out what the analysis needs per game."""
    games = load_games(db_path, season)
    log = load_game_log(db_path, [season - 1, season])
    elo = EloRatingSystem.from_database(db_path, through_season=season)
    odds = HistoricalOddsLookup()

    random.seed(7)
    results = await run_once(games, log, "weighted", elo, db_path, season, odds)

    scores = {
        game["game_id"]: (game["home_score"], game["away_score"], game["week"])
        for game in games
    }

    rows = []
    for result in results:
        away_team, home_team = result["matchup"].split(" @ ")
        market = result["agents"].get("Market Odds")
        if not market or market["confidence"] == 0.5:
            continue                      # no market for this game - nothing to compare

        home_score, away_score, week = scores[result["game_id"]]
        rows.append({
            "season": season,
            "week": week,
            "home": home_team,
            "away": away_team,
            "margin": home_score - away_score,
            "actual_winner": result["actual_winner"],
            "ensemble_pick": result["ensemble"],
            "ensemble_correct": result["ensemble_correct"],
            "ensemble_home_prob": home_probability(
                result["ensemble"], result["confidence"], home_team),
            "market_pick": market["pick"],
            "market_correct": market["correct"],
            "market_home_prob": home_probability(
                market["pick"], market["confidence"], home_team),
        })
    return rows


def report_disagreement(rows: List[Dict[str, Any]]):
    agree = [r for r in rows if r["ensemble_pick"] == r["market_pick"]]
    differ = [r for r in rows if r["ensemble_pick"] != r["market_pick"]]

    print("\n" + "=" * 68)
    print("1. STRAIGHT UP: where the ensemble and the market disagree")
    print("=" * 68)
    print(f"  games with a market      {len(rows)}")
    print(f"  ensemble accuracy        {mean_pct(r['ensemble_correct'] for r in rows)}")
    print(f"  market accuracy          {mean_pct(r['market_correct'] for r in rows)}")
    print()
    print(f"  agree      {len(agree):4d} games ({len(agree)/len(rows):.0%})  "
          f"-> both right {mean_pct(r['ensemble_correct'] for r in agree)}")
    if differ:
        wins = sum(1 for r in differ if r["ensemble_correct"])
        print(f"  disagree   {len(differ):4d} games ({len(differ)/len(rows):.0%})  "
              f"-> ensemble right {mean_pct(r['ensemble_correct'] for r in differ)}, "
              f"market right {mean_pct(r['market_correct'] for r in differ)}")
        print(f"             {significance(wins, len(differ))} vs a coin flip")
        print()
        print("  This is the number that matters. At ~50% the four non-market")
        print("  agents add nothing the closing line does not already carry.")


def report_ats(rows: List[Dict[str, Any]], spreads: Dict[Tuple[int, str, str], float]):
    print("\n" + "=" * 68)
    print("2. AGAINST THE SPREAD: bet the side the ensemble likes more than the market")
    print("=" * 68)
    print(f"  break-even at -110 juice: {BREAK_EVEN_ATS:.2%}\n")

    priced = []
    for row in rows:
        spread = spreads.get((row["season"], row["home"], row["away"]))
        if spread is None:
            continue
        edge = row["ensemble_home_prob"] - row["market_home_prob"]
        # Home covers when the margin beats the number it was giving
        if row["margin"] == spread:
            cover = None                  # push
        else:
            cover = "home" if row["margin"] > spread else "away"
        priced.append({**row, "spread": spread, "edge": edge, "cover": cover})

    if not priced:
        print("  no spreads available")
        return

    print(f"  {'min edge':>9}  {'bets':>5}  {'won':>5}  {'push':>5}  {'ATS%':>7}   "
          f"{'verdict':<12} significance")
    print("  " + "-" * 76)
    for threshold in (0.0, 0.02, 0.05, 0.10, 0.15, 0.20):
        bets = [p for p in priced if abs(p["edge"]) > threshold]
        decided = [p for p in bets if p["cover"] is not None]
        if not decided:
            continue
        won = sum(1 for p in decided
                  if (p["edge"] > 0 and p["cover"] == "home")
                  or (p["edge"] < 0 and p["cover"] == "away"))
        rate = won / len(decided)
        verdict = "profitable" if rate > BREAK_EVEN_ATS else "loses money"
        print(f"  {threshold:>9.0%}  {len(decided):>5}  {won:>5}  "
              f"{len(bets)-len(decided):>5}  {rate:>6.1%}   "
              f"{verdict:<12} {significance(won, len(decided))}")

    # Sanity check on the sign convention: home cover rate should sit near 50%
    decided_all = [p for p in priced if p["cover"] is not None]
    home_cover = sum(1 for p in decided_all if p["cover"] == "home") / len(decided_all)
    print(f"\n  sanity: home teams covered {home_cover:.1%} of {len(decided_all)} games "
          f"(near 50% means the spread sign is right)")


def z_against_coinflip(wins: int, total: int) -> float:
    """How many standard errors a win rate sits from 50%."""
    if total == 0:
        return 0.0
    return ((wins / total) - 0.5) / sqrt(0.25 / total)


def significance(wins: int, total: int) -> str:
    z = z_against_coinflip(wins, total)
    if abs(z) < 2:
        return f"noise (z={z:+.1f})"
    return f"significant (z={z:+.1f})"


def mean_pct(values) -> str:
    values = list(values)
    return f"{statistics.mean(values):.1%}" if values else "n/a"


def parse_seasons(value: str) -> List[int]:
    if "-" in value:
        start, end = value.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(value)]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", default="2021-2025")
    parser.add_argument("--db-path", default="nfl_schedule.db")
    args = parser.parse_args()

    spreads = load_spreads()
    rows: List[Dict[str, Any]] = []
    for season in parse_seasons(args.seasons):
        season_rows = await collect(season, args.db_path)
        rows.extend(season_rows)
        print(f"  {season}: {len(season_rows)} games")

    report_disagreement(rows)
    report_ats(rows, spreads)


if __name__ == "__main__":
    asyncio.run(main())

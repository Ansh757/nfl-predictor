"""
backtest_rotobot.py - Is Rotobot's score distribution honest?

The median score is the market's number by construction, so "how accurate is the
predicted score" mostly measures the market. What Rotobot adds is the shape, and
the shape is what this checks:

  * likelihood of the exact final score (the fitting objective)
  * CRPS of the margin and the total - how close the whole distribution was
  * coverage: does the 80% range contain the result 80% of the time?
  * key numbers: are margins of 3 and 7 as common as in real games?
  * win probability against the de-vigged moneyline - is anything lost?
  * cover / over probabilities - they should hover near 50%, because the
    simulation is centred on the line; a drift means the centre is wrong

Fit on 2021-2024, evaluate on 2025 and 2026 (held out):

    python backtest_rotobot.py --fit
    python backtest_rotobot.py --seasons 2025 2026

Inputs are closing lines from nflverse, fixed before kickoff, so nothing here
looks ahead.
"""
import argparse
import csv
import itertools
import math
import statistics
import time
from typing import Dict, List

from rotobot import score as rs
from utils.historical_odds import DEFAULT_CACHE, _download
from utils.odds_client import american_to_probability, remove_vig
import os

FIT_SEASONS = [2021, 2022, 2023, 2024]


def load_games(seasons: List[int], cache_path: str = DEFAULT_CACHE) -> List[Dict]:
    if not os.path.exists(cache_path):
        _download(cache_path)
    games = []
    with open(cache_path, newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("game_type") != "REG" or int(row["season"]) not in seasons:
                continue
            try:
                game = {
                    "season": int(row["season"]),
                    "week": int(row["week"]),
                    "home_team": row["home_team"],
                    "away_team": row["away_team"],
                    "home_score": int(row["home_score"]),
                    "away_score": int(row["away_score"]),
                    # nflverse spread is positive when home is favoured; flip to betting convention
                    "home_spread": -float(row["spread_line"]),
                    "total": float(row["total_line"]),
                }
            except (TypeError, ValueError):
                continue                      # unplayed, or no line
            try:
                home_p = american_to_probability(float(row["home_moneyline"]))
                away_p = american_to_probability(float(row["away_moneyline"]))
                game["market_home_win"] = remove_vig(home_p, away_p)
            except (TypeError, ValueError):
                game["market_home_win"] = None
            games.append(game)
    return games


def _crps(pmf: Dict[int, float], observed: int) -> float:
    """Continuous ranked probability score for a discrete distribution (lower is better)."""
    total, cumulative = 0.0, 0.0
    values = sorted(pmf)
    lo, hi = min(values[0], observed), max(values[-1], observed)
    for v in range(lo, hi + 1):
        cumulative += pmf.get(v, 0.0)
        step = 1.0 if v >= observed else 0.0
        total += (cumulative - step) ** 2
    return total


def mean_log_likelihood(games: List[Dict], **params) -> float:
    total = 0.0
    for g in games:
        dist = rs.simulate(rs.GameLine(g["home_spread"], g["total"]), **params)
        p = dist.joint.get((g["home_score"], g["away_score"]), 0.0)
        total += math.log(max(p, 1e-6))
    return total / len(games)


def fit(games: List[Dict]):
    grid = {
        "drives_mean": [10.0, 10.5, 11.0, 11.5, 12.0],
        "drives_sd": [0.0, 1.0, 2.0],
        "fg_per_td": [0.55, 0.70, 0.85, 1.00],
    }
    print(f"Fitting on {len(games)} games, {math.prod(len(v) for v in grid.values())} candidates")
    results = []
    started = time.time()
    for values in itertools.product(*grid.values()):
        params = dict(zip(grid.keys(), values))
        ll = mean_log_likelihood(games, **params)
        results.append((ll, params))
    results.sort(key=lambda r: r[0], reverse=True)
    print(f"done in {time.time() - started:.0f}s\n")
    print("Top candidates (mean log-likelihood of the exact final score):")
    for ll, params in results[:8]:
        print(f"  {ll:.4f}  {params}")
    return results[0][1]


def evaluate(games: List[Dict], label: str, **params):
    n = len(games)
    ll = crps_m = crps_t = 0.0
    cover = {"home": 0, "away": 0, "margin": 0, "total": 0}
    p3 = p7 = a3 = a7 = 0.0
    brier_sim = brier_mkt = 0.0
    mkt_n = 0
    cover_pred, cover_hit, over_pred, over_hit = [], [], [], []
    mae_median = mae_implied = 0.0

    for g in games:
        line = rs.GameLine(g["home_spread"], g["total"])
        dist = rs.simulate(line, **params)
        s = rs.summarize(dist, line)
        h, a = g["home_score"], g["away_score"]
        margin, total = h - a, h + a

        ll += math.log(max(dist.joint.get((h, a), 0.0), 1e-6))
        crps_m += _crps(dist.margin_pmf(), margin)
        crps_t += _crps(dist.total_pmf(), total)

        iv = s["interval"]
        cover["home"] += iv["home"][0] <= h <= iv["home"][1]
        cover["away"] += iv["away"][0] <= a <= iv["away"][1]
        cover["margin"] += iv["margin"][0] <= margin <= iv["margin"][1]
        cover["total"] += iv["total"][0] <= total <= iv["total"][1]

        mp = dist.margin_pmf()
        p3 += mp.get(3, 0) + mp.get(-3, 0)
        p7 += mp.get(7, 0) + mp.get(-7, 0)
        a3 += abs(margin) == 3
        a7 += abs(margin) == 7

        mae_median += abs(s["median"]["home"] - h) + abs(s["median"]["away"] - a)
        mae_implied += abs(line.home_points - h) + abs(line.away_points - a)

        if margin != 0:
            home_won = 1.0 if margin > 0 else 0.0
            p_home = s["probabilities"]["home_win"] / (1 - s["probabilities"]["tie"])
            brier_sim += (p_home - home_won) ** 2
            if g["market_home_win"] is not None:
                brier_mkt += (g["market_home_win"] - home_won) ** 2
                mkt_n += 1

        ats = margin + line.home_spread
        if ats != 0:
            cover_pred.append(s["probabilities"]["home_covers"])
            cover_hit.append(1.0 if ats > 0 else 0.0)
        if total != line.total:
            over_pred.append(s["probabilities"]["over"])
            over_hit.append(1.0 if total > line.total else 0.0)

    decided = sum(1 for g in games if g["home_score"] != g["away_score"])
    print(f"\n=== {label}: {n} games ===")
    print(f"  log-likelihood of exact score   {ll / n:.4f}")
    print(f"  CRPS margin / total             {crps_m / n:.2f} / {crps_t / n:.2f}")
    print(f"  80% interval coverage           home {cover['home'] / n:.1%}  away {cover['away'] / n:.1%}  "
          f"margin {cover['margin'] / n:.1%}  total {cover['total'] / n:.1%}")
    print(f"  margin of exactly 3             sim {p3 / n:.1%}  actual {a3 / n:.1%}")
    print(f"  margin of exactly 7             sim {p7 / n:.1%}  actual {a7 / n:.1%}")
    print(f"  team score MAE                  median {mae_median / (2 * n):.2f}  vs market implied {mae_implied / (2 * n):.2f}")
    print(f"  win-prob Brier                  sim {brier_sim / decided:.4f}  vs moneyline {brier_mkt / max(mkt_n, 1):.4f}")
    print(f"  P(home covers)                  mean {statistics.mean(cover_pred):.1%}  actual {statistics.mean(cover_hit):.1%}")
    print(f"  P(over)                         mean {statistics.mean(over_pred):.1%}  actual {statistics.mean(over_hit):.1%}")


def main():
    parser = argparse.ArgumentParser(description="Backtest Rotobot's score distribution.")
    parser.add_argument("--fit", action="store_true", help="Grid-search the drive parameters on 2021-2024")
    parser.add_argument("--seasons", type=int, nargs="+", default=[2025, 2026])
    args = parser.parse_args()

    params = {"drives_mean": rs.DRIVES_MEAN, "drives_sd": rs.DRIVES_SD, "fg_per_td": rs.FG_PER_TD}
    if args.fit:
        params = fit(load_games(FIT_SEASONS))
        evaluate(load_games(FIT_SEASONS), "2021-2024 (in-sample)", **params)

    print(f"\nParameters: {params}")
    for season in args.seasons:
        evaluate(load_games([season]), f"{season} (held out)", **params)


if __name__ == "__main__":
    main()

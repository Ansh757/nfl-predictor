"""
backtest_rotobot_pbp.py - Does the play-by-play engine earn its place?

It has to do three things the exact drive model (rotobot/score.py) and the
player layer (rotobot/players.py) cannot, without being worse at what they do:

  1. Score shape. Margins of exactly 3 and 7 at real rates (the drive model
     gave ~9% for 3 against ~15% real), win probability no worse than the
     market's, 80% ranges that hold 80%.
  2. Player points. Mean PPR error no worse than part 2's projections, and
     honest 80% ranges.
  3. Correlation - the reason to simulate. How much players' results move
     together in the simulation should match reality. Reality is measured
     across games on residuals (actual minus projection), so a good team's
     QB and WR both being good on average does not count as correlation; the
     simulation's figure is the within-game correlation of its own runs.

    python backtest_rotobot_pbp.py --seasons 2025 2026 --runs 1000 --workers 8

Point-in-time throughout: team play-by-play, player roles, injuries and
rosters all come from before kickoff, and the line is the closing line.
"""
import argparse
import math
import zlib
import multiprocessing as mp
import statistics
from collections import defaultdict
from typing import Dict, List, Optional

PAIRS = [("QB", "WR1"), ("QB", "WR2"), ("QB", "TE1"), ("QB", "RB1"), ("WR1", "WR2"), ("QB", "OPP_QB")]

_ctx = None


def _init():
    """Each worker loads its own context once."""
    global _ctx
    import json
    from backtest_rotobot_players import Context
    from rotobot.pbp.data import plays
    from rotobot.pbp.teams import TeamHistory, league_rates
    from rotobot import players as rp
    model = json.load(open("rotobot/pbp/league_model.json"))
    ctx = Context()
    history = TeamHistory(plays([2023, 2024, 2025, 2026]), model["pass_beta"])
    _ctx = {"ctx": ctx, "history": history, "league": league_rates(history), "model": model,
            "player_model": rp.load_model()}


def _roles_for(c, key, team_spread, implied, kickoff):
    """Part 2's projections for one team, plus the team line they were split from."""
    from rotobot import players as rp
    ctx, pm = c["ctx"], c["player_model"]
    season, week, team = key
    opp = ctx.ps.opponent[key]
    f_team = rp.team_features(ctx.ps, team, season, week, pm["league"])
    f_opp = rp.team_features(ctx.ps, opp, season, week, pm["league"])
    if not f_team or not f_opp:
        return None, None
    team_line = rp.team_projection(pm, f_team, f_opp, team_spread, implied)
    players = rp.project_players(ctx.ps, pm, ctx.index, team, season, week, team_line,
                                 ctx.out_ids(season, week, team, kickoff), ctx.rosters.eligible(season, week, team))
    return players, team_line


def _labels(players: List[Dict]) -> Dict[str, str]:
    """Role labels by projected volume: QB, WR1, WR2, TE1, RB1."""
    out = {}
    qb = [p for p in players if p["position"] == "QB" and p.get("starter")]
    if qb:
        out["QB"] = qb[0]["player_id"]
    wrs = sorted((p for p in players if p["position"] == "WR"), key=lambda p: -p["stats"]["targets"])
    for i, p in enumerate(wrs[:2]):
        out[f"WR{i + 1}"] = p["player_id"]
    tes = sorted((p for p in players if p["position"] == "TE"), key=lambda p: -p["stats"]["targets"])
    if tes:
        out["TE1"] = tes[0]["player_id"]
    rbs = sorted((p for p in players if p["position"] == "RB"), key=lambda p: -p["stats"]["carries"])
    if rbs:
        out["RB1"] = rbs[0]["player_id"]
    return out


def run_game(args):
    game_id, line, runs = args
    from rotobot.pbp.simulate import calibrate, roles_from_projection, simulate
    from rotobot.pbp.teams import build_side
    from rotobot.player_data import fantasy_points
    from rotobot import score as rs
    c = _ctx
    ctx = c["ctx"]
    season, week = int(game_id[:4]), int(game_id[5:7])
    home, away = line["home"], line["away"]
    keys = {"home": (season, week, home), "away": (season, week, away)}
    if any(k not in ctx.ps.team_totals for k in keys.values()):
        return None

    sides, projections, labels = {}, {}, {}
    for side, team in (("home", home), ("away", away)):
        spread = line["home_spread"] if side == "home" else -line["home_spread"]
        implied = line["home_points"] if side == "home" else line["away_points"]
        players, team_line = _roles_for(c, keys[side], spread, implied, line["kickoff"])
        if not players:
            return None
        s = build_side(c["history"], c["league"], team, season, week)
        s.qb, s.roles, s.positions = roles_from_projection(players, team_line)
        sides[side], projections[side], labels[side] = s, players, _labels(players)

    seed = zlib.crc32(game_id.encode())         # stable across processes, unlike hash()
    calibrate(c["model"], sides["home"], sides["away"], line["home_points"], line["away_points"], seed)
    sim = simulate(c["model"], sides["home"], sides["away"], seed, runs=runs,
                   home_spread=line["home_spread"], total=line["home_points"] + line["away_points"],
                   quantile_grid=c.get("grid", False))

    exact_line = rs.GameLine(line["home_spread"], line["home_points"] + line["away_points"])
    exact = rs.summarize(rs.simulate(exact_line), exact_line)

    actual_points = ctx.lines_scores.get(game_id)
    result = {"game_id": game_id, "season": season,
              "sim": {k: sim[k] for k in ("mean", "interval", "probabilities", "grid") if k in sim},
              "exact": {"probabilities": exact["probabilities"], "interval": exact["interval"]},
              "final": actual_points, "players": [], "labels": labels, "correlations": {}}

    by_pid = {p["player_id"]: p for p in sim["players"]}
    for side in ("home", "away"):
        actual = {r["player_id"]: fantasy_points(r) for r in ctx.ps.player_games.get(keys[side], [])}
        for proj in projections[side]:
            pid = proj["player_id"]
            s = by_pid.get(pid)
            if not s:
                continue
            result["players"].append({
                "player_id": pid, "position": proj["position"], "side": side,
                "projection": proj["fantasy"]["ppr"], "sim": s["ppr"], "grid": s.get("grid"),
                "actual": actual.get(pid), "played": pid in actual,
            })
    # Within-game simulated correlation for each role pair
    sim_corr = {}
    for side in ("home", "away"):
        lab = labels[side]
        other = labels["away" if side == "home" else "home"]
        for a, b in PAIRS:
            pa = lab.get(a)
            pb = other.get("QB") if b == "OPP_QB" else lab.get(b)
            if pa and pb and pa in by_pid and pb in by_pid:
                key = "opposing_qb" if b == "OPP_QB" else None
                if b == "OPP_QB":
                    value = by_pid[pa]["correlation"]["opposing_qb"]
                elif a == "QB":
                    value = by_pid[pb]["correlation"]["own_qb"]
                else:
                    value = next((t["correlation"] for t in sim["teammate_correlations"]
                                  if {t["a"], t["b"]} == {pa, pb}), None)
                if value is not None:
                    sim_corr.setdefault(f"{a}-{b}", []).append(value)
    result["correlations"] = sim_corr
    return result


def report(results: List[Dict], label: str):
    results = [r for r in results if r and r["final"]]
    n = len(results)
    print(f"\n=== {label}: {n} games ===")

    # 1. Score shape
    cover = defaultdict(int)
    brier = {"sim": 0.0, "exact": 0.0}
    decided = 0
    m3 = {"sim": 0.0, "exact_n": 0.0, "actual": 0}
    m7 = {"sim": 0.0, "actual": 0}
    for r in results:
        h, a = r["final"]
        iv = r["sim"]["interval"]
        cover["team"] += (iv["home"][0] <= h <= iv["home"][1]) + (iv["away"][0] <= a <= iv["away"][1])
        cover["margin"] += iv["margin"][0] <= h - a <= iv["margin"][1]
        cover["total"] += iv["total"][0] <= h + a <= iv["total"][1]
        if h != a:
            decided += 1
            won = 1.0 if h > a else 0.0
            ps, pe = r["sim"]["probabilities"], r["exact"]["probabilities"]
            brier["sim"] += (ps["home_win"] / max(1 - ps["tie"], 1e-9) - won) ** 2
            brier["exact"] += (pe["home_win"] / max(1 - pe["tie"], 1e-9) - won) ** 2
        m3["sim"] += r["sim"]["probabilities"]["margin_3"]
        m3["actual"] += abs(h - a) == 3
        m7["sim"] += r["sim"]["probabilities"]["margin_7"]
        m7["actual"] += abs(h - a) == 7
    print(f"  score 80% coverage    team {cover['team'] / (2 * n):.1%}  margin {cover['margin'] / n:.1%}  total {cover['total'] / n:.1%}")
    print(f"  win-prob Brier        play-by-play {brier['sim'] / decided:.4f}  exact drive model {brier['exact'] / decided:.4f}")
    print(f"  margin of exactly 3   sim {m3['sim'] / n:.1%}  actual {m3['actual'] / n:.1%}  (drive model ~9%)")
    print(f"  margin of exactly 7   sim {m7['sim'] / n:.1%}  actual {m7['actual'] / n:.1%}")

    # 2. Player points
    by_pos = defaultdict(lambda: {"sim": [], "proj": [], "cov": 0, "n": 0})
    for r in results:
        for p in r["players"]:
            if not p["played"] or p["position"] not in ("QB", "RB", "WR", "TE"):
                continue
            b = by_pos[p["position"]]
            b["n"] += 1
            b["sim"].append(abs(p["sim"]["mean"] - p["actual"]))
            b["proj"].append(abs(p["projection"] - p["actual"]))
            b["cov"] += p["sim"]["p10"] <= p["actual"] <= p["sim"]["p90"]
    print(f"  {'pos':4} {'n':>5} {'MAE sim':>8} {'MAE part 2':>10} {'sim 80% range':>14}")
    for pos in ("QB", "RB", "WR", "TE"):
        b = by_pos[pos]
        if b["n"]:
            print(f"  {pos:4} {b['n']:5} {statistics.fmean(b['sim']):8.2f} {statistics.fmean(b['proj']):10.2f} {b['cov'] / b['n']:14.1%}")

    # 3. Correlation: simulated within-game vs real across-game residuals
    print(f"  {'pair':10} {'sim (avg within game)':>22} {'real (residuals)':>17} {'n':>5}")
    for a, b in PAIRS:
        key = f"{a}-{b}"
        sims = [v for r in results for v in r["correlations"].get(key, [])]
        xs, ys = [], []
        for r in results:
            res = {p["player_id"]: p["actual"] - p["projection"] for p in r["players"] if p["played"]}
            for side in ("home", "away"):
                lab = r["labels"][side]
                other = r["labels"]["away" if side == "home" else "home"]
                pa = lab.get(a)
                pb = other.get("QB") if b == "OPP_QB" else lab.get(b)
                if pa in res and pb in res and (b != "OPP_QB" or side == "home"):
                    xs.append(res[pa])
                    ys.append(res[pb])
        real = statistics.correlation(xs, ys) if len(xs) > 10 else float("nan")
        sim_avg = statistics.fmean(sims) if sims else float("nan")
        print(f"  {key:10} {sim_avg:22.3f} {real:17.3f} {len(xs):5}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", type=int, nargs="+", default=[2025])
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=max(mp.cpu_count() - 1, 1))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fit-intervals", action="store_true",
                        help="On the given (fitting) season, find the quantile level per quantity that holds 80%%, "
                             "and write it with --form-sd into rotobot/pbp/league_model.json")
    parser.add_argument("--form-sd", type=float, default=None,
                        help="Override the model's per-game form spread (tune on 2024, never on held-out seasons)")
    args = parser.parse_args()

    from backtest_rotobot_players import load_lines
    import csv
    from utils.historical_odds import DEFAULT_CACHE
    lines = load_lines()
    scores = {}
    with open(DEFAULT_CACHE, newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("home_score") not in ("", "NA", None) and row.get("game_type") == "REG":
                scores[row["game_id"]] = (int(row["home_score"]), int(row["away_score"]))

    for season in args.seasons:
        jobs = [(gid, line, args.runs) for gid, line in sorted(lines.items())
                if gid.startswith(f"{season}_") and gid in scores]
        if args.limit:
            jobs = jobs[:args.limit]
        with mp.get_context("fork").Pool(args.workers, initializer=_init_with_scores,
                                         initargs=(scores, args.form_sd, args.fit_intervals)) as pool:
            results = pool.map(run_game, jobs, chunksize=2)
        if args.fit_intervals:
            fit_intervals(results, args.form_sd)
        else:
            report(results, f"{season} (held out)")


def _init_with_scores(scores, form_sd=None, grid=False):
    _init()
    _ctx["ctx"].lines_scores = scores
    _ctx["grid"] = grid
    if form_sd is not None:
        _ctx["model"]["form_sd"] = form_sd
    if grid:
        # Fitting the levels must start from raw quantiles
        _ctx["model"]["interval_levels"] = {}


def fit_intervals(results: List[Dict], form_sd: Optional[float]):
    """Pick, per quantity, the quantile level whose range held closest to 80%."""
    import json
    results = [r for r in results if r and r["final"]]
    hits = defaultdict(lambda: defaultdict(int))
    counts = defaultdict(int)
    for r in results:
        h, a = r["final"]
        actual = {"home": h, "away": a, "margin": h - a, "total": h + a}
        for lv, bands in r["sim"]["grid"].items():
            for q in ("home", "away"):
                hits["team"][lv] += bands[q][0] <= actual[q] <= bands[q][1]
            for q in ("margin", "total"):
                hits[q][lv] += bands[q][0] <= actual[q] <= bands[q][1]
        counts["team"] += 2
        counts["margin"] += 1
        counts["total"] += 1
        for p in r["players"]:
            if not p["played"] or not p["grid"] or p["position"] not in ("QB", "RB", "WR", "TE"):
                continue
            counts[p["position"]] += 1
            for lv, (lo, hi) in p["grid"].items():
                hits[p["position"]][lv] += lo <= p["actual"] <= hi
    levels = {}
    print("Coverage by nominal level (target 80%):")
    for key in ("team", "margin", "total", "QB", "RB", "WR", "TE"):
        cov = {lv: hits[key][lv] / counts[key] for lv in hits[key]}
        best = min(cov, key=lambda lv: abs(cov[lv] - 0.8))
        levels[key] = float(best)
        print(f"  {key:6} n={counts[key]:5}  chosen {best} -> {cov[best]:.1%}   "
              f"(raw 0.80 -> {cov.get('0.80', float('nan')):.1%})")
    path = "rotobot/pbp/league_model.json"
    with open(path) as handle:
        model = json.load(handle)
    model["interval_levels"] = levels
    if form_sd is not None:
        model["form_sd"] = form_sd
    with open(path, "w") as handle:
        json.dump(model, handle, separators=(",", ":"))
    print(f"wrote interval_levels and form_sd={model.get('form_sd')} to {path}")


if __name__ == "__main__":
    main()

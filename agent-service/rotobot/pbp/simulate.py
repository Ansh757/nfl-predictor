"""
simulate.py - Calibrate a matchup to the market, play it 10,000 times, summarise.

Calibration. Team adjustments (teams.py) say how each side plays; the market says
how many points each should expect. One efficiency multiplier per offence -
scaling its yards, completion rate, and (inversely) its sacks, interceptions and
fumbles - is solved so the average simulated score matches the market's implied
points for both teams. Points respond to efficiency with an elasticity of about
2.1 (measured: 0.9 -> 17.3 points, 1.1 -> 26.6), which is the step size used.
Each iteration replays the same seeded games, so the only thing that changes
between them is the efficiency - the solve converges in a few steps instead of
chasing noise.

Simulation. The calibrated game is played RUNS times from a seed derived from the
game, so the same inputs always give the same answer. Every run produces a full
box score; the summary reports distributions, and - the reason to simulate at
all - how players' outcomes move together.
"""
import random
import statistics
from typing import Dict, List, Optional, Tuple

from rotobot.pbp.engine import (ATT, CAR, FUM, INT, PASSTD, PASSYD, REC, RECTD, RECYD, RUSHTD, RUSHYD, TGT,
                                Game, Role, Side)

RUNS = 10_000
CALIBRATION_RUNS = 800
CALIBRATION_STEPS = 5
ELASTICITY = 2.1
EFFICIENCY_RANGE = (0.6, 1.6)


def ppr(s: List[float], reception_points: float = 1.0) -> float:
    return (0.04 * s[PASSYD] + 4 * s[PASSTD] - 2 * s[INT] + 0.1 * (s[RUSHYD] + s[RECYD])
            + 6 * (s[RUSHTD] + s[RECTD]) + reception_points * s[REC] - 2 * s[FUM])


def calibrate(model: Dict, home: Side, away: Side, home_points: float, away_points: float,
              seed: int) -> Tuple[float, float, List[float]]:
    targets = (max(home_points, 3.0), max(away_points, 3.0))
    eff = [1.0, 1.0]
    achieved = [0.0, 0.0]
    for _ in range(CALIBRATION_STEPS):
        home.efficiency, away.efficiency = eff
        rng = random.Random(seed)
        totals = [0.0, 0.0]
        for _ in range(CALIBRATION_RUNS):
            box, _ = Game(model, home, away, rng).play()
            totals[0] += box[0]["points"]
            totals[1] += box[1]["points"]
        achieved = [t / CALIBRATION_RUNS for t in totals]
        for i in (0, 1):
            ratio = targets[i] / max(achieved[i], 0.5)
            eff[i] = min(max(eff[i] * ratio ** (1 / ELASTICITY), EFFICIENCY_RANGE[0]), EFFICIENCY_RANGE[1])
    home.efficiency, away.efficiency = eff
    return eff[0], eff[1], achieved


def _q(sorted_values: List[float], q: float) -> float:
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))]


def _corr(a: List[float], b: List[float]) -> Optional[float]:
    if len(a) < 3:
        return None
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    return round(cov / (va * vb) ** 0.5, 3) if va > 0 and vb > 0 else None


LEVEL_GRID = [round(0.66 + 0.02 * i, 2) for i in range(14)]   # 0.66 .. 0.92


def _band(sorted_values: List[float], level: float) -> List[float]:
    return [_q(sorted_values, (1 - level) / 2), _q(sorted_values, 1 - (1 - level) / 2)]


def simulate(model: Dict, home: Side, away: Side, seed: int, runs: int = RUNS,
             home_spread: Optional[float] = None, total: Optional[float] = None,
             quantile_grid: bool = False) -> Dict:
    """`quantile_grid` adds each range at a grid of levels - only the backtest needs it,
    to find the level that really holds 80% (see backtest_rotobot_pbp.py --fit-intervals)."""
    rng = random.Random(seed + 1)
    scores: List[Tuple[int, int]] = []
    team_stats = [{k: 0.0 for k in ("pass_att", "completions", "pass_yds", "carries", "rush_yds",
                                    "sacks", "int", "turnovers", "punts", "fg_att", "plays")} for _ in (0, 1)]
    ids = [[r.player_id for r in s.roles] + ([s.qb] if s.qb and s.qb not in [r.player_id for r in s.roles] else [])
           for s in (home, away)]
    points = [{pid: [] for pid in ids[i]} for i in (0, 1)]
    stat_sums = [{pid: [0.0] * 12 for pid in ids[i]} for i in (0, 1)]
    overtime = 0

    for _ in range(runs):
        game = Game(model, home, away, rng)
        box, players = game.play()
        overtime += game.overtime
        scores.append((box[0]["points"], box[1]["points"]))
        for i in (0, 1):
            for k in team_stats[i]:
                team_stats[i][k] += box[i][k]
            for pid in ids[i]:
                s = players[i].get(pid)
                if s is None:
                    points[i][pid].append(0.0)
                    continue
                points[i][pid].append(ppr(s))
                acc = stat_sums[i][pid]
                for j in range(12):
                    acc[j] += s[j]

    levels = model.get("interval_levels", {})
    return _summarise(home, away, scores, team_stats, points, stat_sums, runs, overtime, home_spread, total,
                      levels, quantile_grid)


def _summarise(home, away, scores, team_stats, points, stat_sums, runs, overtime, home_spread, total,
               levels, quantile_grid) -> Dict:
    """Ranges are reported as 80%. The quantiles behind them are the ones that held
    80% of real results on 2024 (`interval_levels` in the model), per quantity and
    position - the same calibration as the exact score model's CALIBRATED_LEVELS."""
    level = lambda key: levels.get(key, 0.8)
    hs = sorted(h for h, _ in scores)
    as_ = sorted(a for _, a in scores)
    margins = [h - a for h, a in scores]
    totals = sorted(h + a for h, a in scores)
    counts: Dict[Tuple[int, int], int] = {}
    for sc in scores:
        counts[sc] = counts.get(sc, 0) + 1

    out = {
        "runs": runs,
        "efficiency": {"home": round(home.efficiency, 3), "away": round(away.efficiency, 3)},
        "mean": {"home": round(statistics.fmean(hs), 2), "away": round(statistics.fmean(as_), 2)},
        "median": {"home": _q(hs, 0.5), "away": _q(as_, 0.5)},
        "interval": {
            "level": 0.8,
            "home": _band(hs, level("team")),
            "away": _band(as_, level("team")),
            "margin": _band(sorted(margins), level("margin")),
            "total": _band(totals, level("total")),
        },
        "probabilities": {
            "home_win": round(sum(m > 0 for m in margins) / runs, 4),
            "away_win": round(sum(m < 0 for m in margins) / runs, 4),
            "tie": round(sum(m == 0 for m in margins) / runs, 4),
            "overtime": round(overtime / runs, 4),
            "margin_3": round(sum(abs(m) == 3 for m in margins) / runs, 4),
            "margin_7": round(sum(abs(m) == 7 for m in margins) / runs, 4),
        },
        "most_common_scores": [{"home": h, "away": a, "probability": round(c / runs, 4)}
                               for (h, a), c in sorted(counts.items(), key=lambda kv: -kv[1])[:5]],
        "team_stats": [{k: round(v / runs, 2) for k, v in team_stats[i].items()} for i in (0, 1)],
    }
    if quantile_grid:
        sm = sorted(margins)
        out["grid"] = {f"{lv:.2f}": {"home": _band(hs, lv), "away": _band(as_, lv), "margin": _band(sm, lv),
                                     "total": _band(totals, lv)} for lv in LEVEL_GRID}
    if home_spread is not None:
        out["probabilities"]["home_covers"] = round(sum(m + home_spread > 0 for m in margins) / runs, 4)
    if total is not None:
        out["probabilities"]["over"] = round(sum(t > total for t in totals) / runs, 4)

    team_points = [[h for h, _ in scores], [a for _, a in scores]]
    sides = (home, away)
    players_out = []
    for i in (0, 1):
        qb = sides[i].qb
        qb_points = points[i].get(qb) if qb else None
        opp_qb = sides[1 - i].qb
        for pid, pts in points[i].items():
            ordered = sorted(pts)
            sums = stat_sums[i][pid]
            position = sides[i].positions.get(pid) if sides[i].positions else None
            lo, hi = _band(ordered, level(position or "player"))
            entry = {
                "player_id": pid, "side": "home" if i == 0 else "away",
                # p10 / p90 are the bounds of the calibrated 80% range, not raw percentiles
                "ppr": {"mean": round(statistics.fmean(pts), 2), "p10": round(lo, 1),
                        "p50": round(_q(ordered, 0.5), 1), "p90": round(hi, 1)},
                "stats": {name: round(sums[idx] / runs, 2) for name, idx in (
                    ("targets", TGT), ("receptions", REC), ("receiving_yards", RECYD), ("receiving_tds", RECTD),
                    ("carries", CAR), ("rushing_yards", RUSHYD), ("rushing_tds", RUSHTD), ("attempts", ATT),
                    ("passing_yards", PASSYD), ("passing_tds", PASSTD), ("passing_interceptions", INT))},
                "correlation": {
                    "team_points": _corr(pts, team_points[i]),
                    "own_qb": _corr(pts, qb_points) if qb_points and pid != qb else None,
                    "opposing_qb": _corr(pts, points[1 - i].get(opp_qb)) if opp_qb and points[1 - i].get(opp_qb) else None,
                },
            }
            if quantile_grid:
                entry["grid"] = {f"{lv:.2f}": _band(ordered, lv) for lv in LEVEL_GRID}
            players_out.append(entry)
    out["players"] = players_out
    out["stacks"] = _stacks(sides, points)
    # Teammates, pairwise: the six most productive per side
    out["teammate_correlations"] = []
    for i in (0, 1):
        top = sorted(points[i], key=lambda pid: -statistics.fmean(points[i][pid]))[:6]
        for x in range(len(top)):
            for y in range(x + 1, len(top)):
                out["teammate_correlations"].append(
                    {"a": top[x], "b": top[y], "correlation": _corr(points[i][top[x]], points[i][top[y]])})
    return out


def _stacks(sides, points) -> List[Dict]:
    """Each QB with his top pass catchers: how often both have a big day together."""
    stacks = []
    for i in (0, 1):
        qb = sides[i].qb
        if not qb or qb not in points[i]:
            continue
        catchers = sorted((r for r in sides[i].roles if r.target > 0 and r.player_id != qb),
                          key=lambda r: -r.target)[:3]
        q = points[i][qb]
        q_line = sorted(q)[len(q) // 2]
        for r in catchers:
            w = points[i][r.player_id]
            w_line = sorted(w)[len(w) // 2]
            both = sum(1 for a, b in zip(q, w) if a > q_line and b > w_line) / len(q)
            stacks.append({
                "qb": qb, "player_id": r.player_id, "correlation": _corr(q, w),
                # Both beating their own medians: 25% if independent, more if they move together
                "both_above_median": round(both, 4),
            })
    return stacks


def roles_from_projection(players: List[Dict], team_line: Dict[str, float]) -> Tuple[Optional[str], List[Role], Dict[str, str]]:
    """Turn part 2's player projections into the shares the engine draws from."""
    qb = next((p["player_id"] for p in players if p["position"] == "QB" and p.get("starter")), None)
    targets = max(team_line.get("targets", 0.0), 1e-6)
    carries = max(team_line.get("carries", 0.0), 1e-6)
    rush_tds = sum(p["stats"]["rushing_tds"] for p in players) or 1e-6
    team_catch = team_line.get("completions", 0.0) / targets if targets > 1e-6 else 0.65
    team_ypc_pass = team_line.get("passing_yards", 0.0) / max(team_line.get("completions", 0.0), 1e-6)
    team_ypc_run = team_line.get("rushing_yards", 0.0) / carries

    roles = []
    for p in players:
        s = p["stats"]
        carry = s["carries"]
        if p["player_id"] == qb:
            # About half of a quarterback's carries are scrambles, which the
            # engine already gives him on pass plays
            carry *= 0.5
        catch = s["receptions"] / s["targets"] if s["targets"] > 0.05 else team_catch
        ypt = s["receiving_yards"] / s["receptions"] if s["receptions"] > 0.05 else team_ypc_pass
        ypc = s["rushing_yards"] / s["carries"] if s["carries"] > 0.05 else team_ypc_run
        roles.append(Role(
            player_id=p["player_id"],
            target=s["targets"] / targets,
            carry=carry / carries,
            goal_line=s["rushing_tds"] / rush_tds,
            catch_rel=min(max(catch / team_catch, 0.6), 1.4) if team_catch else 1.0,
            ypt_rel=min(max(ypt / team_ypc_pass, 0.5), 2.0) if team_ypc_pass else 1.0,
            ypc_rel=min(max(ypc / team_ypc_run, 0.5), 2.0) if team_ypc_run else 1.0,
        ))
    positions = {p["player_id"]: p["position"] for p in players}
    return qb, roles, positions

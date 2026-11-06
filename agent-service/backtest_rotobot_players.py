"""
backtest_rotobot_players.py - Do Rotobot's fantasy projections beat a season average?

That is the bar. Anyone can project a player at what he has averaged; a model
only earns its place if it does better, on games it was not fitted on.

    python backtest_rotobot_players.py --fit              # fit on 2021-2024, write rotobot/player_model.json
    python backtest_rotobot_players.py --seasons 2025 2026

Point-in-time throughout: a game sees player stats from games that kicked off
before it, the closing line (fixed before kickoff), and the injury report as it
stood before kickoff. Evaluation covers players who were projected and played;
the ones the model missed or wrongly projected are counted separately rather
than quietly dropped.

Baselines, both point-in-time:
  * season average - PPR points per game this season, or last season before
    the player's first game
  * recent average - PPR points per game over his last 8 games
"""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set, Tuple
from zoneinfo import ZoneInfo

from rotobot import players as rp
from rotobot.player_data import PlayerStats, fantasy_points
from rotobot.rosters import Rosters
from utils.historical_injuries import HistoricalInjuryLookup
from utils.historical_odds import DEFAULT_CACHE, NFLVERSE_TEAM_NAMES

FIT_SEASONS = [2021, 2022, 2023, 2024]
POSITIONS = ("QB", "RB", "WR", "TE")
RANGE_STATS = {
    "QB": ("ppr", "passing_yards"),
    "RB": ("ppr", "rushing_yards", "receptions"),
    "WR": ("ppr", "receiving_yards", "receptions"),
    "TE": ("ppr", "receiving_yards", "receptions"),
}
OUT_STATUSES = {"out", "doubtful"}
EASTERN = ZoneInfo("America/New_York")


def load_lines() -> Dict[str, Dict]:
    lines = {}
    with open(DEFAULT_CACHE, newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                spread, total = float(row["spread_line"]), float(row["total_line"])
            except (TypeError, ValueError):
                continue
            kickoff = None
            if row.get("gameday") and row.get("gametime"):
                kickoff = datetime.fromisoformat(f"{row['gameday']}T{row['gametime']}").replace(tzinfo=EASTERN)
            lines[row["game_id"]] = {
                "home": row["home_team"], "away": row["away_team"],
                # nflverse: spread positive when home is favoured
                "home_points": total / 2 + spread / 2, "away_points": total / 2 - spread / 2,
                "home_spread": -spread, "kickoff": kickoff,
            }
    return lines


class Context:
    """Everything a projection needs, loaded once."""

    def __init__(self):
        self.ps = PlayerStats(range(2020, 2027))
        self.index = rp.player_index(self.ps)
        self.lines = load_lines()
        self.injuries = {s: HistoricalInjuryLookup(s) for s in range(2021, 2027)}
        self.rosters = Rosters(range(2021, 2027))

    def team_games(self, seasons: List[int]):
        """Regular-season team-games with a line, as (key, team spread, implied points)."""
        for key in sorted(self.ps.team_totals):
            season, week, team = key
            if season not in seasons or self.ps.season_type.get((season, week)) != "REG":
                continue
            line = self.lines.get(self.ps.game_id.get(key))
            if not line:
                continue
            home = team == line["home"]
            yield key, (line["home_spread"] if home else -line["home_spread"]), \
                (line["home_points"] if home else line["away_points"]), line["kickoff"]

    def out_ids(self, season: int, week: int, team: str, kickoff) -> Set[str]:
        lookup = self.injuries.get(season)
        if not lookup:
            return set()
        entries = lookup.for_team_week(week, NFLVERSE_TEAM_NAMES.get(team, team), before=kickoff)
        return {e["player_id"] for e in entries if e["player_id"] and e["status"].lower() in OUT_STATUSES}

    def project(self, model, key, team_spread, implied, kickoff) -> List[Dict]:
        season, week, team = key
        opp = self.ps.opponent[key]
        f_team = rp.team_features(self.ps, team, season, week, model["league"])
        f_opp = rp.team_features(self.ps, opp, season, week, model["league"])
        if not f_team or not f_opp:
            return []
        team_line = rp.team_projection(model, f_team, f_opp, team_spread, implied)
        return rp.project_players(self.ps, model, self.index, team, season, week, team_line,
                                  self.out_ids(season, week, team, kickoff),
                                  self.rosters.eligible(season, week, team))


# --- Fitting -------------------------------------------------------------------

def _solve(xtx: List[List[float]], xty: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting; a 5x5 system needs nothing more."""
    n = len(xty)
    a = [row[:] + [xty[i]] for i, row in enumerate(xtx)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(n):
            if r != col:
                f = a[r][col] / a[col][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col])]
    return [a[i][n] / a[i][i] for i in range(n)]


def fit(ctx: Context) -> Dict:
    fit_keys = [k for k in ctx.ps.team_totals
                if k[0] in FIT_SEASONS and ctx.ps.season_type.get((k[0], k[1])) == "REG"]
    league = {stat: statistics.mean(ctx.ps.team_totals[k][stat] for k in fit_keys) for stat in rp.TEAM_STATS}

    position_rates = {}
    for pos in ("QB", "RB", "FB", "WR", "TE"):
        rows = [r for k in fit_keys for r in ctx.ps.player_games[k] if r["position"] == pos]
        s = lambda f: sum(r[f] for r in rows)
        touches = s("carries") + s("receptions")
        position_rates[pos] = {
            "ypt": s("receiving_yards") / max(s("targets"), 1),
            "catch": s("receptions") / max(s("targets"), 1),
            "rec_td": s("receiving_tds") / max(s("targets"), 1),
            "ypc": s("rushing_yards") / max(s("carries"), 1),
            "rush_td": s("rushing_tds") / max(s("carries"), 1),
            "fumble": (s("rushing_fumbles_lost") + s("receiving_fumbles_lost")) / max(touches, 1),
        }
    model = {"league": league, "position_rates": position_rates, "team": {}, "ranges": {}}

    # Team layer: one least-squares fit per stat
    rows = []
    for key, team_spread, implied, _ in ctx.team_games(FIT_SEASONS):
        season, week, team = key
        f_team = rp.team_features(ctx.ps, team, season, week, league)
        f_opp = rp.team_features(ctx.ps, ctx.ps.opponent[key], season, week, league)
        if f_team and f_opp:
            rows.append((key, f_team, f_opp, team_spread, implied))
    print(f"Team layer: {len(rows)} team-games")
    for stat in rp.TEAM_STATS:
        xs = [[1.0, ft["offence"][stat], fo["defence"][stat], sp, imp] for _, ft, fo, sp, imp in rows]
        ys = [ctx.ps.team_totals[key][stat] for key, *_ in rows]
        xtx = [[sum(x[i] * x[j] for x in xs) + (1e-6 if i == j else 0) for j in range(5)] for i in range(5)]
        xty = [sum(x[i] * y for x, y in zip(xs, ys)) for i in range(5)]
        model["team"][stat] = _solve(xtx, xty)
        pred = [sum(b * v for b, v in zip(model["team"][stat], x)) for x in xs]
        naive = [ft["offence"][stat] for _, ft, *_ in rows]
        mae = statistics.mean(abs(p - y) for p, y in zip(pred, ys))
        mae_naive = statistics.mean(abs(p - y) for p, y in zip(naive, ys))
        print(f"  {stat:22} MAE {mae:7.2f}  (recent average {mae_naive:7.2f})  "
              f"beta {[round(b, 3) for b in model['team'][stat]]}")

    # How much of a missing player's share reaches the players still projected
    print("Redistribution of vacated share (PPR MAE, projected players who played, 2021-2024):")
    best = None
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        model["redistribute"] = fraction
        errors = [abs(p["fantasy"]["ppr"] - a["ppr"]) for p, a in _matched(ctx, model, FIT_SEASONS)]
        mae = statistics.mean(errors)
        print(f"  {fraction:.2f}  {mae:.4f}  ({len(errors)} player-games)")
        if best is None or mae < best[1]:
            best = (fraction, mae)
    model["redistribute"] = best[0]

    # Ranges: in-sample residual quantiles, scaled by sqrt(projection + 1)
    resid = defaultdict(list)
    for proj, actual in _matched(ctx, model, FIT_SEASONS):
        pos = proj["position"]
        for stat in RANGE_STATS.get(pos, ()):
            p = proj["fantasy"]["ppr"] if stat == "ppr" else proj["stats"][stat]
            a = actual["ppr"] if stat == "ppr" else actual[stat]
            resid[(pos, stat)].append((a - p) / (max(p, 0) + 1) ** 0.5)
    for (pos, stat), zs in resid.items():
        zs.sort()
        q = lambda f: zs[min(len(zs) - 1, int(f * len(zs)))]
        model["ranges"].setdefault(pos, {})[stat] = [round(q(0.10), 4), round(q(0.90), 4)]
    model["ranges"]["FB"] = model["ranges"]["RB"]
    return model


def _matched(ctx: Context, model, seasons):
    """(projection, actual) for every projected player who played."""
    for key, team_spread, implied, kickoff in ctx.team_games(seasons):
        actual = {r["player_id"]: r for r in ctx.ps.player_games[key]}
        for proj in ctx.project(model, key, team_spread, implied, kickoff):
            row = actual.get(proj["player_id"])
            if row:
                yield proj, {**row, "ppr": fantasy_points(row)}


# --- Evaluation ----------------------------------------------------------------

def _baselines(ctx: Context, pid: str, season: int, week: int) -> Tuple[float, float]:
    games = [g for g in ctx.index.get(pid, []) if (g[0], g[1]) < (season, week)
             and ctx.ps.season_type.get((g[0], g[1])) == "REG"]
    points = {g: fantasy_points(next(r for r in ctx.ps.player_games[g] if r["player_id"] == pid)) for g in games}
    this_season = [p for g, p in points.items() if g[0] == season]
    last_season = [p for g, p in points.items() if g[0] == season - 1]
    season_avg = statistics.mean(this_season or last_season) if (this_season or last_season) else None
    recent = [points[g] for g in games[-8:]]
    recent_avg = statistics.mean(recent) if recent else None
    return season_avg, recent_avg


def _spearman(a: List[float], b: List[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for rank, i in enumerate(order):
            r[i] = rank
        return r
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def evaluate(ctx: Context, model: Dict, season: int):
    by_pos = defaultdict(lambda: {"model": [], "season": [], "recent": [], "covered": 0, "n": 0})
    # The same, counting a projected player who then did not play as zero points
    strict = defaultdict(lambda: {"model": [], "season": []})
    weekly = defaultdict(lambda: defaultdict(list))        # (week, pos) -> lists for rank correlation
    projected_not_played = played_not_projected = 0
    missed_points = 0.0
    phantom = []                   # projected PPR of players who then did not play

    for key, team_spread, implied, kickoff in ctx.team_games([season]):
        projections = [rp.with_ranges([p], model)[0] for p in ctx.project(model, key, team_spread, implied, kickoff)]
        projected = {p["player_id"]: p for p in projections}
        actual = {r["player_id"]: r for r in ctx.ps.player_games[key] if r["position"] in POSITIONS}
        for pid, proj in projected.items():
            if pid not in actual:
                projected_not_played += 1
                phantom.append(proj["fantasy"]["ppr"])
                season_avg, _ = _baselines(ctx, pid, key[0], key[1])
                if season_avg is not None and proj["position"] in POSITIONS:
                    strict[proj["position"]]["model"].append(proj["fantasy"]["ppr"])
                    strict[proj["position"]]["season"].append(season_avg)
        for pid, row in actual.items():
            pts = fantasy_points(row)
            proj = projected.get(pid)
            if proj is None:
                if pts >= 5:
                    played_not_projected += 1
                    missed_points += pts
                continue
            season_avg, recent_avg = _baselines(ctx, pid, key[0], key[1])
            if season_avg is None:
                continue
            pos = row["position"]
            b = by_pos[pos]
            b["n"] += 1
            b["model"].append(abs(proj["fantasy"]["ppr"] - pts))
            b["season"].append(abs(season_avg - pts))
            strict[pos]["model"].append(abs(proj["fantasy"]["ppr"] - pts))
            strict[pos]["season"].append(abs(season_avg - pts))
            b["recent"].append(abs(recent_avg - pts))
            lo, hi = proj["ranges"]["ppr"]
            b["covered"] += lo <= pts <= hi
            w = weekly[(key[1], pos)]
            w["model"].append(proj["fantasy"]["ppr"])
            w["season"].append(season_avg)
            w["actual"].append(pts)

    print(f"\n=== {season} (held out) ===")
    print(f"  {'pos':4} {'n':>5}  {'MAE model':>9} {'season avg':>10} {'recent avg':>10}  {'vs season':>9}  "
          f"{'rank corr model / season':>24}  {'80% range':>9}")
    for pos in POSITIONS:
        b = by_pos[pos]
        if not b["n"]:
            continue
        m, s, r = (statistics.mean(b[k]) for k in ("model", "season", "recent"))
        rho_m = [_spearman(w["model"], w["actual"]) for (wk, p), w in weekly.items() if p == pos]
        rho_s = [_spearman(w["season"], w["actual"]) for (wk, p), w in weekly.items() if p == pos]
        rho_m = statistics.mean(x for x in rho_m if x == x)
        rho_s = statistics.mean(x for x in rho_s if x == x)
        print(f"  {pos:4} {b['n']:5}  {m:9.2f} {s:10.2f} {r:10.2f}  {(m - s) / s:+9.1%}  "
              f"{rho_m:11.3f} / {rho_s:.3f}  {b['covered'] / b['n']:9.1%}")
    print("  counting projected players who did not play as zero:")
    for pos in POSITIONS:
        st = strict[pos]
        if st["model"]:
            m, sa = statistics.mean(st["model"]), statistics.mean(st["season"])
            print(f"    {pos:4} {len(st['model']):5}  MAE model {m:.2f}  season avg {sa:.2f}  {(m - sa) / sa:+.1%}")
    big = sum(1 for x in phantom if x >= 8)
    summary = {pos: {"model": statistics.mean(by_pos[pos]["model"]),
                     "season": statistics.mean(by_pos[pos]["season"]),
                     "coverage": by_pos[pos]["covered"] / by_pos[pos]["n"]}
               for pos in POSITIONS if by_pos[pos]["n"]}
    print(f"  projected but did not play: {projected_not_played} "
          f"(median projection {statistics.median(phantom):.1f} PPR; {big} projected at 8+)")
    print(f"  played (5+ PPR) but not projected: {played_not_projected} ({missed_points:.0f} PPR points)")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Backtest Rotobot's player projections.")
    parser.add_argument("--fit", action="store_true")
    parser.add_argument("--seasons", type=int, nargs="+", default=[2025, 2026])
    args = parser.parse_args()

    ctx = Context()
    if args.fit:
        model = fit(ctx)
        with open(rp.MODEL_PATH, "w") as handle:
            json.dump(model, handle, indent=1)
        print(f"Wrote {rp.MODEL_PATH}")
    model = rp.load_model()
    for season in args.seasons:
        evaluate(ctx, model, season)


if __name__ == "__main__":
    main()

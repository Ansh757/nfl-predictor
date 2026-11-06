"""
fit.py - League play models, fitted on 2021-2024 regular-season play-by-play.

    python -m rotobot.pbp.fit          # writes rotobot/pbp/league_model.json

Everything here is league-wide. What makes one offence different from another
is applied at game time (teams.py), and the market calibration on top of that
(calibrate.py) - so this file describes how an average NFL game unfolds, and
nothing about who is playing.

Where a model is a table of real outcomes, the engine samples from it rather
than from a fitted curve: a completion in the red zone is drawn from completions
that actually happened in the red zone, so the shape - the many short gains, the
occasional 60-yarder - is the real one.
"""
import json
import math
import os
import random
from collections import defaultdict
from typing import Dict, List

from rotobot.pbp.data import by_game

FIT_SEASONS = [2021, 2022, 2023, 2024]
MODEL_PATH = os.path.join(os.path.dirname(__file__), "league_model.json")
SAMPLES_PER_BUCKET = 400
# Stored in place of yardage for a play that scored. A gain from the 3 can only
# be 3 yards, so a pool of red-zone yardages mixed across positions understates
# how often a team scores from the 8; recording the touchdown itself keeps the
# real scoring rate for each zone. The engine reads it as "reached the end zone".
TOUCHDOWN = 999


# --- Situation buckets, shared with the engine ---------------------------------

def dist_bucket(ydstogo: float) -> str:
    if ydstogo <= 2:
        return "short"
    if ydstogo <= 6:
        return "medium"
    if ydstogo <= 10:
        return "long"
    return "very_long"


def zone(yardline_100: float) -> str:
    if yardline_100 <= 5:
        return "goal"
    if yardline_100 <= 10:
        return "rz10"
    if yardline_100 <= 20:
        return "rz20"
    if yardline_100 <= 40:
        return "plus"
    return "field"


def fourth_bucket(ydstogo: float) -> str:
    if ydstogo <= 1:
        return "1"
    if ydstogo <= 3:
        return "2-3"
    if ydstogo <= 6:
        return "4-6"
    return "7+"


def pass_features(down, ydstogo, yardline_100, score_diff, game_seconds, half_seconds, qtr) -> List[float]:
    """Inputs to the pass/run model. score_diff is the offence's lead."""
    late = max(0.0, 1.0 - game_seconds / 900.0) if qtr >= 4 else 0.0   # 0 -> 1 over the 4th quarter
    trailing = min(max(-score_diff, 0), 21) / 7.0
    leading = min(max(score_diff, 0), 21) / 7.0
    two_min = 1.0 if half_seconds <= 120 else 0.0
    return [
        1.0,
        1.0 if down == 2 else 0.0,
        1.0 if down >= 3 else 0.0,
        math.log(max(ydstogo, 1)),
        yardline_100 / 100.0,
        1.0 if yardline_100 <= 10 else 0.0,
        trailing, leading,
        trailing * late, leading * late,
        two_min, two_min * trailing,
    ]


def sample(values: List[float], n: int = SAMPLES_PER_BUCKET) -> List[float]:
    """A fixed-size, evenly spaced sample of the sorted values - a compact empirical distribution."""
    if not values:
        return []
    values = sorted(values)
    if len(values) <= n:
        return values
    return [values[int((i + 0.5) * len(values) / n)] for i in range(n)]


def _logistic_fit(xs: List[List[float]], ys: List[float], iters: int = 12, ridge: float = 1e-3) -> List[float]:
    """Plain Newton-Raphson logistic regression; a dozen features needs nothing more."""
    k = len(xs[0])
    beta = [0.0] * k
    for _ in range(iters):
        grad = [0.0] * k
        hess = [[0.0] * k for _ in range(k)]
        for x, y in zip(xs, ys):
            z = sum(b * v for b, v in zip(beta, x))
            p = 1 / (1 + math.exp(-max(min(z, 30), -30)))
            w = p * (1 - p)
            for i in range(k):
                grad[i] += (y - p) * x[i]
                xi = w * x[i]
                row = hess[i]
                for j in range(i, k):
                    row[j] += xi * x[j]
        for i in range(k):
            hess[i][i] += ridge
            for j in range(i):
                hess[i][j] = hess[j][i]
        step = _solve(hess, grad)
        beta = [b + s for b, s in zip(beta, step)]
    return beta


def _solve(a: List[List[float]], b: List[float]) -> List[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c and m[c][c]:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] if m[i][i] else 0.0 for i in range(n)]


# --- Fitting -----------------------------------------------------------------------

def _is_pass_call(p) -> bool:
    return p["play_type"] == "pass" or (p["play_type"] == "run" and p["qb_scramble"] == 1)


def _is_run_call(p) -> bool:
    return p["play_type"] == "run" and p["qb_scramble"] != 1


def _next_scrimmage(plays, i):
    for q in plays[i + 1:]:
        if q["play_type"] in ("pass", "run", "qb_kneel", "qb_spike", "field_goal", "punt") and q["down"]:
            return q
    return None


def fit() -> Dict:
    games = by_game(FIT_SEASONS)
    games = {g: p for g, p in games.items() if p and p[0]["season_type"] == "REG"}
    print(f"{len(games)} games, {sum(len(p) for p in games.values())} plays")

    xs, ys = [], []
    fourth = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))   # (late?, dist, yard bin) -> go, punt, fg
    pass_out = defaultdict(lambda: defaultdict(int))
    comp_yards, run_yards = defaultdict(list), defaultdict(list)
    scramble_yards, sack_yards = [], []
    runoff = defaultdict(list)
    penalties = {"offence": [], "defence": []}
    snaps = 0
    kickoff_start, punt_net = [], defaultdict(list)
    fg = []
    pat = [0, 0]
    two_pt = [0, 0]
    two_pt_rate = defaultdict(lambda: [0, 0])                      # diff-after-TD bucket -> tried, chances
    run_fumbles = [0, 0]
    pass_fumbles = [0, 0]
    kickoff_td = [0, 0]
    punt_td = [0, 0]

    for plays in games.values():
        for i, p in enumerate(plays):
            pt = p["play_type"]
            nxt = plays[i + 1] if i + 1 < len(plays) else None
            down, dist, yl = p["down"], p["ydstogo"], p["yardline_100"]
            diff = p["score_differential"]
            gs, hs, q = p["game_seconds_remaining"], p["half_seconds_remaining"], p["qtr"]
            usable = None not in (down, dist, yl, diff, gs, hs, q)

            # Play calling, downs 1-3
            if usable and down <= 3 and (_is_pass_call(p) or _is_run_call(p)) and not p["two_point_attempt"]:
                xs.append(pass_features(down, dist, yl, diff, gs, hs, q))
                ys.append(1.0 if _is_pass_call(p) else 0.0)

            # Fourth down
            if usable and down == 4 and pt in ("pass", "run", "punt", "field_goal"):
                late = q >= 4 and gs <= 600 and diff < 0
                choice = 0 if pt in ("pass", "run") else (1 if pt == "punt" else 2)
                fourth[late][(fourth_bucket(dist), min(int(yl // 10), 9))][choice] += 1

            # Outcomes
            if usable and down and not p["two_point_attempt"]:
                key = f"{dist_bucket(dist)}|{zone(yl)}"
                if _is_pass_call(p):
                    snaps += 1
                    o = pass_out[key]
                    o["n"] += 1
                    if p["sack"] == 1:
                        o["sack"] += 1
                        sack_yards.append(p["yards_gained"] or 0)
                    elif p["qb_scramble"] == 1:
                        o["scramble"] += 1
                        scramble_yards.append(TOUCHDOWN if p["rush_touchdown"] == 1 else (p["yards_gained"] or 0))
                    elif p["interception"] == 1:
                        o["int"] += 1
                    elif p["complete_pass"] == 1:
                        o["complete"] += 1
                        comp_yards[key].append(TOUCHDOWN if p["pass_touchdown"] == 1 else (p["yards_gained"] or 0))
                        pass_fumbles[0] += p["fumble_lost"] == 1
                        pass_fumbles[1] += 1
                elif _is_run_call(p):
                    snaps += 1
                    run_yards[key].append(TOUCHDOWN if p["rush_touchdown"] == 1 else (p["yards_gained"] or 0))
                    run_fumbles[0] += p["fumble_lost"] == 1
                    run_fumbles[1] += 1

            # Penalties that wiped out the play (no_play rows)
            if usable and pt == "no_play" and p["penalty"] == 1 and p["penalty_yards"] is not None:
                side = "offence" if p["penalty_team"] == p["posteam"] else "defence"
                penalties[side].append([p["penalty_yards"], 1 if p["first_down_penalty"] == 1 else 0])

            # Clock: time from this snap to the next, same quarter
            if (nxt and usable and nxt["qtr"] == q and nxt["game_seconds_remaining"] is not None
                    and pt in ("pass", "run", "qb_kneel", "no_play")):
                elapsed = gs - nxt["game_seconds_remaining"]
                if 0 <= elapsed <= 60 and not (p["timeout"] == 1):
                    if pt == "qb_kneel":
                        cls = "kneel"
                    elif pt == "no_play":
                        cls = "penalty"
                    elif p["sack"] == 1:
                        cls = "sack"
                    elif pt == "pass" and p["complete_pass"] != 1:
                        cls = "incomplete"
                    elif p["out_of_bounds"] == 1:
                        cls = "out_of_bounds"
                    else:
                        cls = "inbounds"
                    if diff < 0 and ((q >= 4 and gs <= 300) or hs <= 120):
                        tempo = "hurry"
                    elif diff > 0 and q >= 4 and gs <= 300:
                        tempo = "milk"
                    else:
                        tempo = "normal"
                    if nxt["timeout"] != 1:
                        runoff[f"{cls}|{tempo}"].append(elapsed)

            # Special teams
            if pt == "kickoff":
                kickoff_td[1] += 1
                if p["return_touchdown"] == 1:
                    kickoff_td[0] += 1
                elif p["season"] >= 2024:
                    # 2024's kickoff rule moved the typical start forward; earlier
                    # seasons would describe a play that no longer exists.
                    # nflverse lists the *receiving* team as posteam on a kickoff.
                    n = _next_scrimmage(plays, i)
                    if n and n["posteam"] == p["posteam"] and n["yardline_100"] is not None:
                        kickoff_start.append(n["yardline_100"])
            if pt == "punt" and yl is not None:
                punt_td[1] += 1
                if p["return_touchdown"] == 1:
                    punt_td[0] += 1
                else:
                    n = _next_scrimmage(plays, i)
                    if n and n["posteam"] == p["defteam"] and n["yardline_100"] is not None:
                        # The receiving team's field position, as distance from the punting spot
                        punt_net[min(int(yl // 10), 9)].append(n["yardline_100"])
            if pt == "field_goal" and p["kick_distance"] and p["field_goal_result"]:
                fg.append((p["kick_distance"], 1 if p["field_goal_result"] == "made" else 0))
            if pt == "extra_point" and p["extra_point_result"]:
                pat[0] += p["extra_point_result"] == "good"
                pat[1] += 1
            if p["two_point_attempt"] == 1 and p["two_point_conv_result"]:
                two_pt[0] += p["two_point_conv_result"] == "success"
                two_pt[1] += 1

            # Two-point decisions: after a touchdown, what did the team try?
            if pt in ("extra_point",) or p["two_point_attempt"] == 1:
                if diff is not None and q is not None:
                    bucket = _two_point_bucket(diff, q, gs)
                    two_pt_rate[bucket][0] += p["two_point_attempt"] == 1
                    two_pt_rate[bucket][1] += 1

    print(f"pass/run model on {len(xs)} plays")
    pass_beta = _logistic_fit(xs, ys)

    def smooth(counts, prior):
        total = sum(counts) + sum(prior)
        return [(c + pr) / total for c, pr in zip(counts, prior)]

    fourth_table = {}
    for late, cells in fourth.items():
        for (db, yb), counts in cells.items():
            prior = [1, 1, 1] if yb < 4 else [1, 1, 0.2]
            fourth_table[f"{int(late)}|{db}|{yb}"] = smooth(counts, prior)

    fg_beta = _logistic_fit([[1.0, d / 10.0] for d, _ in fg], [m for _, m in fg])

    model = {
        "fit_seasons": FIT_SEASONS,
        "pass_beta": pass_beta,
        "fourth": fourth_table,
        "pass_outcomes": {k: {f: v[f] / v["n"] for f in ("sack", "scramble", "int", "complete")} | {"n": v["n"]}
                          for k, v in pass_out.items()},
        "completion_yards": {k: sample(v) for k, v in comp_yards.items()},
        "run_yards": {k: sample(v) for k, v in run_yards.items()},
        "scramble_yards": sample(scramble_yards),
        "sack_yards": sample(sack_yards),
        "fumble_lost": {"run": run_fumbles[0] / run_fumbles[1], "catch": pass_fumbles[0] / pass_fumbles[1]},
        "penalty_rate": {s: len(v) / snaps for s, v in penalties.items()},
        "penalty_samples": {s: random.Random(7).sample(v, min(len(v), SAMPLES_PER_BUCKET)) for s, v in penalties.items()},
        "runoff": {k: sample(v, 200) for k, v in runoff.items() if len(v) >= 30},
        "kickoff_start": sample(kickoff_start),
        "kickoff_return_td": kickoff_td[0] / kickoff_td[1],
        "punt_start": {str(k): sample(v, 200) for k, v in punt_net.items()},
        "punt_return_td": punt_td[0] / punt_td[1],
        "fg_beta": fg_beta,
        "pat": pat[0] / pat[1],
        "two_point_success": two_pt[0] / two_pt[1],
        "two_point_rate": {k: v[0] / v[1] for k, v in two_pt_rate.items() if v[1] >= 20},
    }
    return model


def _two_point_bucket(diff_after_td: float, qtr: float, game_seconds: float) -> str:
    """Score after the touchdown, before the try, from the scoring team's side."""
    late = "late" if qtr >= 4 and game_seconds <= 900 else "early"
    d = int(diff_after_td)
    key = str(d) if -16 <= d <= 16 else ("<-16" if d < -16 else ">16")
    return f"{late}|{key}"


# Set by backtest_rotobot_pbp.py (tuned on 2024 by simulating whole games), not by
# this fit - carried over so refitting the play tables does not silently drop them
TUNED_KEYS = ("form_sd", "interval_levels")

if __name__ == "__main__":
    model = fit()
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH) as handle:
            previous = json.load(handle)
        model.update({k: previous[k] for k in TUNED_KEYS if k in previous})
    with open(MODEL_PATH, "w") as handle:
        json.dump(model, handle, separators=(",", ":"))
    print(f"wrote {MODEL_PATH} ({os.path.getsize(MODEL_PATH) // 1024} KB)")
    print("pass beta", [round(b, 3) for b in model["pass_beta"]])
    print("PAT", round(model["pat"], 3), "2pt", round(model["two_point_success"], 3))
    print("penalty rates", {k: round(v, 4) for k, v in model["penalty_rate"].items()})

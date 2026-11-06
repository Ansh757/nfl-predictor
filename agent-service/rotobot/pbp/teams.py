"""
teams.py - What makes this offence and this defence different from average.

From each team's last eight games of play-by-play (strictly before the game
being simulated), on both sides of the ball:

  * completion rate                       -> a logit shift
  * yards per completion, per carry       -> multipliers
  * sack rate, interception rate          -> multipliers
  * pass rate over expected (offence)     -> a logit shift on the play call:
    how much more this team passes than the league would in the same downs,
    distances, scores and clock

Every figure is shrunk toward league average by a pseudo-count, so a team with
two games of data looks mostly average and a team with eight looks like itself.
Interception rate is shrunk hardest: it is the noisiest thing in the sport.

These describe a team's style and efficiency. They do not decide how many
points it scores against this opponent - the market calibration does that
(calibrate.py), by scaling efficiency until the average simulated score matches
the line. Teams here shape *how* a game unfolds; the market sets *how well*.
"""
import math
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from rotobot.pbp.engine import Side
from rotobot.pbp.fit import pass_features

WINDOW = 8
PRIOR = {"comp": 150, "ypc_pass": 100, "ypc_run": 150, "sack": 300, "int": 800, "proe": 250}
CLAMP = (0.75, 1.30)


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


class TeamHistory:
    """Per-game offence and defence totals, built once from a list of plays."""

    def __init__(self, plays: Iterable[Dict], pass_beta: List[float]):
        self.games: Dict[str, List[Tuple[int, int, str]]] = defaultdict(list)   # team -> (season, week, game_id)
        self.totals: Dict[Tuple[str, str, str], Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        seen = set()
        for p in plays:
            off, de = p["posteam"], p["defteam"]
            if not off or not de or p["season_type"] != "REG" or p["down"] is None:
                continue
            gid = p["game_id"]
            for team in (off, de):
                if (gid, team) not in seen:
                    seen.add((gid, team))
                    self.games[team].append((int(p["season"]), int(p["week"]), gid))
            is_pass = p["play_type"] == "pass" or (p["play_type"] == "run" and p["qb_scramble"] == 1)
            is_run = p["play_type"] == "run" and p["qb_scramble"] != 1
            if not (is_pass or is_run) or p["two_point_attempt"] == 1:
                continue
            for side, team in (("off", off), ("def", de)):
                t = self.totals[(gid, team, side)]
                t["plays"] += 1
                if is_pass and p["down"] <= 3 and None not in (p["ydstogo"], p["yardline_100"], p["score_differential"],
                                                              p["game_seconds_remaining"], p["half_seconds_remaining"], p["qtr"]):
                    x = pass_features(p["down"], p["ydstogo"], p["yardline_100"], p["score_differential"],
                                      p["game_seconds_remaining"], p["half_seconds_remaining"], p["qtr"])
                    t["xpass"] += 1 / (1 + math.exp(-sum(b * v for b, v in zip(pass_beta, x))))
                    t["pass_calls_123"] += 1
                    t["calls_123"] += 1
                elif is_run and p["down"] <= 3 and None not in (p["ydstogo"], p["yardline_100"], p["score_differential"],
                                                                 p["game_seconds_remaining"], p["half_seconds_remaining"], p["qtr"]):
                    x = pass_features(p["down"], p["ydstogo"], p["yardline_100"], p["score_differential"],
                                      p["game_seconds_remaining"], p["half_seconds_remaining"], p["qtr"])
                    t["xpass"] += 1 / (1 + math.exp(-sum(b * v for b, v in zip(pass_beta, x))))
                    t["calls_123"] += 1
                if is_pass:
                    t["dropbacks"] += 1
                    if p["sack"] == 1:
                        t["sacks"] += 1
                    elif p["qb_scramble"] != 1:
                        t["attempts"] += 1
                        t["ints"] += p["interception"] == 1
                        if p["complete_pass"] == 1:
                            t["completions"] += 1
                            t["comp_yards"] += p["yards_gained"] or 0
                else:
                    t["carries"] += 1
                    t["rush_yards"] += p["yards_gained"] or 0
        for team in self.games:
            self.games[team].sort()

    def window(self, team: str, season: int, week: int) -> List[str]:
        return [gid for s, w, gid in self.games.get(team, []) if (s, w) < (season, week)][-WINDOW:]

    def sums(self, team: str, side: str, season: int, week: int) -> Dict[str, float]:
        out: Dict[str, float] = defaultdict(float)
        for gid in self.window(team, season, week):
            for k, v in self.totals.get((gid, team, side), {}).items():
                out[k] += v
        return out


def league_rates(history: TeamHistory) -> Dict[str, float]:
    total: Dict[str, float] = defaultdict(float)
    for (gid, team, side), t in history.totals.items():
        if side == "off":
            for k, v in t.items():
                total[k] += v
    return {
        "comp": total["completions"] / total["attempts"],
        "ypc_pass": total["comp_yards"] / total["completions"],
        "ypc_run": total["rush_yards"] / total["carries"],
        "sack": total["sacks"] / total["dropbacks"],
        "int": total["ints"] / total["attempts"],
    }


def _clamp(x: float) -> float:
    return min(max(x, CLAMP[0]), CLAMP[1])


def _unit(s: Dict[str, float], league: Dict[str, float]) -> Dict[str, float]:
    """Shrunk ratios against league for one side of one team."""
    comp = (s["completions"] + PRIOR["comp"] * league["comp"]) / (s["attempts"] + PRIOR["comp"])
    ypc_pass = (s["comp_yards"] + PRIOR["ypc_pass"] * league["ypc_pass"]) / (s["completions"] + PRIOR["ypc_pass"])
    ypc_run = (s["rush_yards"] + PRIOR["ypc_run"] * league["ypc_run"]) / (s["carries"] + PRIOR["ypc_run"])
    sack = (s["sacks"] + PRIOR["sack"] * league["sack"]) / (s["dropbacks"] + PRIOR["sack"])
    ints = (s["ints"] + PRIOR["int"] * league["int"]) / (s["attempts"] + PRIOR["int"])
    return {
        "comp": _logit(comp) - _logit(league["comp"]),
        "pass": _clamp(ypc_pass / league["ypc_pass"]),
        "run": _clamp(ypc_run / league["ypc_run"]),
        "sack": _clamp(sack / league["sack"]),
        "int": _clamp(ints / league["int"]),
    }


def build_side(history: TeamHistory, league: Dict[str, float], team: str, season: int, week: int) -> Side:
    off = history.sums(team, "off", season, week)
    de = history.sums(team, "def", season, week)
    o, d = _unit(off, league), _unit(de, league)
    # Pass rate over expected, shrunk, as a logit shift around a ~58% base
    proe = (off["pass_calls_123"] - off["xpass"]) / (off["calls_123"] + PRIOR["proe"])
    base = 0.58
    lean = _logit(min(max(base + proe, 0.05), 0.95)) - _logit(base)
    return Side(
        code=team, pass_lean=lean,
        comp_off=o["comp"], pass_off=o["pass"], run_off=o["run"], sack_off=o["sack"], int_off=o["int"],
        comp_def=d["comp"], pass_def=d["pass"], run_def=d["run"], sack_def=d["sack"], int_def=d["int"],
    )

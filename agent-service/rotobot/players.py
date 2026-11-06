"""
players.py - Fantasy projections, built down from the market's team totals.

Three layers, each only allowed to decide what the one above leaves open:

  1. Team volume and production. Small linear models, fitted on 2021-2024,
     predict each team's pass attempts, completions, yards, TDs, carries and so
     on from its recent output, its opponent's recent defence, the spread (game
     script: a team expected to trail throws more) and the market's expected
     points. The last input is the anchor - it is what ties player lines to the
     score model.
  2. Who plays. A player is projected if he appeared in one of the team's last
     three games, is not listed Out or Doubtful, has not since appeared for
     another team, and - where nflverse has published it - is on that week's
     roster as active (rosters.py: this is what catches offseason departures and
     injured reserve). Shares of targets and carries come from his recent games,
     weighted toward the latest, and are renormalised over the players who are
     active - which is how an injured starter's share reaches the rest.
  3. How the team's production is split. A player's efficiency (yards per
     target, catch rate, TD rate), shrunk hard toward his position's average,
     only decides his slice. Player yards and TDs always add up to the team's.

The quarterback who started the team's most recent game, if active, takes the
team's passing line; the next-busiest active QB otherwise.

Known blind spot: a player with no history for this team - a rookie's debut,
a signing who has not played yet - is not projected, and his share goes to the
players who are. Week 1 is where that bites. The roster removes the players who
left; it cannot invent a role for the ones who arrived.
"""
import json
import os
from typing import Dict, List, Optional, Set, Tuple

from rotobot.player_data import PlayerStats, fantasy_points

WINDOW = 8                 # team games of history for volume and shares
HALF_LIFE = 4.0            # games; recency weighting for shares
ACTIVE_LOOKBACK = 3        # must have played in one of the team's last N games
TEAM_STATS = ("attempts", "completions", "passing_yards", "passing_tds",
              "passing_interceptions", "carries", "rushing_yards", "rushing_tds", "targets")

# Pseudo-counts for shrinking a player's rates toward his position's average.
# TD rates are shrunk hardest: a receiver with three scores on twenty targets
# has not learned to score on 15% of them.
PRIOR = {"ypt": 40, "catch": 40, "rec_td": 150, "ypc": 50, "rush_td": 150, "fumble": 300}

MODEL_PATH = os.path.join(os.path.dirname(__file__), "player_model.json")


def load_model(path: str = MODEL_PATH) -> Dict:
    with open(path) as handle:
        return json.load(handle)


# --- Team layer ------------------------------------------------------------

def team_features(ps: PlayerStats, team: str, season: int, week: int,
                  league: Dict[str, float]) -> Optional[Dict[str, Dict[str, float]]]:
    """Recent per-game offence and defence for a team, shrunk to league average when short."""
    recent = ps.recent_games(team, season, week, WINDOW)
    if not recent:
        return None
    offence, defence = {}, {}
    allowed = [ps.allowed(key) for key in recent]
    allowed = [a for a in allowed if a]
    for stat in TEAM_STATS:
        own = [ps.team_totals[key][stat] for key in recent]
        # Two games' worth of league average, so week 2 is not a one-game sample
        offence[stat] = (sum(own) + 2 * league[stat]) / (len(own) + 2)
        opp = [a[stat] for a in allowed]
        defence[stat] = (sum(opp) + 2 * league[stat]) / (len(opp) + 2)
    return {"offence": offence, "defence": defence, "games": len(recent)}


def team_projection(model: Dict, features_team, features_opp, team_spread: float,
                    implied_points: float) -> Dict[str, float]:
    out = {}
    for stat in TEAM_STATS:
        beta = model["team"][stat]
        x = [1.0, features_team["offence"][stat], features_opp["defence"][stat],
             team_spread, implied_points]
        out[stat] = max(0.0, sum(b * v for b, v in zip(beta, x)))
    return out


# --- Player layer ----------------------------------------------------------

def _last_team(ps: PlayerStats, player_id: str, before: Tuple[int, int],
               index: Dict[str, List[Tuple[int, int, str]]]) -> Optional[str]:
    games = [g for g in index.get(player_id, []) if (g[0], g[1]) < before]
    return games[-1][2] if games else None


def player_index(ps: PlayerStats) -> Dict[str, List[Tuple[int, int, str]]]:
    """player_id -> every (season, week, team) he appeared in, oldest first."""
    index: Dict[str, List[Tuple[int, int, str]]] = {}
    for key, rows in ps.player_games.items():
        for row in rows:
            index.setdefault(row["player_id"], []).append(key)
    for games in index.values():
        games.sort()
    return index


def _shrunk(num: float, den: float, prior_rate: float, weight: float) -> float:
    return (num + prior_rate * weight) / (den + weight)


def project_players(ps: PlayerStats, model: Dict, index, team: str, season: int, week: int,
                    team_line: Dict[str, float], out_ids: Set[str],
                    roster: Optional[Set[str]] = None) -> List[Dict]:
    """`roster`: player ids the week's roster lists as eligible, or None if unknown (see rosters.py)."""
    recent = ps.recent_games(team, season, week, WINDOW)
    if not recent:
        return []
    before = (season, week)
    lookback = set(recent[:ACTIVE_LOOKBACK])

    # Recency-weighted shares, taken over the games each player actually played
    shares: Dict[str, Dict] = {}
    for i, key in enumerate(recent):
        weight = 0.5 ** (i / HALF_LIFE)
        totals = ps.team_totals[key]
        for row in ps.player_games[key]:
            entry = shares.setdefault(row["player_id"], {
                "name": row["name"], "position": row["position"], "headshot": row["headshot"],
                "t_w": 0.0, "t": 0.0, "c_w": 0.0, "c": 0.0, "recent": False, "last_att": None,
            })
            entry["t"] += weight * (row["targets"] / totals["targets"] if totals["targets"] else 0)
            entry["c"] += weight * (row["carries"] / totals["carries"] if totals["carries"] else 0)
            entry["t_w"] += weight
            entry["c_w"] += weight
            if key in lookback:
                entry["recent"] = True
            if entry["last_att"] is None:
                entry["last_att"] = row["attempts"]       # newest game seen first

    active = {
        pid: e for pid, e in shares.items()
        if e["recent"] and pid not in out_ids and e["position"] != "OTHER"
        and _last_team(ps, pid, before, index) == team
        and (roster is None or pid in roster)
    }
    if not active:
        return []

    target_share = {pid: e["t"] / e["t_w"] for pid, e in active.items()}
    carry_share = {pid: e["c"] / e["c_w"] for pid, e in active.items()}

    # Everyone who held a role recently, active or not: the shares the team's
    # targets and carries were actually split across.
    held = [e for e in shares.values() if e["recent"] and e["position"] != "OTHER"]
    t_base = sum(e["t"] / e["t_w"] for e in held)
    c_base = sum(e["c"] / e["c_w"] for e in held)
    redistribute = model.get("redistribute", 1.0)
    ts = _normalise(target_share, t_base, redistribute)
    cs = _normalise(carry_share, c_base, redistribute)

    rates = {pid: _player_rates(ps, index, pid, before, active[pid]["position"], model) for pid in active}

    def split(share, rate_key, team_value):
        # Efficiency decides each player's slice of the share the projected
        # players hold between them; the rest belongs to players not projected.
        coverage = sum(share.values())
        weights = {pid: share[pid] * rates[pid][rate_key] for pid in active}
        total = sum(weights.values())
        return {pid: team_value * coverage * w / total if total else 0.0 for pid, w in weights.items()}
    rec_yds = split(ts, "ypt", team_line["passing_yards"])
    receptions = split(ts, "catch", team_line["completions"])
    rec_tds = split(ts, "rec_td", team_line["passing_tds"])
    rush_yds = split(cs, "ypc", team_line["rushing_yards"])
    rush_tds = split(cs, "rush_td", team_line["rushing_tds"])

    qbs = [pid for pid, e in active.items() if e["position"] == "QB"]
    starter = max(qbs, key=lambda pid: (active[pid]["last_att"] or 0, active[pid]["t_w"]), default=None)

    players = []
    for pid, e in active.items():
        stats = {
            "targets": team_line["targets"] * ts[pid],
            "receptions": receptions[pid],
            "receiving_yards": rec_yds[pid],
            "receiving_tds": rec_tds[pid],
            "carries": team_line["carries"] * cs[pid],
            "rushing_yards": rush_yds[pid],
            "rushing_tds": rush_tds[pid],
            "attempts": 0.0, "completions": 0.0, "passing_yards": 0.0,
            "passing_tds": 0.0, "passing_interceptions": 0.0,
        }
        stats["fumbles_lost"] = rates[pid]["fumble"] * (stats["carries"] + stats["receptions"])
        if pid == starter:
            for stat in ("attempts", "completions", "passing_yards", "passing_tds", "passing_interceptions"):
                stats[stat] = team_line[stat]
        elif e["position"] == "QB":
            continue                       # a backup QB's line is noise; leave him out
        points = {
            "ppr": fantasy_points(stats, 1.0),
            "half_ppr": fantasy_points(stats, 0.5),
            "standard": fantasy_points(stats, 0.0),
        }
        if points["ppr"] < 0.5:
            continue
        players.append({
            "player_id": pid, "name": e["name"], "position": e["position"],
            "headshot": e["headshot"], "starter": pid == starter if e["position"] == "QB" else None,
            "stats": {k: round(v, 2) for k, v in stats.items()},
            "fantasy": {k: round(v, 2) for k, v in points.items()},
        })
    players.sort(key=lambda p: p["fantasy"]["ppr"], reverse=True)
    return players


def _normalise(share: Dict[str, float], base: float, redistribute: float) -> Dict[str, float]:
    """
    Turn raw shares into fractions of the team's volume.

    `base` is what the shares summed to across everyone who held a role. When
    some of those players are out, gone or on injured reserve, a fraction
    `redistribute` of their share goes to the projected players, in proportion
    to their own; the rest goes to players the model cannot name - rookies,
    signings, call-ups. Full redistribution (1.0) over-projected everyone left:
    measured, not assumed - see backtest_rotobot_players.py --fit.
    """
    active = sum(share.values())
    if not active or not base:
        return {pid: 0.0 for pid in share}
    vacated = max(base - active, 0.0)
    scale = (active + redistribute * vacated) / (base * active)
    return {pid: s * scale for pid, s in share.items()}


def _player_rates(ps: PlayerStats, index, pid: str, before, position: str, model: Dict) -> Dict[str, float]:
    """A player's efficiency over his last 2 x WINDOW games, shrunk to his position."""
    games = [g for g in index.get(pid, []) if (g[0], g[1]) < before][-2 * WINDOW:]
    sums = {k: 0.0 for k in ("targets", "receptions", "receiving_yards", "receiving_tds",
                             "carries", "rushing_yards", "rushing_tds", "fumbles", "touches")}
    for key in games:
        row = next(r for r in ps.player_games[key] if r["player_id"] == pid)
        for k in ("targets", "receptions", "receiving_yards", "receiving_tds",
                  "carries", "rushing_yards", "rushing_tds"):
            sums[k] += row[k]
        sums["fumbles"] += row["rushing_fumbles_lost"] + row["receiving_fumbles_lost"]
        sums["touches"] += row["carries"] + row["receptions"]
    league = model["position_rates"].get(position, model["position_rates"]["WR"])
    return {
        "ypt": _shrunk(sums["receiving_yards"], sums["targets"], league["ypt"], PRIOR["ypt"]),
        "catch": _shrunk(sums["receptions"], sums["targets"], league["catch"], PRIOR["catch"]),
        "rec_td": _shrunk(sums["receiving_tds"], sums["targets"], league["rec_td"], PRIOR["rec_td"]),
        "ypc": _shrunk(sums["rushing_yards"], sums["carries"], league["ypc"], PRIOR["ypc"]),
        "rush_td": _shrunk(sums["rushing_tds"], sums["carries"], league["rush_td"], PRIOR["rush_td"]),
        "fumble": _shrunk(sums["fumbles"], sums["touches"], league["fumble"], PRIOR["fumble"]),
    }


# --- Ranges ------------------------------------------------------------------

def with_ranges(players: List[Dict], model: Dict) -> List[Dict]:
    """Attach calibrated 80% ranges: residual quantiles by position, scaled by sqrt(projection)."""
    for p in players:
        cal = model["ranges"].get(p["position"])
        if not cal:
            continue
        p["ranges"] = {}
        for stat, (z_lo, z_hi) in cal.items():
            proj = p["fantasy"]["ppr"] if stat == "ppr" else p["stats"][stat]
            scale = (max(proj, 0.0) + 1.0) ** 0.5
            p["ranges"][stat] = [round(max(0.0, proj + z_lo * scale), 1), round(max(0.0, proj + z_hi * scale), 1)]
    return players

"""
score.py - The distribution of final scores for one game, anchored to the market.

The market's spread and total fix each team's expected points:

    home = total / 2 - home_spread / 2        (home_spread < 0 when home is favoured)
    away = total / 2 + home_spread / 2

That is the anchor, and it is deliberate: every measurement in this repo says the
closing line beats any signal we derive ourselves (see CLAUDE.md, "The market
question"). What the line does not give is the *shape* - how likely 27-24 is
against 30-21. That comes from a drive model:

  * both teams get the same number of possessions D, drawn per game;
  * each possession ends in a touchdown (7, or 6 if the extra point is missed),
    a field goal (3) or nothing, with the touchdown rate solved so the expected
    score equals the market's figure and field goals at a fixed ratio to it;
  * a tie after regulation goes to overtime, which ends in a field goal or a
    touchdown for one side, or very occasionally stays tied.

Scores built from 3s and 7s land on real football numbers - 20, 17, 24, 27 - and
margins of 3 and 7 come out as often as they do in real games, which a normal
distribution around the spread cannot do.

Computed exactly rather than sampled. A team's points are a sum of i.i.d. drive
outcomes, so their distribution is a convolution, and the two teams are
independent given D. No random seed, no Monte Carlo noise, and fast enough in
plain Python to fit the parameters below over every game since 2021.

Parameters were fitted on 2021-2024 by maximum likelihood of the exact final
score (backtest_rotobot.py --fit); 2025 and 2026 are held out.

Two known limits, both measured in backtest_rotobot.py:

  * The raw distribution is slightly too wide - a nominal 80% range held the
    result 83-85% of the time. Real teams change behaviour with the score
    (leaders run the clock, trailers take risks), which pulls outcomes in, and
    independent drives cannot. The reported ranges are therefore calibrated:
    "80%" is read off the 76% quantiles, which hit 80% on 2021-2024 and
    79.0-79.8% on held-out 2025.
  * Margins of exactly 3 come out at ~9% against ~15% in real games. That is
    end-of-game strategy - playing for the tying or winning field goal - which
    a drive-independent model cannot produce. It matters for pricing spreads on
    key numbers; it barely moves medians, ranges or anything fantasy-related.
"""
from dataclasses import dataclass
from math import erf, exp, sqrt
from typing import Dict, List, Optional, Tuple

# --- Fitted on 2021-2024. Re-derive with: python backtest_rotobot.py --fit ---
# The likelihood is nearly flat in the drive count (the top candidates sat
# within 0.002 of each other from 10 to 12 drives), so it is held at the
# league's ~11 possessions per team rather than at whichever grid point won by
# noise. The field-goal ratio is the parameter the data actually pinned.
DRIVES_MEAN = 11.0
DRIVES_SD = 1.0
FG_PER_TD = 0.85          # field goals per touchdown drive

# The quantile pair reported as an 80% range. See the module docstring.
CALIBRATED_LEVELS = {0.8: 0.76}

# Not fitted - league rates that move too little to be worth estimating here.
PAT_RATE = 0.94           # extra point made after a touchdown
OT_TIE_RATE = 0.06        # overtime games that end tied
OT_FG_SHARE = 0.55        # overtime decided by a field goal rather than a touchdown

# Without a market (see live.py) the total falls back to the league average
LEAGUE_AVERAGE_TOTAL = 44.5
# Measured std of (margin - spread), 2021-2024. Converts a win probability into
# a spread when there is no market spread to read.
MARGIN_SD = 12.7

MAX_SCORE = 90


@dataclass(frozen=True)
class GameLine:
    """What the simulation is anchored to. home_spread uses betting convention."""
    home_spread: float
    total: float

    @property
    def home_points(self) -> float:
        return self.total / 2 - self.home_spread / 2

    @property
    def away_points(self) -> float:
        return self.total / 2 + self.home_spread / 2


def _drive_outcomes(points_per_drive: float, fg_per_td: float) -> List[Tuple[int, float]]:
    """Per-drive score distribution whose mean is points_per_drive."""
    td_value = 7 * PAT_RATE + 6 * (1 - PAT_RATE)
    p_td = points_per_drive / (td_value + 3 * fg_per_td)
    p_fg = p_td * fg_per_td
    # A team implied at 45 points would need more than one score per drive;
    # cap it and accept the expected score running slightly under.
    if p_td + p_fg > 0.95:
        scale = 0.95 / (p_td + p_fg)
        p_td, p_fg = p_td * scale, p_fg * scale
    return [
        (7, p_td * PAT_RATE),
        (6, p_td * (1 - PAT_RATE)),
        (3, p_fg),
        (0, 1 - p_td - p_fg),
    ]


def _score_pmfs(expected: float, drive_counts: List[int], fg_per_td: float,
                drives_mean: float) -> Dict[int, List[float]]:
    """Score distribution after exactly d drives, for every d in drive_counts."""
    outcomes = _drive_outcomes(max(expected, 0.0) / drives_mean, fg_per_td)
    pmf = [1.0] + [0.0] * MAX_SCORE
    out: Dict[int, List[float]] = {}
    for d in range(1, max(drive_counts) + 1):
        nxt = [0.0] * (MAX_SCORE + 1)
        for score, p in enumerate(pmf):
            if p == 0.0:
                continue
            for points, q in outcomes:
                nxt[min(score + points, MAX_SCORE)] += p * q
        pmf = nxt
        if d in drive_counts:
            out[d] = pmf
    return out


def _drive_count_weights(drives_mean: float, drives_sd: float) -> List[Tuple[int, float]]:
    """A discretised normal over possessions per team."""
    if drives_sd <= 0:
        return [(round(drives_mean), 1.0)]
    lo, hi = int(drives_mean - 3 * drives_sd), int(drives_mean + 3 * drives_sd) + 1
    weights = [(d, exp(-0.5 * ((d - drives_mean) / drives_sd) ** 2)) for d in range(max(lo, 1), hi + 1)]
    total = sum(w for _, w in weights)
    return [(d, w / total) for d, w in weights]


@dataclass
class ScoreDistribution:
    """Exact joint distribution of (home, away) final score."""
    joint: Dict[Tuple[int, int], float]

    def prob(self, predicate) -> float:
        return sum(p for (h, a), p in self.joint.items() if predicate(h, a))

    def marginal(self, side: str) -> List[float]:
        # Overtime can add up to 6 to a capped regulation score
        pmf = [0.0] * (MAX_SCORE + 7)
        for (h, a), p in self.joint.items():
            pmf[h if side == "home" else a] += p
        return pmf

    def margin_pmf(self) -> Dict[int, float]:
        out: Dict[int, float] = {}
        for (h, a), p in self.joint.items():
            out[h - a] = out.get(h - a, 0.0) + p
        return out

    def total_pmf(self) -> Dict[int, float]:
        out: Dict[int, float] = {}
        for (h, a), p in self.joint.items():
            out[h + a] = out.get(h + a, 0.0) + p
        return out

    def most_likely(self) -> Tuple[int, int]:
        return max(self.joint, key=self.joint.get)


def quantile(pmf, q: float) -> int:
    """Smallest value whose cumulative probability reaches q. pmf: list or dict."""
    items = enumerate(pmf) if isinstance(pmf, list) else sorted(pmf.items())
    cumulative = 0.0
    last = 0
    for value, p in items:
        cumulative += p
        last = value
        if cumulative >= q - 1e-12:
            return value
    return last


def simulate(line: GameLine, drives_mean: float = DRIVES_MEAN, drives_sd: float = DRIVES_SD,
             fg_per_td: float = FG_PER_TD) -> ScoreDistribution:
    weights = _drive_count_weights(drives_mean, drives_sd)
    counts = [d for d, _ in weights]
    home = _score_pmfs(line.home_points, counts, fg_per_td, drives_mean)
    away = _score_pmfs(line.away_points, counts, fg_per_td, drives_mean)

    joint: Dict[Tuple[int, int], float] = {}
    for d, w in weights:
        hp, ap = home[d], away[d]
        h_nonzero = [(h, p) for h, p in enumerate(hp) if p > 1e-9]
        a_nonzero = [(a, p) for a, p in enumerate(ap) if p > 1e-9]
        for h, ph in h_nonzero:
            for a, pa in a_nonzero:
                key = (h, a)
                joint[key] = joint.get(key, 0.0) + w * ph * pa

    return ScoreDistribution(_overtime(joint))


def _overtime(joint: Dict[Tuple[int, int], float]) -> Dict[Tuple[int, int], float]:
    """Resolve regulation ties. The stronger side, by regulation odds, wins more OTs."""
    home_win = sum(p for (h, a), p in joint.items() if h > a)
    away_win = sum(p for (h, a), p in joint.items() if a > h)
    decided = home_win + away_win
    p_home = home_win / decided if decided > 0 else 0.5

    out: Dict[Tuple[int, int], float] = {}
    for (h, a), p in joint.items():
        if h != a:
            out[(h, a)] = out.get((h, a), 0.0) + p
            continue
        out[(h, a)] = out.get((h, a), 0.0) + p * OT_TIE_RATE
        settled = p * (1 - OT_TIE_RATE)
        for points, share in ((3, OT_FG_SHARE), (6, 1 - OT_FG_SHARE)):
            out[(h + points, a)] = out.get((h + points, a), 0.0) + settled * share * p_home
            out[(h, a + points)] = out.get((h, a + points), 0.0) + settled * share * (1 - p_home)
    return out


def spread_from_win_probability(home_win_probability: float) -> float:
    """Betting-convention spread implied by a win probability, via MARGIN_SD."""
    # Inverse of P(margin > 0) for margin ~ N(-spread, MARGIN_SD), by bisection
    lo, hi = -40.0, 40.0
    for _ in range(60):
        mid = (lo + hi) / 2
        p = 0.5 * (1 + erf((-mid) / (MARGIN_SD * sqrt(2))))
        if p > home_win_probability:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 1)


def summarize(dist: ScoreDistribution, line: GameLine, interval: float = 0.8) -> Dict:
    """Everything the API and the backtest report about one game."""
    nominal = CALIBRATED_LEVELS.get(interval, interval)
    lo_q, hi_q = (1 - nominal) / 2, 1 - (1 - nominal) / 2
    home_pmf, away_pmf = dist.marginal("home"), dist.marginal("away")
    margin, total = dist.margin_pmf(), dist.total_pmf()
    likely = dist.most_likely()
    return {
        "anchor": {
            "home_spread": line.home_spread,
            "total": line.total,
            "home_implied_points": round(line.home_points, 1),
            "away_implied_points": round(line.away_points, 1),
        },
        "most_likely_score": {"home": likely[0], "away": likely[1]},
        "median": {"home": quantile(home_pmf, 0.5), "away": quantile(away_pmf, 0.5)},
        "interval": {
            "level": interval,
            "home": [quantile(home_pmf, lo_q), quantile(home_pmf, hi_q)],
            "away": [quantile(away_pmf, lo_q), quantile(away_pmf, hi_q)],
            "margin": [quantile(margin, lo_q), quantile(margin, hi_q)],
            "total": [quantile(total, lo_q), quantile(total, hi_q)],
        },
        "probabilities": {
            "home_win": round(dist.prob(lambda h, a: h > a), 4),
            "away_win": round(dist.prob(lambda h, a: a > h), 4),
            "tie": round(dist.prob(lambda h, a: h == a), 4),
            # Pushes count for neither side, so these need not sum to one
            "home_covers": round(dist.prob(lambda h, a: h - a + line.home_spread > 0), 4),
            "over": round(dist.prob(lambda h, a: h + a > line.total), 4),
        },
    }


def expected_points(pmf: List[float]) -> float:
    return sum(score * p for score, p in enumerate(pmf))


def drive_outcome_rates(points: float, drives_mean: Optional[float] = None,
                        fg_per_td: float = FG_PER_TD) -> Dict[str, float]:
    """Per-drive TD / FG rates for a team - reused by the player model."""
    outcomes = dict((pts, p) for pts, p in _drive_outcomes(points / (drives_mean or DRIVES_MEAN), fg_per_td))
    return {"td": outcomes[7] + outcomes[6], "fg": outcomes[3]}

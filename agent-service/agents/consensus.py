"""
consensus.py - Shared ensemble voting logic.

Used by both the /predict endpoint (main.py) and the backtest harness
(backtest.py) so that measured accuracy reflects the code that actually
serves predictions.

Two voting methods are available:

  'weighted' (default)
      Each agent contributes `weight * (confidence - 0.5)` to its pick. Agents
      that do not beat a coin flip in backtest carry a weight of ~0, so they
      cannot outvote an agent carrying real signal. This is what AGENT_WEIGHTS
      encodes.

  'majority'
      One agent, one vote, for any number of agents. Ties broken by the most
      confident agent. Kept for comparison and for ensembles with no
      calibrated weights.

Historical note: the original implementation only had branches for N-0
(unanimous) and (N-1)-1 (majority) splits, and fell through to "most confident
agent wins" for everything else. That was invisible with exactly four agents,
where 4-0, 3-1 and 2-2 are the only possible splits, but it silently discarded
the majority on a 3-2 split the moment a fifth agent was added.
"""
from typing import Any, Dict, List, Optional, Sequence

# Agents with no calibration yet fall back to this. Deliberately small: a new
# agent should have to earn its influence in the backtest before it can swing
# a prediction.
DEFAULT_WEIGHT = 0.02
DEFAULT_WEIGHT_PLACEHOLDER = DEFAULT_WEIGHT

# Weights calibrated from the walk-forward backtest over the 2021-2024 seasons
# (see backtest.py). A weight is the agent's measured edge over a coin flip,
# floored at zero: an agent that cannot beat 50% contributes nothing.
#
# Re-derive with:  python backtest.py --season <year> --runs 20
# Re-derived after neutral-site correction. Historical ratings previously
# credited the designated home team with home-field advantage at every venue,
# including the ~30 completed neutral-site games (international fixtures and
# four of five Super Bowls), so Elo carried an error forward from games where
# nobody was at home. Every figure below is 2021-2024 under the corrected
# methodology; the movement is small because 30 games out of 1,359 is small.
AGENT_WEIGHTS: Dict[str, float] = {
    "Market Odds": 0.164,         # 66.4% - strongest agent; 60.7/65.7/67.6/71.7
    "Basic Predictor": 0.111,     # 61.2% (was 61.0); 57.7/60.1/62.5/64.3
    "Elo Ratings": 0.116,         # 61.6% (was 61.5) - understated; 2021 is a cold start
    "Rest & Travel": 0.021,       # 52.1% (was 52.2) - small but consistently positive

    # Weather Impact (51.1%) and News Sentiment (49.7%) were retired: both
    # measured at coin-flip level, and dropping them made the ensemble slightly
    # better. Sportsbooks price wind and news into the line, so an agent
    # re-deriving them adds nothing alongside Market Odds. Weather survives as a
    # display-only provider in utils/weather.py.
    #
    # Still not backtestable: ESPN publishes no historical injury archive, so
    # this one has never been scored. It sits at DEFAULT_WEIGHT until a season
    # of logged live predictions can calibrate it. An unmeasured weight has no
    # business outvoting a measured one.
    "Injury Impact": DEFAULT_WEIGHT_PLACEHOLDER,
}

# Confidence above 0.5 that a maximally confident agent can contribute
MAX_CONFIDENCE_EDGE = 0.4


def _agent_weight(name: str, weights: Dict[str, float]) -> float:
    return max(0.0, weights.get(name, DEFAULT_WEIGHT))


def _tally_votes(predictions: Sequence[Dict], home_team: str, away_team: str) -> tuple:
    home_votes = sum(1 for pred in predictions if pred["winner"] == home_team)
    away_votes = sum(1 for pred in predictions if pred["winner"] == away_team)
    return home_votes, away_votes


def _weighted_scores(
    predictions: Sequence[Dict],
    agent_names: Sequence[str],
    home_team: str,
    away_team: str,
    weights: Dict[str, float]
) -> Dict[str, float]:
    """Sum each agent's weighted confidence edge onto the team it picked."""
    scores = {home_team: 0.0, away_team: 0.0}
    for index, pred in enumerate(predictions):
        pick = pred["winner"]
        if pick not in scores:
            continue
        name = agent_names[index] if index < len(agent_names) else ""
        edge = max(0.0, pred["confidence"] - 0.5)
        scores[pick] += _agent_weight(name, weights) * edge
    return scores


def build_consensus(
    predictions: Sequence[Dict[str, Any]],
    agent_names: Sequence[str],
    home_team: str,
    away_team: str,
    method: str = "weighted",
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Combine individual agent predictions into a single ensemble pick.

    Returns a dict with 'winner', 'confidence', 'reasoning', the vote split,
    and (for the weighted method) the per-team weighted scores.
    """
    if not predictions:
        raise ValueError("build_consensus requires at least one prediction")

    weights = AGENT_WEIGHTS if weights is None else weights
    home_votes, away_votes = _tally_votes(predictions, home_team, away_team)
    total_votes = len(predictions)

    if method == "weighted":
        winner, confidence, headline, scores = _decide_weighted(
            predictions, agent_names, home_team, away_team, weights,
            home_votes, away_votes, total_votes
        )
    elif method == "majority":
        winner, confidence, headline = _decide_majority(
            predictions, home_team, away_team, home_votes, away_votes, total_votes
        )
        scores = None
    else:
        raise ValueError(f"Unknown consensus method: {method!r}")

    reasoning_summary = [
        f"{agent_names[i] if i < len(agent_names) else f'agent{i}'}: {pred['reasoning'][:40]}..."
        for i, pred in enumerate(predictions)
    ]
    reasoning = headline + " | ".join(reasoning_summary)

    result = {
        "winner": winner,
        "confidence": round(confidence, 4),
        "reasoning": reasoning,
        "home_votes": home_votes,
        "away_votes": away_votes,
        "method": method
    }
    if scores is not None:
        result["weighted_scores"] = {team: round(value, 4) for team, value in scores.items()}
    return result


def _decide_weighted(
    predictions: Sequence[Dict],
    agent_names: Sequence[str],
    home_team: str,
    away_team: str,
    weights: Dict[str, float],
    home_votes: int,
    away_votes: int,
    total_votes: int
) -> tuple:
    scores = _weighted_scores(predictions, agent_names, home_team, away_team, weights)
    home_score, away_score = scores[home_team], scores[away_team]

    if home_score == away_score:
        # Every agent weighted to zero, or a genuine dead heat - fall back to
        # the raw vote, then to the single most confident agent.
        winner, confidence, headline = _decide_majority(
            predictions, home_team, away_team, home_votes, away_votes, total_votes
        )
        return winner, confidence, "No weighted separation. " + headline, scores

    winner = home_team if home_score > away_score else away_team
    margin = abs(home_score - away_score)

    # Normalise the margin against the most any ensemble could produce, so
    # confidence stays comparable as agents are added or reweighted.
    max_margin = sum(
        _agent_weight(agent_names[i] if i < len(agent_names) else "", weights)
        for i in range(total_votes)
    ) * MAX_CONFIDENCE_EDGE
    share = (margin / max_margin) if max_margin > 0 else 0.0
    confidence = min(0.90, 0.5 + 0.4 * share)

    winning_votes = home_votes if winner == home_team else away_votes
    if winning_votes == total_votes:
        headline = f"Unanimous: all {total_votes} agents favor {winner}. "
    elif winning_votes * 2 > total_votes:
        headline = f"Weighted consensus favors {winner} ({winning_votes}/{total_votes} agents). "
    else:
        headline = (
            f"Weighted consensus favors {winner} despite a {winning_votes}/{total_votes} "
            f"vote split - higher-accuracy agents outweigh the count. "
        )
    return winner, confidence, headline, scores


def _decide_majority(
    predictions: Sequence[Dict],
    home_team: str,
    away_team: str,
    home_votes: int,
    away_votes: int,
    total_votes: int
) -> tuple:
    """One agent, one vote - correct for any number of agents."""
    if home_votes > away_votes:
        winner = home_team
    elif away_votes > home_votes:
        winner = away_team
    else:
        # Genuine tie - the only case that needs a tiebreak
        most_confident = max(predictions, key=lambda pred: pred["confidence"])
        winner = most_confident["winner"]
        confidence = most_confident["confidence"] * 0.9
        headline = (
            f"Split decision ({home_votes}-{away_votes}) resolved by highest "
            f"confidence prediction. "
        )
        return winner, confidence, headline

    winning_predictions = [pred for pred in predictions if pred["winner"] == winner]
    confidence = sum(pred["confidence"] for pred in winning_predictions) / len(winning_predictions)

    winning_votes = max(home_votes, away_votes)
    if winning_votes == total_votes:
        confidence = min(0.95, confidence + 0.05)  # Unanimous agreement bonus
        headline = f"Unanimous decision: all {total_votes} agents favor {winner}. "
    else:
        headline = f"Majority: {winning_votes}/{total_votes} agents favor {winner}. "
    return winner, confidence, headline

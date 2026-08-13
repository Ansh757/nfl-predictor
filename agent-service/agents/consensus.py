"""
consensus.py - Shared ensemble voting logic.

Used by both the /predict endpoint (main.py) and the backtest harness
(backtest.py) so that measured accuracy reflects the code that actually
serves predictions.
"""
from typing import Any, Dict, List, Sequence


def build_consensus(
    predictions: Sequence[Dict[str, Any]],
    agent_names: Sequence[str],
    home_team: str,
    away_team: str
) -> Dict[str, Any]:
    """
    Combine individual agent predictions into a single ensemble pick.

    Voting rules:
      - Majority of agents wins; confidence is the mean confidence of the
        agents on the winning side.
      - Unanimous agreement earns a +0.05 confidence bonus.
      - A 2-2 split is broken by the single most confident agent, and that
        agent's confidence is discounted by 10%.

    Returns a dict with 'winner', 'confidence', 'reasoning', and the vote split.
    """
    home_votes = sum(1 for pred in predictions if pred["winner"] == home_team)
    away_votes = sum(1 for pred in predictions if pred["winner"] == away_team)
    total_votes = len(predictions)

    # Determine overall winner and confidence
    if home_votes > away_votes:
        winner = home_team
        winning_predictions = [pred for pred in predictions if pred["winner"] == home_team]
    else:
        winner = away_team
        winning_predictions = [pred for pred in predictions if pred["winner"] == away_team]

    if winning_predictions:
        confidence = sum(pred["confidence"] for pred in winning_predictions) / len(winning_predictions)
    else:
        # No agent picked either listed team - fall back to a coin-flip confidence
        confidence = 0.5

    # Generate consensus reasoning
    if home_votes == total_votes or away_votes == total_votes:
        reasoning = f"Unanimous decision: All {total_votes} agents favor {winner}. "
        confidence += 0.05  # Boost confidence for unanimous decisions
    elif home_votes == total_votes - 1 or away_votes == total_votes - 1:
        majority_count = max(home_votes, away_votes)
        reasoning = f"Strong majority: {majority_count}/{total_votes} agents favor {winner}. "
    else:  # even split
        # Break tie by highest confidence
        max_confidence_prediction = max(predictions, key=lambda x: x["confidence"])
        winner = max_confidence_prediction["winner"]
        confidence = max_confidence_prediction["confidence"] * 0.9  # Reduce confidence for split
        reasoning = f"Split decision ({home_votes}-{away_votes}) resolved by highest confidence prediction. "

    # Add agent reasoning summary
    reasoning_summary = [
        f"{agent_names[i]}: {pred['reasoning'][:40]}..."
        for i, pred in enumerate(predictions)
    ]
    reasoning += " | ".join(reasoning_summary)

    return {
        "winner": winner,
        "confidence": round(confidence, 4),
        "reasoning": reasoning,
        "home_votes": home_votes,
        "away_votes": away_votes
    }

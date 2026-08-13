"""
odds_agent.py - Market agent backed by real sportsbook lines.

The intended replacement for MarketIntelligenceAgent, which invents its lines
with `random`. This one reads actual consensus pricing from The Odds API,
strips the bookmaker's vig, and uses the resulting fair probability directly.

Weighting caveat
----------------
The free Odds API tier serves current lines only, so this agent cannot be
scored in backtest and ships at the default weight in consensus.AGENT_WEIGHTS.
That is conservative to the point of being unfair to it - closing lines
typically predict straight-up winners in the high 60s - but a weight that has
not been measured on this data has no business outvoting one that has. Raise it
once you have either historical odds or a season of logged live predictions.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from utils.odds_client import OddsClient


class MarketOddsAgent:
    """Predicts from de-vigged consensus moneyline probability."""

    def __init__(self, name: str, client: Optional[OddsClient] = None):
        self.name = name
        self.status = "active"
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        self.client = client or OddsClient()

    async def get_status(self) -> Dict[str, Any]:
        if not self.client.enabled:
            message = "ODDS_API_KEY not configured; agent is inert."
        else:
            events = await self.client.get_all_odds()
            message = (
                f"Live odds for {len(events)} games "
                f"(quota remaining: {self.client.quota_remaining})."
                if events else "Odds feed configured but returned no games."
            )
        return {
            "status": self.status,
            "last_activity": self.last_activity,
            "message": message
        }

    async def refresh(self):
        self.last_activity = datetime.now()
        self.client._cache = None
        self.client._cached_at = None
        await self.client.get_all_odds()
        self.logger.info("Odds refreshed")

    def _neutral(self, home_team: str, reason: str) -> Dict[str, Any]:
        """
        A prediction that contributes nothing. Weighted consensus scores on
        (confidence - 0.5), so 0.50 means this agent is ignored rather than
        adding noise.
        """
        return {
            "winner": home_team,
            "confidence": 0.50,
            "reasoning": reason,
            "home_win_probability": None,
            "home_spread": None,
            "data_available": False,
            "source": "unavailable"
        }

    async def predict_game(self, game_data, game_context: Dict[str, Any]) -> Dict[str, Any]:
        self.last_activity = datetime.now()
        self.status = "reading_market"

        try:
            home_team = game_data.home_team_name
            away_team = game_data.away_team_name

            if not self.client.enabled:
                self.status = "active"
                return self._neutral(home_team, "No ODDS_API_KEY configured. No market signal applied.")

            odds = await self.client.get_game_odds(home_team, away_team)
            if not odds:
                self.status = "active"
                return self._neutral(
                    home_team,
                    f"No market listed for {away_team} @ {home_team} (game may be too far out). "
                    "No market signal applied."
                )

            home_prob = odds["home_win_probability"]
            if home_prob >= 0.5:
                winner, win_prob = home_team, home_prob
            else:
                winner, win_prob = away_team, 1.0 - home_prob

            # De-vigged market probability is already well calibrated
            confidence = max(0.50, min(0.90, win_prob))

            self.status = "active"
            return {
                "winner": winner,
                "confidence": round(confidence, 3),
                "reasoning": self._generate_reasoning(home_team, away_team, odds, winner, win_prob),
                "home_win_probability": home_prob,
                "home_spread": odds["home_spread"],
                "book_count": odds["book_count"],
                "overround": odds["overround"],
                "data_available": True,
                "source": "the-odds-api"
            }

        except Exception as exc:
            self.status = "error"
            self.logger.error(f"Error reading odds: {exc}")
            raise

    def _generate_reasoning(self, home_team: str, away_team: str, odds: Dict,
                            winner: str, win_prob: float) -> str:
        parts = [f"Consensus of {odds['book_count']} sportsbooks"]

        spread = odds.get("home_spread")
        if spread is not None:
            if spread < 0:
                parts.append(f"{home_team} favored by {abs(spread):.1f}")
            elif spread > 0:
                parts.append(f"{away_team} favored by {spread:.1f}")
            else:
                parts.append("Market has this as a pick'em")

        parts.append(f"Fair moneyline gives {winner} a {win_prob:.0%} win probability")
        parts.append(f"Vig removed (overround {odds['overround']:.3f})")
        return ". ".join(parts) + "."

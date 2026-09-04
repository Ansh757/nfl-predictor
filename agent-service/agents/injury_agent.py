"""
injury_agent.py - Roster availability agent backed by real ESPN injury reports.

Replaces the simulated injury numbers that DataCollectorAgent produces. Impact
is weighted by position (a quarterback matters far more than a backup safety)
and by report status (Out hurts more than Questionable).

Calibration
-----------
ESPN returns only *current* injury status, which is why this agent originally
shipped unmeasured. nflverse publishes the official weekly reports back to 2009,
so it is now backtestable through utils/historical_injuries.py - the same route
that got Market Odds from a default weight to a measured one. The backtest feeds
those reports in via `pregame_reports` and drives this class unchanged, so what
is measured is the real position weighting and severity logic.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List

from utils.injury_client import InjuryClient

# Share of team strength attributable to each position. QB dominates; special
# teams barely register.
POSITION_IMPACT = {
    "QB": 0.35,
    "LT": 0.08, "OT": 0.07, "T": 0.07,
    "WR": 0.06, "RB": 0.06, "TE": 0.05,
    "DE": 0.06, "EDGE": 0.06, "OLB": 0.05,
    "CB": 0.05, "DT": 0.05, "LB": 0.04, "ILB": 0.04, "MLB": 0.04,
    "S": 0.04, "FS": 0.04, "SS": 0.04, "DB": 0.04,
    "G": 0.04, "OG": 0.04, "C": 0.04, "OL": 0.04,
    "FB": 0.02, "K": 0.01, "P": 0.01, "LS": 0.005,
}
DEFAULT_POSITION_IMPACT = 0.03

# A team's total injury burden is capped so a long report cannot produce an
# absurd edge - depth charts absorb some of it.
MAX_TEAM_IMPACT = 0.45
# Converts an impact differential into a win-probability edge
IMPACT_TO_EDGE = 0.35


class InjuryImpactAgent:
    """Predicts from the differential in injury burden between the two teams."""

    def __init__(self, name: str, client: InjuryClient = None):
        self.name = name
        self.status = "active"
        # Point-in-time reports supplied by the backtest, keyed by game id.
        # Same convention as EloRatingAgent.pregame_ratings and
        # RestTravelAgent.pregame_rest: never mutated once a run starts, so
        # twelve concurrent games cannot read each other's week.
        self.pregame_reports: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        self.client = client or InjuryClient()

    async def get_status(self) -> Dict[str, Any]:
        report = await self.client.get_all_injuries()
        total = sum(len(items) for items in report.values())
        return {
            "status": self.status,
            "last_activity": self.last_activity,
            "message": (
                f"Tracking {total} injuries across {len(report)} teams (ESPN)."
                if report else "Injury feed unavailable; agent is inert."
            )
        }

    async def refresh(self):
        self.last_activity = datetime.now()
        self.client._cache = None
        self.client._cached_at = None
        await self.client.get_all_injuries()
        self.logger.info("Injury report refreshed")

    def _team_impact(self, injuries: List[Dict[str, Any]]) -> float:
        """Weighted injury burden for one team, capped."""
        total = sum(
            POSITION_IMPACT.get(entry["position"].upper(), DEFAULT_POSITION_IMPACT)
            * entry["severity"]
            for entry in injuries
        )
        return min(MAX_TEAM_IMPACT, total)

    async def predict_game(self, game_data, game_context: Dict[str, Any]) -> Dict[str, Any]:
        self.last_activity = datetime.now()
        self.status = "analyzing_injuries"

        try:
            home_team = game_data.home_team_name
            away_team = game_data.away_team_name

            game_id = getattr(game_data, "game_id", None)
            if game_id is not None and game_id in self.pregame_reports:
                report = self.pregame_reports[game_id]
            else:
                report = await self.client.get_all_injuries()

            if not report:
                # No data: return an exactly-neutral prediction. Weighted
                # consensus scores on (confidence - 0.5), so 0.5 contributes
                # nothing rather than injecting noise.
                self.status = "active"
                return {
                    "winner": home_team,
                    "confidence": 0.50,
                    "reasoning": "Injury feed unavailable. No injury signal applied.",
                    "home_injury_impact": None,
                    "away_injury_impact": None,
                    "data_available": False,
                    "source": "unavailable"
                }

            home_injuries = report.get(home_team, [])
            away_injuries = report.get(away_team, [])
            home_impact = self._team_impact(home_injuries)
            away_impact = self._team_impact(away_injuries)

            # A healthier team is favoured: positive edge means home is healthier
            edge = (away_impact - home_impact) * IMPACT_TO_EDGE

            if edge > 0.005:
                winner = home_team
            elif edge < -0.005:
                winner = away_team
            else:
                # Equally banged up - no signal either way
                self.status = "active"
                return {
                    "winner": home_team,
                    "confidence": 0.50,
                    "reasoning": (
                        f"Comparable injury burden ({home_team} {home_impact:.2f} vs "
                        f"{away_team} {away_impact:.2f}). No injury edge."
                    ),
                    "home_injury_impact": round(home_impact, 3),
                    "away_injury_impact": round(away_impact, 3),
                    "data_available": True,
                    "source": "espn"
                }

            confidence = min(0.75, 0.50 + abs(edge))

            self.status = "active"
            return {
                "winner": winner,
                "confidence": round(confidence, 3),
                "reasoning": self._generate_reasoning(
                    home_team, away_team, home_injuries, away_injuries,
                    home_impact, away_impact, winner
                ),
                "home_injury_impact": round(home_impact, 3),
                "away_injury_impact": round(away_impact, 3),
                "home_key_injuries": self._key_injuries(home_injuries),
                "away_key_injuries": self._key_injuries(away_injuries),
                "data_available": True,
                "source": "espn"
            }

        except Exception as exc:
            self.status = "error"
            self.logger.error(f"Error in injury analysis: {exc}")
            raise

    def _key_injuries(self, injuries: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, str]]:
        ranked = sorted(
            injuries,
            key=lambda entry: POSITION_IMPACT.get(entry["position"].upper(), DEFAULT_POSITION_IMPACT)
            * entry["severity"],
            reverse=True
        )
        return [
            {"player": e["player"], "position": e["position"], "status": e["status"]}
            for e in ranked[:limit]
        ]

    def _generate_reasoning(self, home_team: str, away_team: str,
                            home_injuries: List[Dict], away_injuries: List[Dict],
                            home_impact: float, away_impact: float, winner: str) -> str:
        parts = [
            f"{home_team} {len(home_injuries)} injuries (impact {home_impact:.2f}), "
            f"{away_team} {len(away_injuries)} (impact {away_impact:.2f})"
        ]

        for team, injuries in ((home_team, home_injuries), (away_team, away_injuries)):
            quarterbacks = [
                e for e in injuries
                if e["position"].upper() == "QB" and e["severity"] >= 0.75
            ]
            if quarterbacks:
                parts.append(
                    f"{team} QB {quarterbacks[0]['player']} is {quarterbacks[0]['status'].lower()}"
                )

        healthier = home_team if home_impact < away_impact else away_team
        parts.append(f"{healthier} is the healthier side")
        parts.append(f"Edge to {winner}")
        return ". ".join(parts) + "."

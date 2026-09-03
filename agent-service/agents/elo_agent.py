"""
elo_agent.py - Power-rating agent backed by Elo.

Unlike the Basic Predictor, which looks at a rolling window of raw results,
Elo carries the whole history forward and accounts for opponent quality: a 3-1
record against strong teams outranks 3-1 against weak ones.

Ratings come from the local game log, so this agent makes no network calls and
is fully replayable in backtest.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from utils.elo import EloRatingSystem
from utils.venues import game_context as resolve_game_context


class EloRatingAgent:
    """Predicts from Elo power ratings and the implied win probability."""

    def __init__(self, name: str, db_path: str = "nfl_schedule.db",
                 rating_system: Optional[EloRatingSystem] = None):
        self.name = name
        self.status = "active"
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        self.db_path = db_path

        # Pre-kickoff ratings keyed by game_id. The backtest populates this so
        # each game is scored on ratings as they stood at the time; in
        # production it stays empty and current ratings are used.
        self.pregame_ratings: Dict[int, Tuple[float, float]] = {}

        if rating_system is not None:
            self.elo = rating_system
        else:
            try:
                self.elo = EloRatingSystem.from_database(db_path)
                self.logger.info(
                    f"Elo ratings built for {len(self.elo.ratings)} teams from {db_path}"
                )
            except Exception as exc:
                self.logger.warning(f"Could not build Elo ratings ({exc}); using league average")
                self.elo = EloRatingSystem()

    async def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "last_activity": self.last_activity,
            "message": f"Elo ratings loaded for {len(self.elo.ratings)} teams."
        }

    async def refresh(self):
        """Rebuild ratings so newly completed games are reflected."""
        self.last_activity = datetime.now()
        try:
            self.elo = EloRatingSystem.from_database(self.db_path)
            self.logger.info(f"Elo ratings rebuilt for {len(self.elo.ratings)} teams")
        except Exception as exc:
            self.logger.warning(f"Elo refresh failed: {exc}")

    def _ratings_for(self, game_data) -> Tuple[float, float]:
        """Point-in-time ratings if the caller supplied them, else current."""
        game_id = getattr(game_data, "game_id", None)
        if game_id is not None and game_id in self.pregame_ratings:
            return self.pregame_ratings[game_id]
        return (
            self.elo.rating(game_data.home_team_name),
            self.elo.rating(game_data.away_team_name)
        )

    async def predict_game(self, game_data, game_context: Dict[str, Any]) -> Dict[str, Any]:
        self.last_activity = datetime.now()
        self.status = "rating_teams"

        try:
            home_team = game_data.home_team_name
            away_team = game_data.away_team_name

            home_rating, away_rating = self._ratings_for(game_data)

            # Home-field advantage is a fact about the venue, not about the
            # matchup. At a neutral site the designated home team is not at
            # home, so it does not get the 65 points - this is correcting the
            # game context, not applying a travel adjustment. Independent of
            # whether the game is international: a Super Bowl is neutral and
            # domestic, and both get exactly this treatment.
            venue_context = resolve_game_context(
                home_team,
                getattr(game_data, "venue", None),
                getattr(game_data, "neutral_site", None),
                getattr(game_data, "venue_country", None),
            )
            neutral = venue_context["neutral_site"]
            home_win_prob = self.elo.expected_score(home_rating, away_rating, neutral=neutral)

            if home_win_prob >= 0.5:
                winner, win_prob = home_team, home_win_prob
            else:
                winner, win_prob = away_team, 1.0 - home_win_prob

            # Elo's win probability is already calibrated, so use it directly
            confidence = max(0.50, min(0.90, win_prob))

            reasoning = self._generate_reasoning(
                home_team, away_team, home_rating, away_rating, winner, home_win_prob,
                venue_context
            )

            self.status = "active"
            return {
                "winner": winner,
                "confidence": round(confidence, 3),
                "reasoning": reasoning,
                "home_elo": round(home_rating, 1),
                "away_elo": round(away_rating, 1),
                "elo_gap": round(home_rating - away_rating, 1),
                "home_win_probability": round(home_win_prob, 3),
                "neutral_site": neutral,
                "international_game": venue_context["international_game"],
                "venue_country": venue_context["venue_country"],
                "source": "elo"
            }

        except Exception as exc:
            self.status = "error"
            self.logger.error(f"Error in Elo prediction: {exc}")
            raise

    def _generate_reasoning(self, home_team: str, away_team: str,
                            home_rating: float, away_rating: float,
                            winner: str, home_win_prob: float,
                            venue_context: Optional[Dict[str, Any]] = None) -> str:
        parts = [
            f"Elo {home_team} {home_rating:.0f} vs {away_team} {away_rating:.0f}"
        ]

        gap = abs(home_rating - away_rating)
        stronger = home_team if home_rating > away_rating else away_team
        if gap > 150:
            parts.append(f"{stronger} holds a large {gap:.0f}-point rating edge")
        elif gap > 60:
            parts.append(f"{stronger} rates {gap:.0f} points higher")
        else:
            parts.append("Teams are closely rated")

        venue_context = venue_context or {}
        if venue_context.get("neutral_site"):
            # Deliberately says nothing about "international" here - that
            # wording belongs to the travel agent, and this sentence is equally
            # true of a domestic Super Bowl.
            where = venue_context.get("venue_country")
            location = f" ({where})" if where and venue_context.get("international_game") else ""
            parts.append(f"Neutral site{location} - no home-field advantage applied")
        else:
            parts.append(f"Home field is worth {self.elo.home_advantage:.0f} Elo points")

        # Both phrasings below appeal to home field, so neither can be used
        # where there is none - at a neutral site the rating gap is the whole
        # story and saying otherwise describes a game that is not being played.
        if venue_context.get("neutral_site"):
            if winner != stronger:
                parts.append(f"{winner} favoured despite the lower rating")
        elif winner == home_team and home_rating < away_rating:
            parts.append(f"{home_team} favored on home field despite the lower rating")
        elif winner == away_team:
            parts.append(f"{away_team}'s rating overcomes home field")

        win_prob = home_win_prob if winner == home_team else 1.0 - home_win_prob
        parts.append(f"Implied win probability {win_prob:.0%}")

        return ". ".join(parts) + "."

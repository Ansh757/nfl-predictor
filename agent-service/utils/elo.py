"""
elo.py - Elo power ratings computed from the local game log.

Standard NFL-flavoured Elo: a margin-of-victory multiplier so blowouts move
ratings more than one-score wins, a home-field bonus expressed in Elo points,
and a regression toward the mean between seasons so last year's champion does
not start the new year overrated.

No external data source - everything comes from the `games` table that
schedule_loader.py already populates.
"""
import math
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

# Tuned to the widely used FiveThirtyEight NFL Elo settings
DEFAULT_K = 20.0
DEFAULT_HOME_ADVANTAGE = 65.0     # Elo points, worth roughly 2.5 game points
DEFAULT_MEAN = 1505.0
DEFAULT_REGRESSION = 1.0 / 3.0    # Share pulled back to the mean each offseason


class EloRatingSystem:
    """Builds Elo ratings by walking a game log forward in time."""

    def __init__(
        self,
        k: float = DEFAULT_K,
        home_advantage: float = DEFAULT_HOME_ADVANTAGE,
        mean: float = DEFAULT_MEAN,
        regression: float = DEFAULT_REGRESSION
    ):
        self.k = k
        self.home_advantage = home_advantage
        self.mean = mean
        self.regression = regression

        self.ratings: Dict[str, float] = {}
        # game_id -> (home_rating_before_kickoff, away_rating_before_kickoff)
        self.pregame_ratings: Dict[int, Tuple[float, float]] = {}

    # ------------------------------------------------------------------ maths

    def expected_score(self, home_rating: float, away_rating: float,
                       neutral: bool = False) -> float:
        """Probability the home team wins, from the rating gap."""
        adjustment = 0.0 if neutral else self.home_advantage
        diff = (home_rating + adjustment) - away_rating
        return 1.0 / (1.0 + math.pow(10.0, -diff / 400.0))

    def _mov_multiplier(self, margin: int, winner_rating_diff: float) -> float:
        """
        Scale the update by margin of victory, damped by how favoured the
        winner already was - so a strong team beating a weak one by 20 moves
        less than an upset by the same margin.
        """
        return math.log(abs(margin) + 1.0) * (2.2 / ((winner_rating_diff * 0.001) + 2.2))

    # ------------------------------------------------------------------ build

    def rating(self, team: str) -> float:
        return self.ratings.get(team, self.mean)

    def _regress_to_mean(self):
        for team in self.ratings:
            self.ratings[team] = (
                self.ratings[team] * (1.0 - self.regression) + self.mean * self.regression
            )

    def build(self, games: List[Dict[str, Any]]):
        """
        Process a chronologically ordered game log, recording each team's
        rating as it stood *before* every game.

        Each game needs: game_id, season, home_team, away_team,
        home_score, away_score.
        """
        current_season: Optional[int] = None

        for game in games:
            season = game.get("season")
            if current_season is not None and season != current_season:
                self._regress_to_mean()
            current_season = season

            home, away = game["home_team"], game["away_team"]
            home_rating, away_rating = self.rating(home), self.rating(away)

            game_id = game.get("game_id")
            if game_id is not None:
                self.pregame_ratings[game_id] = (home_rating, away_rating)

            home_score, away_score = game.get("home_score"), game.get("away_score")
            if home_score is None or away_score is None:
                continue  # Unplayed - ratings recorded, nothing to learn from

            # Actual result, from the home team's perspective
            if home_score > away_score:
                actual = 1.0
            elif home_score < away_score:
                actual = 0.0
            else:
                actual = 0.5

            expected = self.expected_score(home_rating, away_rating)
            margin = home_score - away_score

            if margin == 0:
                multiplier = 1.0
            else:
                # Rating edge held by whoever actually won, including home field
                if margin > 0:
                    winner_diff = (home_rating + self.home_advantage) - away_rating
                else:
                    winner_diff = away_rating - (home_rating + self.home_advantage)
                multiplier = self._mov_multiplier(margin, max(winner_diff, -400.0))

            shift = self.k * multiplier * (actual - expected)
            self.ratings[home] = home_rating + shift
            self.ratings[away] = away_rating - shift

    # ------------------------------------------------------------------- load

    @classmethod
    def from_database(cls, db_path: str, through_season: Optional[int] = None, **kwargs):
        """Build ratings from every completed game in the schedule database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        query = '''
            SELECT game_id, season, game_date, home_team, away_team,
                   home_score, away_score
            FROM games
            WHERE home_team IS NOT NULL AND away_team IS NOT NULL
              -- A fabricated result moves ratings exactly as a real one does.
              -- The invented 2025 Super Bowl sat between Seattle and New
              -- England, who then opened 2026 against each other, so both sides
              -- of that game carried a rating earned in a game never played.
              AND COALESCE(is_synthetic, 0) = 0
        '''
        params: Tuple = ()
        if through_season is not None:
            query += " AND season <= ?"
            params = (through_season,)
        query += " ORDER BY game_date"

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        games = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()

        system = cls(**kwargs)
        system.build(games)
        return system

    def top_teams(self, limit: int = 10) -> List[Tuple[str, float]]:
        return sorted(self.ratings.items(), key=lambda item: item[1], reverse=True)[:limit]

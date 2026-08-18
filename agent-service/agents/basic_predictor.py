import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import os

# Import API clients
from utils.api_clients import APIManager, get_team_abbreviation
from utils.team_stats import load_game_log, team_stats_as_of

class BasicPredictorAgent:
    """
    Enhanced NFL Game Prediction Agent with Real API Data
    
    This agent makes predictions based on:
    - Team win/loss records from ESPN/PFR
    - Point differential from real game data
    - Recent form and momentum
    - Home/away performance splits
    - Realistic home field advantage
    """
    
    def __init__(self, name: str, db_path: str = "nfl_schedule.db"):
        self.name = name
        self.status = "active"
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        self.db_path = db_path

        # Real results are the primary source. ESPN is only a fallback for teams
        # with no local history, because its team endpoint returns wins and
        # losses and nothing else - no points, no splits, no form.
        self._game_log = None

        # Point-in-time overrides keyed by game_id: {game_id: {team: stats}}.
        # The backtest fills this so each game is scored on the form as it stood
        # at that kickoff. It must be game-keyed, not team-keyed - 12 games run
        # concurrently, and a shared team-keyed cache lets one game overwrite
        # another's stats mid-flight, which made results depend on scheduling.
        self.pregame_stats: Dict[Any, Dict[str, Dict[str, Any]]] = {}

        # Initialize API manager
        nfl_api_key = os.getenv('NFL_API_KEY')  # Optional
        weather_api_key = os.getenv('WEATHER_API_KEY')  # Optional
        self.api_manager = APIManager(nfl_api_key, weather_api_key)
        
        # Cache for team stats (2 hour TTL)
        self.stats_cache = {}
        self.cache_duration = timedelta(hours=2)
        
        # Prediction weights
        self.weights = {
            "win_rate": 0.35,
            "point_differential": 0.30,
            "recent_form": 0.20,
            "home_away_split": 0.10,
            "strength_of_schedule": 0.05
        }
        
        # Home field advantage
        self.home_field_advantage = 2.5
        
        self.logger.info(f"BasicPredictorAgent '{name}' initialized against {db_path}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Return current agent status"""
        return {
            "status": self.status,
            "last_activity": self.last_activity,
            "message": f"Ready with real API data. Cache: {len(self.stats_cache)} teams."
        }
    
    async def refresh(self):
        """Refresh agent data and clear old cache"""
        self.last_activity = datetime.now()
        
        # Clear expired cache
        current_time = datetime.now()
        expired_keys = [
            key for key, (data, timestamp) in self.stats_cache.items()
            if current_time - timestamp > self.cache_duration
        ]
        for key in expired_keys:
            del self.stats_cache[key]
        
        # Drop the log so newly settled results are picked up
        self._game_log = None
        self.logger.info(f"Agent refreshed. Cleared {len(expired_keys)} expired entries")
    
    def _log(self):
        """Game log, loaded once and refreshed by refresh()."""
        if self._game_log is None:
            try:
                self._game_log = load_game_log(self.db_path)
                self.logger.info(f"Game log loaded for {len(self._game_log)} teams")
            except Exception as exc:
                self.logger.warning(f"Could not load game log from {self.db_path}: {exc}")
                self._game_log = {}
        return self._game_log

    async def get_team_stats(self, team_name: str) -> Dict[str, Any]:
        """
        Team profile from real results.

        Order of preference:
          1. An injected cache entry - the backtest uses this to supply
             point-in-time stats for the game being replayed.
          2. The local game log, which carries actual scores and therefore real
             point differential, form and home/away splits.
          3. ESPN, which supplies the win/loss record only. Everything it cannot
             answer is left neutral rather than invented.
        """
        cache_key = f"{team_name}_stats"
        if cache_key in self.stats_cache:
            data, timestamp = self.stats_cache[cache_key]
            if datetime.now() - timestamp < self.cache_duration:
                return data

        stats = team_stats_as_of(self._log(), team_name, datetime.now().isoformat())

        if stats["source"] == "no_history":
            team_abbr = get_team_abbreviation(team_name)
            api_stats = await self.api_manager.get_team_stats(team_abbr)
            if api_stats:
                stats = self._from_record_only(api_stats, team_name)
                self.logger.info(f"No local history for {team_name}; using ESPN record only")
            else:
                self.logger.warning(f"No data at all for {team_name}; using a neutral profile")

        self.stats_cache[cache_key] = (stats, datetime.now())
        return stats

    def _from_record_only(self, api_stats: Dict, team_name: str) -> Dict[str, Any]:
        """
        Build a profile from a win/loss record alone.

        Everything the record cannot support is left neutral. The previous
        version filled these with random.uniform() draws, which meant roughly
        two thirds of the strength score was noise on every live prediction.
        """
        win_rate = api_stats.get("win_rate", 0.5)
        return {
            "team": team_name,
            "win_rate": win_rate,
            # Neutral, not fabricated: ESPN gives no points data
            "point_differential": api_stats.get("point_differential", 0.0),
            "points_per_game": api_stats.get("points_per_game", 22.0),
            "points_allowed_per_game": api_stats.get("points_allowed_per_game", 22.0),
            # Derived deterministically from the record rather than sampled
            "recent_form": [1 if win_rate >= 0.5 else 0] * 4,
            "home_win_rate": win_rate,
            "away_win_rate": win_rate,
            "strength_of_schedule": 0.5,
            "last_updated": datetime.now(),
            "games_used": api_stats.get("wins", 0) + api_stats.get("losses", 0),
            "source": f"record_only:{api_stats.get('source', 'api')}",
        }

    async def predict_game(self, game_data, game_context: Dict[str, Any]) -> Dict[str, Any]:
        """Make prediction using real API data"""
        
        self.last_activity = datetime.now()
        self.status = "predicting"
        
        try:
            home_team = game_data.home_team_name
            away_team = game_data.away_team_name
            
            self.logger.info(f"Predicting {away_team} @ {home_team} using real stats")
            
            # Get stats for both teams
            override = self.pregame_stats.get(getattr(game_data, "game_id", None))
            if override:
                home_stats = override[home_team]
                away_stats = override[away_team]
            else:
                home_stats = await self.get_team_stats(home_team)
                away_stats = await self.get_team_stats(away_team)
            
            # Log data sources
            home_source = home_stats.get('source', 'unknown')
            away_source = away_stats.get('source', 'unknown')
            self.logger.info(f"Data sources - {home_team}: {home_source}, {away_team}: {away_source}")
            
            # Calculate strength scores
            home_score = self._calculate_team_strength(home_stats, is_home=True)
            away_score = self._calculate_team_strength(away_stats, is_home=False)
            
            # Add home field advantage
            home_score += self.home_field_advantage
            
            # Determine winner
            if home_score > away_score:
                winner = home_team
                score_diff = home_score - away_score
            else:
                winner = away_team
                score_diff = away_score - home_score
            
            # Calculate confidence
            base_confidence = 0.50
            confidence_boost = min(0.40, score_diff / 20)
            confidence = base_confidence + confidence_boost
            confidence = max(0.50, min(0.90, confidence))
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                home_team, away_team,
                home_stats, away_stats,
                home_score, away_score,
                winner, confidence
            )
            
            prediction = {
                "winner": winner,
                "confidence": round(confidence, 3),
                "reasoning": reasoning,
                "home_strength_score": round(home_score, 2),
                "away_strength_score": round(away_score, 2),
                "score_differential": round(score_diff, 2),
                "key_factors": self._identify_key_factors(home_stats, away_stats, winner),
                "data_quality": "game_log" if home_source == away_source == "game_log" else f"{home_source}/{away_source}"
            }
            
            self.logger.info(f"Prediction: {winner} wins ({confidence:.1%}) [Data: {prediction['data_quality']}]")
            self.status = "active"
            
            return prediction
            
        except Exception as e:
            self.status = "error"
            self.logger.error(f"Error making prediction: {e}")
            raise
    
    def _calculate_team_strength(self, stats: Dict[str, Any], is_home: bool) -> float:
        """Calculate team strength score"""
        
        score = 0.0
        
        # Win rate component
        win_rate = stats["home_win_rate"] if is_home else stats["away_win_rate"]
        score += win_rate * 100 * self.weights["win_rate"]
        
        # Point differential component
        point_diff_score = (stats["point_differential"] + 10) * 1.5
        point_diff_score = max(0, min(30, point_diff_score))
        score += point_diff_score * self.weights["point_differential"]
        
        # Recent form/momentum
        recent_wins = sum(stats["recent_form"])
        momentum_score = (recent_wins / 4) * 100
        score += momentum_score * self.weights["recent_form"]
        
        # Home/away performance
        split_performance = stats["home_win_rate"] if is_home else stats["away_win_rate"]
        score += split_performance * 100 * self.weights["home_away_split"]
        
        # Strength of schedule
        sos_bonus = stats["strength_of_schedule"] * 100
        score += sos_bonus * self.weights["strength_of_schedule"]
        
        return score
    
    def _identify_key_factors(self, home_stats: Dict, away_stats: Dict, winner: str) -> list:
        """Identify key factors driving the prediction"""
        factors = []
        
        # Win rate advantage
        home_wr = home_stats["home_win_rate"]
        away_wr = away_stats["away_win_rate"]
        if abs(home_wr - away_wr) > 0.15:
            better_team = home_stats["team"] if home_wr > away_wr else away_stats["team"]
            factors.append(f"{better_team} has superior win rate ({max(home_wr, away_wr):.1%} vs {min(home_wr, away_wr):.1%})")
        
        # Point differential
        home_pd = home_stats["point_differential"]
        away_pd = away_stats["point_differential"]
        if abs(home_pd - away_pd) > 3:
            better_team = home_stats["team"] if home_pd > away_pd else away_stats["team"]
            factors.append(f"{better_team} has better point differential ({max(home_pd, away_pd):+.1f} vs {min(home_pd, away_pd):+.1f})")
        
        # Recent momentum
        home_recent = sum(home_stats["recent_form"])
        away_recent = sum(away_stats["recent_form"])
        if abs(home_recent - away_recent) >= 2:
            hot_team = home_stats["team"] if home_recent > away_recent else away_stats["team"]
            hot_wins = max(home_recent, away_recent)
            factors.append(f"{hot_team} is hot with {hot_wins} wins in last 4 games")
        
        return factors[:3]
    
    def _generate_reasoning(self, home_team: str, away_team: str,
                          home_stats: Dict, away_stats: Dict,
                          home_score: float, away_score: float,
                          winner: str, confidence: float) -> str:
        """Generate reasoning"""
        
        reasoning_parts = []
        
        # Data source note
        if home_stats.get('source') not in ['simulation', 'unknown']:
            reasoning_parts.append(f"Using real {home_stats['source']} data")
        
        # Win rate comparison
        home_wr = home_stats["home_win_rate"]
        away_wr = away_stats["away_win_rate"]
        
        if winner == home_team:
            if home_wr > away_wr:
                reasoning_parts.append(f"{home_team} has better home record ({home_wr:.1%} vs {away_team}'s {away_wr:.1%} away)")
            else:
                reasoning_parts.append(f"{home_team} benefits from home field advantage")
        else:
            reasoning_parts.append(f"{away_team}'s road performance ({away_wr:.1%}) overcomes home advantage")
        
        # Point differential
        home_pd = home_stats["point_differential"]
        away_pd = away_stats["point_differential"]
        
        if abs(home_pd - away_pd) > 3:
            if home_pd > away_pd:
                reasoning_parts.append(f"{home_team} dominates point differential ({home_pd:+.1f} vs {away_pd:+.1f})")
            else:
                reasoning_parts.append(f"{away_team} has superior point differential ({away_pd:+.1f} vs {home_pd:+.1f})")
        
        # Confidence
        if confidence > 0.75:
            reasoning_parts.append(f"High confidence - {winner} has clear advantage")
        elif confidence > 0.60:
            reasoning_parts.append(f"Moderate confidence in {winner}")
        else:
            reasoning_parts.append(f"Low confidence - evenly matched")
        
        return ". ".join(reasoning_parts[:4]) + "."
    
    async def cleanup(self):
        """Close API connections"""
        await self.api_manager.close_all()
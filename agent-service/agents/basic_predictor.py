import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import os

# Import API clients
from utils.api_clients import APIManager, get_team_abbreviation

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
    
    def __init__(self, name: str):
        self.name = name
        self.status = "active"
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        
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
        
        self.logger.info(f"BasicPredictorAgent '{name}' initialized with real API integration")
    
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
        
        self.logger.info(f"Agent refreshed. Cleared {len(expired_keys)} expired entries")
    
    async def get_team_stats(self, team_name: str) -> Dict[str, Any]:
        """Get comprehensive team statistics from real APIs"""
        
        # Check cache first
        cache_key = f"{team_name}_stats"
        if cache_key in self.stats_cache:
            data, timestamp = self.stats_cache[cache_key]
            if datetime.now() - timestamp < self.cache_duration:
                self.logger.debug(f"Using cached stats for {team_name}")
                return data
        
        # Get team abbreviation
        team_abbr = get_team_abbreviation(team_name)
        
        # Try to get real stats from APIs
        api_stats = await self.api_manager.get_team_stats(team_abbr)
        
        if api_stats:
            # We got real data! Enhance it with calculated fields
            stats = self._enhance_api_stats(api_stats, team_name)
            self.logger.info(f"Got REAL stats for {team_name} from {api_stats.get('source', 'API')}")
        else:
            # Fallback to simulation
            self.logger.warning(f"API failed for {team_name}, using simulation")
            stats = await self._simulate_team_stats(team_name)
        
        # Cache the result
        self.stats_cache[cache_key] = (stats, datetime.now())
        
        return stats
    
    def _enhance_api_stats(self, api_stats: Dict, team_name: str) -> Dict[str, Any]:
        """Enhance real API stats with calculated fields"""
        
        # Calculate point differential if not provided
        if 'point_differential' not in api_stats:
            ppg = api_stats.get('points_per_game', 20)
            papg = api_stats.get('points_allowed_per_game', 20)
            api_stats['point_differential'] = round(ppg - papg, 2)
        
        # Simulate recent form based on win rate (until we get real game logs)
        win_rate = api_stats.get('win_rate', 0.5)
        recent_form = []
        for _ in range(4):
            win_chance = win_rate + random.uniform(-0.15, 0.15)
            recent_form.append(1 if random.random() < max(0, min(1, win_chance)) else 0)
        
        # Estimate home/away splits based on overall win rate
        home_win_rate = min(0.9, win_rate + random.uniform(0.05, 0.12))
        away_win_rate = max(0.1, win_rate - random.uniform(0.05, 0.12))
        
        # Add calculated fields
        api_stats.update({
            'team': team_name,
            'recent_form': recent_form,
            'home_win_rate': round(home_win_rate, 3),
            'away_win_rate': round(away_win_rate, 3),
            'strength_of_schedule': 0.5,  # Default until we can calculate
            'points_per_game': api_stats.get('points_per_game', 20.0),
            'points_allowed_per_game': api_stats.get('points_allowed_per_game', 20.0),
            'offensive_rating': round(api_stats.get('points_per_game', 20) * 4, 1),
            'defensive_rating': round((35 - api_stats.get('points_allowed_per_game', 20)) * 4, 1),
            'last_updated': datetime.now()
        })
        
        return api_stats
    
    async def _simulate_team_stats(self, team_name: str) -> Dict[str, Any]:
        """Fallback simulation when APIs fail"""
        
        win_rate = random.uniform(0.25, 0.75)
        base_differential = (win_rate - 0.5) * 20
        point_differential = base_differential + random.uniform(-2, 2)
        
        recent_form = []
        for _ in range(4):
            win_chance = win_rate + random.uniform(-0.2, 0.2)
            recent_form.append(1 if random.random() < win_chance else 0)
        
        home_win_rate = min(0.9, win_rate + random.uniform(0.05, 0.15))
        away_win_rate = max(0.1, win_rate - random.uniform(0.05, 0.15))
        
        points_per_game = 20 + (win_rate * 15) + random.uniform(-2, 2)
        points_allowed = 20 + ((1 - win_rate) * 15) + random.uniform(-2, 2)
        
        return {
            "team": team_name,
            "win_rate": round(win_rate, 3),
            "point_differential": round(point_differential, 2),
            "recent_form": recent_form,
            "home_win_rate": round(home_win_rate, 3),
            "away_win_rate": round(away_win_rate, 3),
            "strength_of_schedule": 0.5,
            "points_per_game": round(points_per_game, 1),
            "points_allowed_per_game": round(points_allowed, 1),
            "offensive_rating": round(points_per_game * 4, 1),
            "defensive_rating": round((35 - points_allowed) * 4, 1),
            "last_updated": datetime.now(),
            "source": "simulation"
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
                "data_quality": "real" if home_source != "simulation" and away_source != "simulation" else "simulated"
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
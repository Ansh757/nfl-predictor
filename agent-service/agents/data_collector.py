import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, List
import logging

class DataCollectorAgent:
    """
    Data Collection Agent for NFL Games
    
    This agent gathers additional context for game predictions:
    - Weather conditions (simulated for now)
    - Recent team performance (simulated)
    - Injury reports (simulated)
    - Historical matchups (simulated)
    
    Later we'll integrate with real APIs (ESPN, weather services, etc.)
    """
    
    def __init__(self, name: str):
        self.name = name
        self.status = "active"
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        
        # Cache for data (in real implementation, we'd use Redis)
        self.cache = {}
        
        self.logger.info(f"DataCollectorAgent '{name}' initialized")
    
    async def get_status(self) -> Dict[str, Any]:
        """Return current agent status"""
        return {
            "status": self.status,
            "last_activity": self.last_activity,
            "message": f"Ready to collect game data. Cache contains {len(self.cache)} entries."
        }
    
    async def refresh(self):
        """Refresh agent data and clear cache"""
        self.cache.clear()
        self.last_activity = datetime.now()
        self.logger.info("Agent refreshed, cache cleared")
    
    async def collect_game_data(self, game_data) -> Dict[str, Any]:
        """
        Collect comprehensive data for a game
        
        Args:
            game_data: Basic game information
            
        Returns:
            Dictionary with all collected data
        """
        self.last_activity = datetime.now()
        self.status = "collecting_data"
        
        try:
            cache_key = f"game_{game_data.game_id}"
            
            # Check cache first
            if cache_key in self.cache:
                self.logger.info(f"Using cached data for game {game_data.game_id}")
                return self.cache[cache_key]
            
            self.logger.info(f"Collecting data for {game_data.away_team_name} @ {game_data.home_team_name}")
            
            # Simulate parallel data collection
            tasks = [
                self._get_weather_data(game_data),
                self._get_team_stats(game_data.home_team_name),
                self._get_team_stats(game_data.away_team_name),
                self._get_injury_reports(game_data.home_team_name),
                self._get_injury_reports(game_data.away_team_name),
                self._get_historical_matchup(game_data.home_team_name, game_data.away_team_name)
            ]
            
            results = await asyncio.gather(*tasks)
            
            context = {
                "weather": results[0],
                "home_team_stats": results[1],
                "away_team_stats": results[2],
                "home_injuries": results[3],
                "away_injuries": results[4],
                "historical_matchup": results[5],
                "collection_time": datetime.now(),
                "data_quality": "simulated"  # Will be "live" when we use real APIs
            }
            
            # Cache the result
            self.cache[cache_key] = context
            
            self.logger.info(f"Data collection complete for game {game_data.game_id}")
            self.status = "active"
            
            return context
            
        except Exception as e:
            self.status = "error"
            self.logger.error(f"Error collecting game data: {e}")
            raise
    
    async def _get_weather_data(self, game_data) -> Dict[str, Any]:
        """Simulate weather data collection"""
        await asyncio.sleep(0.1)  # Simulate API call delay
        
        if game_data.is_dome:
            return {
                "condition": "dome",
                "temperature": 72,
                "humidity": 45,
                "wind_speed": 0,
                "precipitation": 0,
                "impact": "neutral"
            }
        
        # Simulate outdoor weather
        import random
        
        conditions = ["clear", "cloudy", "light_rain", "heavy_rain", "snow", "windy"]
        condition = random.choice(conditions)
        
        weather = {
            "condition": condition,
            "temperature": random.randint(20, 85),
            "humidity": random.randint(30, 90),
            "wind_speed": random.randint(0, 25),
            "precipitation": random.randint(0, 100) if condition in ["light_rain", "heavy_rain", "snow"] else 0
        }
        
        # Determine impact on game
        if weather["wind_speed"] > 15:
            weather["impact"] = "favors_running_game"
        elif weather["precipitation"] > 50:
            weather["impact"] = "favors_defense"
        elif weather["temperature"] < 32:
            weather["impact"] = "cold_weather_game"
        else:
            weather["impact"] = "neutral"
        
        return weather
    
    async def _get_team_stats(self, team_name: str) -> Dict[str, Any]:
        """Simulate team statistics collection"""
        await asyncio.sleep(0.1)  # Simulate API call delay
        
        import random
        
        return {
            "team": team_name,
            "recent_form": random.choice(["hot", "cold", "average"]),
            "points_per_game": round(random.uniform(18, 35), 1),
            "points_allowed_per_game": round(random.uniform(18, 35), 1),
            "total_yards_per_game": random.randint(300, 450),
            "passing_yards_per_game": random.randint(200, 320),
            "rushing_yards_per_game": random.randint(80, 180),
            "turnover_differential": random.randint(-10, 15),
            "red_zone_efficiency": round(random.uniform(0.45, 0.75), 2),
            "third_down_conversion": round(random.uniform(0.35, 0.55), 2)
        }
    
    async def _get_injury_reports(self, team_name: str) -> Dict[str, Any]:
        """Simulate injury report collection"""
        await asyncio.sleep(0.1)  # Simulate API call delay
        
        import random
        
        injury_impact = random.choice(["minimal", "moderate", "significant"])
        
        return {
            "team": team_name,
            "injury_impact": injury_impact,
            "key_players_out": random.randint(0, 3),
            "questionable_players": random.randint(0, 5),
            "overall_health": random.choice(["excellent", "good", "concerning", "poor"])
        }
    
    async def _get_historical_matchup(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """Simulate historical matchup data"""
        await asyncio.sleep(0.1)  # Simulate API call delay
        
        import random
        
        total_games = random.randint(10, 50)
        home_wins = random.randint(0, total_games)
        
        return {
            "matchup": f"{home_team} vs {away_team}",
            "total_games": total_games,
            "home_team_wins": home_wins,
            "away_team_wins": total_games - home_wins,
            "average_home_score": round(random.uniform(18, 35), 1),
            "average_away_score": round(random.uniform(18, 35), 1),
            "last_meeting": {
                "date": "2023-12-15",  # Placeholder
                "winner": random.choice([home_team, away_team]),
                "score": f"{random.randint(14, 35)}-{random.randint(14, 35)}"
            }
        }
    
    async def get_live_data(self, data_type: str, **params) -> Dict[str, Any]:
        """Get specific live data (for future real API integration)"""
        self.last_activity = datetime.now()
        
        if data_type == "weather":
            return await self._get_weather_data(params.get("game_data"))
        elif data_type == "team_stats":
            return await self._get_team_stats(params.get("team_name"))
        elif data_type == "injuries":
            return await self._get_injury_reports(params.get("team_name"))
        else:
            return {"error": f"Unknown data type: {data_type}"}
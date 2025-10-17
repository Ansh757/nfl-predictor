import os
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

class WeatherImpactAgent:
    """
    Weather Impact Agent with real API support and historical analysis
    """
    
    def __init__(self, name: str):
        self.name = name
        self.status = "active"
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        
        # API Keys
        self.weather_api_key = os.getenv("WEATHER_API_KEY")
        
        # Simplified venue data with key info
        self.nfl_venues = {
            # AFC East
            "Highmark Stadium": {"city": "Orchard Park", "state": "NY", "dome": False, "lat": 42.7738, "lon": -78.7870},
            "Hard Rock Stadium": {"city": "Miami Gardens", "state": "FL", "dome": False, "lat": 25.9580, "lon": -80.2389},
            "Gillette Stadium": {"city": "Foxborough", "state": "MA", "dome": False, "lat": 42.0909, "lon": -71.2643},
            "MetLife Stadium": {"city": "East Rutherford", "state": "NJ", "dome": False, "lat": 40.8128, "lon": -74.0742},
            
            # AFC North
            "M&T Bank Stadium": {"city": "Baltimore", "state": "MD", "dome": False, "lat": 39.2780, "lon": -76.6227},
            "Paycor Stadium": {"city": "Cincinnati", "state": "OH", "dome": False, "lat": 39.0954, "lon": -84.5160},
            "FirstEnergy Stadium": {"city": "Cleveland", "state": "OH", "dome": False, "lat": 41.5061, "lon": -81.6995},
            "Acrisure Stadium": {"city": "Pittsburgh", "state": "PA", "dome": False, "lat": 40.4468, "lon": -80.0158},
            
            # AFC South
            "NRG Stadium": {"city": "Houston", "state": "TX", "dome": True},
            "Lucas Oil Stadium": {"city": "Indianapolis", "state": "IN", "dome": True},
            "TIAA Bank Field": {"city": "Jacksonville", "state": "FL", "dome": False, "lat": 30.3239, "lon": -81.6373},
            "Nissan Stadium": {"city": "Nashville", "state": "TN", "dome": False, "lat": 36.1665, "lon": -86.7713},
            
            # AFC West
            "Empower Field at Mile High": {"city": "Denver", "state": "CO", "dome": False, "lat": 39.7439, "lon": -105.0200},
            "Arrowhead Stadium": {"city": "Kansas City", "state": "MO", "dome": False, "lat": 39.0489, "lon": -94.4839},
            "Allegiant Stadium": {"city": "Las Vegas", "state": "NV", "dome": True},
            "SoFi Stadium": {"city": "Inglewood", "state": "CA", "dome": False, "lat": 33.9535, "lon": -118.3390},
            
            # NFC East
            "AT&T Stadium": {"city": "Arlington", "state": "TX", "dome": True},
            "Lincoln Financial Field": {"city": "Philadelphia", "state": "PA", "dome": False, "lat": 39.9008, "lon": -75.1675},
            "FedExField": {"city": "Landover", "state": "MD", "dome": False, "lat": 38.9076, "lon": -76.8645},
            
            # NFC North
            "Soldier Field": {"city": "Chicago", "state": "IL", "dome": False, "lat": 41.8623, "lon": -87.6167},
            "Ford Field": {"city": "Detroit", "state": "MI", "dome": True},
            "Lambeau Field": {"city": "Green Bay", "state": "WI", "dome": False, "lat": 44.5013, "lon": -88.0622},
            "U.S. Bank Stadium": {"city": "Minneapolis", "state": "MN", "dome": True},
            
            # NFC South
            "Mercedes-Benz Stadium": {"city": "Atlanta", "state": "GA", "dome": True},
            "Bank of America Stadium": {"city": "Charlotte", "state": "NC", "dome": False, "lat": 35.2258, "lon": -80.8530},
            "Mercedes-Benz Superdome": {"city": "New Orleans", "state": "LA", "dome": True},
            "Raymond James Stadium": {"city": "Tampa", "state": "FL", "dome": False, "lat": 27.9759, "lon": -82.5033},
            
            # NFC West
            "State Farm Stadium": {"city": "Glendale", "state": "AZ", "dome": True},
            "Levi's Stadium": {"city": "Santa Clara", "state": "CA", "dome": False, "lat": 37.4031, "lon": -121.9695},
            "Lumen Field": {"city": "Seattle", "state": "WA", "dome": False, "lat": 47.5952, "lon": -122.3316},
        }
        
        # Team weather performance profiles
        self.team_weather_profiles = {
            "Buffalo Bills": {"cold_advantage": 0.15, "snow_advantage": 0.12, "heat_penalty": -0.10},
            "Miami Dolphins": {"heat_advantage": 0.12, "cold_penalty": -0.15, "humidity_advantage": 0.08},
            "Green Bay Packers": {"cold_advantage": 0.18, "wind_advantage": 0.10, "dome_penalty": -0.08},
            "Kansas City Chiefs": {"cold_advantage": 0.12, "wind_advantage": 0.10, "all_weather": 0.08},
            "Chicago Bears": {"wind_advantage": 0.15, "cold_advantage": 0.12, "lake_effect": 0.10},
            "Seattle Seahawks": {"rain_advantage": 0.10, "mild_weather": 0.05},
            "New England Patriots": {"cold_advantage": 0.10, "wind_advantage": 0.08, "all_weather": 0.06},
            "Detroit Lions": {"dome_home": 0.08, "outdoor_penalty": -0.10},
            "New Orleans Saints": {"dome_home": 0.08, "outdoor_penalty": -0.12, "humidity_advantage": 0.06},
            "Dallas Cowboys": {"dome_home": 0.08, "outdoor_penalty": -0.06},
        }
        
        self.logger.info(f"WeatherImpactAgent '{name}' initialized")
    
    async def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "last_activity": self.last_activity,
            "weather_api_available": bool(self.weather_api_key),
            "message": "Weather analysis ready"
        }
    
    async def refresh(self):
        self.last_activity = datetime.now()
        self.logger.info("Weather agent refreshed")
    
    async def predict_game(self, game_data, game_context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze weather impact on game"""
        
        self.last_activity = datetime.now()
        self.status = "analyzing_weather"
        
        try:
            home_team = game_data.home_team_name
            away_team = game_data.away_team_name
            venue = game_context.get("venue", "Unknown")
            
            self.logger.info(f"Weather analysis for {away_team} @ {home_team} at {venue}")
            
            # Get weather conditions
            weather = await self._get_weather(venue)
            
            # If dome, no weather impact
            if weather.get("is_dome"):
                return self._dome_prediction(home_team, away_team, weather)
            
            # Analyze team weather advantages
            home_advantage = self._calculate_team_weather_advantage(home_team, weather)
            away_advantage = self._calculate_team_weather_advantage(away_team, weather)
            
            # Calculate prediction
            prediction = self._calculate_prediction(
                home_team, away_team, home_advantage, away_advantage, weather
            )
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                home_team, away_team, weather, home_advantage, away_advantage, prediction
            )
            
            result = {
                "winner": prediction["winner"],
                "confidence": prediction["confidence"],
                "reasoning": reasoning,
                "weather_conditions": weather,
                "home_weather_advantage": home_advantage,
                "away_weather_advantage": away_advantage
            }
            
            self.logger.info(f"Weather analysis complete: {prediction['winner']} ({prediction['confidence']:.1%})")
            self.status = "active"
            
            return result
            
        except Exception as e:
            self.status = "error"
            self.logger.error(f"Error in weather analysis: {e}")
            raise
    
    async def _get_weather(self, venue: str) -> Dict[str, Any]:
        """Get weather conditions for venue"""
        
        venue_info = self.nfl_venues.get(venue, {})
        
        # Check if dome
        if venue_info.get("dome"):
            return {
                "venue": venue,
                "is_dome": True,
                "temperature": 72,
                "conditions": "controlled",
                "wind_speed": 0,
                "precipitation": 0,
                "source": "dome"
            }
        
        # Try multiple weather APIs in order
        if "lat" in venue_info:
            # 1. Try Open-Meteo (FREE, no key required)
            try:
                weather = await self._fetch_open_meteo(venue_info)
                if weather:
                    self.logger.info(f"Got real weather from Open-Meteo for {venue}")
                    return weather
            except Exception as e:
                self.logger.warning(f"Open-Meteo failed: {e}")
            
            # 2. Try WeatherAPI (requires key)
            if self.weather_api_key:
                try:
                    weather = await self._fetch_weatherapi(venue_info)
                    if weather:
                        self.logger.info(f"Got real weather from WeatherAPI for {venue}")
                        return weather
                except Exception as e:
                    self.logger.warning(f"WeatherAPI failed: {e}")
            
            # 3. Try NOAA (FREE, US only)
            if venue_info.get("state") in ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
                                            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                                            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                                            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                                            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]:
                try:
                    weather = await self._fetch_noaa(venue_info)
                    if weather:
                        self.logger.info(f"Got real weather from NOAA for {venue}")
                        return weather
                except Exception as e:
                    self.logger.warning(f"NOAA failed: {e}")
        
        # All APIs failed - use simulation as last resort
        self.logger.warning(f"All weather APIs failed for {venue}, using simulation")
        return self._simulate_weather(venue, venue_info)
    
    async def _fetch_open_meteo(self, venue_info: Dict) -> Optional[Dict[str, Any]]:
        """Fetch weather from Open-Meteo (FREE, no API key required)"""
        
        try:
            import aiohttp
        except ImportError:
            return None
        
        lat = venue_info["lat"]
        lon = venue_info["lon"]
        
        # Open-Meteo API (completely free, no key needed)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_gusts_10m",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "America/New_York"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        current = data["current"]
                        
                        # Map weather codes to conditions
                        weather_code = current.get("weather_code", 0)
                        conditions = self._map_weather_code(weather_code)
                        
                        return {
                            "venue": venue_info.get("city"),
                            "is_dome": False,
                            "temperature": round(current["temperature_2m"]),
                            "feels_like": round(current["temperature_2m"]),  # Open-Meteo doesn't provide feels_like
                            "conditions": conditions,
                            "wind_speed": round(current["wind_speed_10m"]),
                            "wind_gust": round(current.get("wind_gusts_10m", 0)),
                            "precipitation": round(current.get("precipitation", 0), 2),
                            "humidity": current.get("relative_humidity_2m", 65),
                            "source": "open-meteo (free)"
                        }
        except Exception as e:
            self.logger.error(f"Open-Meteo API error: {e}")
            return None
    
    async def _fetch_weatherapi(self, venue_info: Dict) -> Optional[Dict[str, Any]]:
        """Fetch weather from WeatherAPI.com (requires API key)"""
        
        try:
            import aiohttp
        except ImportError:
            return None
        
        city = f"{venue_info['city']}, {venue_info['state']}"
        url = "http://api.weatherapi.com/v1/current.json"
        params = {
            "key": self.weather_api_key,
            "q": city,
            "aqi": "no"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        current = data["current"]
                        
                        return {
                            "venue": venue_info.get("city"),
                            "is_dome": False,
                            "temperature": round(current["temp_f"]),
                            "feels_like": round(current["feelslike_f"]),
                            "conditions": current["condition"]["text"],
                            "wind_speed": round(current["wind_mph"]),
                            "wind_gust": round(current.get("gust_mph", 0)),
                            "precipitation": current["precip_in"],
                            "humidity": current["humidity"],
                            "source": "weatherapi"
                        }
        except Exception as e:
            self.logger.error(f"WeatherAPI error: {e}")
            return None
    
    async def _fetch_noaa(self, venue_info: Dict) -> Optional[Dict[str, Any]]:
        """Fetch weather from NOAA (FREE, US only, no key required)"""
        
        try:
            import aiohttp
        except ImportError:
            return None
        
        lat = venue_info["lat"]
        lon = venue_info["lon"]
        
        try:
            async with aiohttp.ClientSession() as session:
                # First, get the grid point
                points_url = f"https://api.weather.gov/points/{lat},{lon}"
                headers = {"User-Agent": "NFLPredictor/1.0"}
                
                async with session.get(points_url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        points_data = await response.json()
                        forecast_url = points_data["properties"]["forecast"]
                        
                        # Get the forecast
                        async with session.get(forecast_url, headers=headers, timeout=10) as forecast_response:
                            if forecast_response.status == 200:
                                forecast_data = await forecast_response.json()
                                current_period = forecast_data["properties"]["periods"][0]
                                
                                # Parse conditions
                                temp = current_period["temperature"]
                                wind_str = current_period["windSpeed"]
                                wind_speed = int(wind_str.split()[0]) if wind_str else 0
                                
                                return {
                                    "venue": venue_info.get("city"),
                                    "is_dome": False,
                                    "temperature": temp,
                                    "feels_like": temp,
                                    "conditions": current_period["shortForecast"],
                                    "wind_speed": wind_speed,
                                    "wind_gust": wind_speed + 5,  # Estimate
                                    "precipitation": 0,  # NOAA doesn't provide current precip easily
                                    "humidity": 65,  # Default
                                    "source": "noaa (free)"
                                }
        except Exception as e:
            self.logger.error(f"NOAA API error: {e}")
            return None
    
    def _map_weather_code(self, code: int) -> str:
        """Map Open-Meteo weather codes to conditions"""
        weather_codes = {
            0: "clear sky",
            1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "fog", 48: "depositing rime fog",
            51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
            61: "slight rain", 63: "moderate rain", 65: "heavy rain",
            71: "slight snow", 73: "moderate snow", 75: "heavy snow",
            80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
            95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail"
        }
        return weather_codes.get(code, "unknown")
    
    def _simulate_weather(self, venue: str, venue_info: Dict) -> Dict[str, Any]:
        """Simulate realistic weather for venue"""
        
        month = datetime.now().month
        
        # Regional temperature averages by month
        if venue_info.get("state") in ["NY", "WI", "IL", "MA", "MN"]:  # Northern
            temps = [25, 30, 40, 55, 65, 75, 80, 78, 70, 55, 40, 30]
        elif venue_info.get("state") in ["FL", "TX", "LA"]:  # Southern
            temps = [60, 65, 70, 75, 80, 85, 88, 88, 85, 78, 70, 65]
        else:  # Moderate
            temps = [40, 45, 50, 60, 68, 75, 78, 76, 70, 60, 50, 45]
        
        temp = temps[month - 1] + random.randint(-5, 5)
        
        # Simulate wind
        wind = random.randint(5, 20)
        
        # Simulate precipitation
        precip = 0
        if month in [4, 5, 10, 11]:  # Rainy months
            precip = random.uniform(0, 0.3)
        
        return {
            "venue": venue,
            "is_dome": False,
            "temperature": temp,
            "feels_like": temp,
            "conditions": "partly cloudy" if precip == 0 else "rain",
            "wind_speed": wind,
            "precipitation": round(precip, 2),
            "humidity": 65,
            "source": "simulated"
        }
    
    def _calculate_team_weather_advantage(self, team: str, weather: Dict) -> float:
        """Calculate team's advantage in current weather"""
        
        profile = self.team_weather_profiles.get(team, {})
        advantage = 0.0
        
        temp = weather["temperature"]
        wind = weather["wind_speed"]
        precip = weather["precipitation"]
        
        # Cold weather advantage
        if temp < 32:
            advantage += profile.get("cold_advantage", 0)
        
        # Heat advantage/penalty
        if temp > 85:
            advantage += profile.get("heat_advantage", 0)
            advantage += profile.get("heat_penalty", 0)
        
        # Cold penalty
        if temp < 45:
            advantage += profile.get("cold_penalty", 0)
        
        # Wind advantage
        if wind > 15:
            advantage += profile.get("wind_advantage", 0)
        
        # Precipitation advantage
        if precip > 0.1:
            if "rain" in weather["conditions"].lower():
                advantage += profile.get("rain_advantage", 0)
            if "snow" in weather["conditions"].lower():
                advantage += profile.get("snow_advantage", 0)
        
        return advantage
    
    def _dome_prediction(self, home_team: str, away_team: str, weather: Dict) -> Dict[str, Any]:
        """Handle dome game prediction"""
        
        home_profile = self.team_weather_profiles.get(home_team, {})
        away_profile = self.team_weather_profiles.get(away_team, {})
        
        home_dome_adv = home_profile.get("dome_home", 0)
        away_outdoor_penalty = away_profile.get("outdoor_penalty", 0)
        
        advantage = home_dome_adv - away_outdoor_penalty
        
        if advantage > 0.05:
            winner = home_team
        elif advantage < -0.05:
            winner = away_team
        else:
            # Truly neutral - pick randomly
            winner = home_team if random.random() > 0.5 else away_team
        
        confidence = 0.50 + min(0.15, abs(advantage) * 2)
        
        return {
            "winner": winner,
            "confidence": round(confidence, 3),
            "reasoning": "Dome environment eliminates weather variables. Controlled conditions favor teams accustomed to indoor play.",
            "weather_conditions": weather,
            "home_weather_advantage": home_dome_adv,
            "away_weather_advantage": away_outdoor_penalty
        }
    
    def _calculate_prediction(self, home_team: str, away_team: str,
                            home_advantage: float, away_advantage: float,
                            weather: Dict) -> Dict[str, Any]:
        """Calculate weather-based prediction"""
        
        # Pure weather differential - NO home bias
        differential = home_advantage - away_advantage
        
        # Determine winner based on weather advantage only
        if differential > 0.05:
            winner = home_team
            advantage = differential
        elif differential < -0.05:
            winner = away_team
            advantage = abs(differential)
        else:
            # Truly neutral weather - pick randomly
            winner = home_team if random.random() > 0.5 else away_team
            advantage = 0.02
        
        # Base confidence at 50% (no bias)
        base_confidence = 0.50
        weather_boost = min(0.25, advantage * 2.5)
        confidence = base_confidence + weather_boost
        confidence = max(0.50, min(0.80, confidence))
        
        return {
            "winner": winner,
            "confidence": round(confidence, 3),
            "weather_advantage": round(advantage, 3)
        }
    
    def _generate_reasoning(self, home_team: str, away_team: str, weather: Dict,
                          home_advantage: float, away_advantage: float,
                          prediction: Dict) -> str:
        """Generate weather analysis reasoning"""
        
        reasoning_parts = []
        
        # Data source indicator
        source = weather.get("source", "unknown")
        if "free" in source or source in ["open-meteo", "noaa"]:
            reasoning_parts.append(f"Using real weather data from {source}")
        elif source == "weatherapi":
            reasoning_parts.append("Using real weather data from WeatherAPI")
        elif source == "simulated":
            reasoning_parts.append("Using simulated weather (APIs unavailable)")
        
        # Weather description
        temp = weather["temperature"]
        wind = weather["wind_speed"]
        precip = weather.get("precipitation", 0)
        
        weather_desc = []
        if temp < 32:
            weather_desc.append(f"freezing temps ({temp}°F)")
        elif temp > 85:
            weather_desc.append(f"hot weather ({temp}°F)")
        else:
            weather_desc.append(f"{temp}°F")
        
        if wind > 15:
            weather_desc.append(f"{wind} mph winds")
        
        if precip > 0.1:
            weather_desc.append("precipitation expected")
        
        if weather_desc:
            reasoning_parts.append(f"Conditions: {', '.join(weather_desc)}")
        else:
            reasoning_parts.append(f"Mild conditions ({temp}°F)")
        
        # Team advantages
        if abs(home_advantage) > 0.08:
            adv_type = "excels" if home_advantage > 0 else "struggles"
            reasoning_parts.append(f"{home_team} {adv_type} in these conditions")
        
        if abs(away_advantage) > 0.08:
            adv_type = "excels" if away_advantage > 0 else "struggles"
            reasoning_parts.append(f"{away_team} {adv_type} in these conditions")
        
        # Weather impact
        if temp < 32 or temp > 85:
            reasoning_parts.append("Extreme weather favors experienced teams")
        elif wind > 20:
            reasoning_parts.append("Strong winds impact passing and kicking")
        elif precip > 0.2:
            reasoning_parts.append("Heavy precipitation increases turnover risk")
        
        # Confidence
        confidence = prediction["confidence"]
        if confidence > 0.70:
            reasoning_parts.append("High confidence from clear weather advantage")
        elif confidence > 0.60:
            reasoning_parts.append("Moderate confidence from weather factors")
        else:
            reasoning_parts.append("Low confidence - minimal weather impact")
        
        return ". ".join(reasoning_parts) + "."
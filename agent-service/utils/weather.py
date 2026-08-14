"""
weather.py - Game-day conditions, for display rather than prediction.

This used to be a voting agent. It was retired from the ensemble because it
measured 51.1% over 2021-2024 - barely distinguishable from a coin flip - and
removing it made the ensemble marginally *better*. The underlying reason is
structural rather than a matter of implementation quality: sportsbooks move
lines on wind forecasts, so by kickoff the market has already priced whatever
the weather is worth. An agent re-deriving that adds nothing to an ensemble
that already reads the market.

Conditions are still worth showing. "18 mph winds at Highmark" is useful
context on a game card even when it carries no predictive edge, so this
survives as a provider: it reports the weather and makes no pick.

Two fixes came with the demotion:
  * Coordinates now come from utils/venues.py, the complete 32-team table. The
    old agent carried its own copy covering 22 teams and omitting dome
    coordinates entirely.
  * Results are cached. The old agent was the only one without a cache and hit
    the API on every prediction - its warm call was slower than its cold one.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from utils.venues import TEAM_VENUES, venue_for

CACHE_TTL = timedelta(minutes=30)
REQUEST_TIMEOUT = 10

# Open-Meteo weather codes
WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}

# Monthly averages used only when every source fails
SEASONAL_TEMPS = {
    "cold": [25, 30, 40, 55, 65, 75, 80, 78, 70, 55, 40, 30],
    "warm": [60, 65, 70, 75, 80, 85, 88, 88, 85, 78, 70, 65],
    "mild": [40, 45, 50, 60, 68, 75, 78, 76, 70, 60, 50, 45],
}
COLD_STATES = {"NY", "WI", "IL", "MA", "MN", "MI", "OH", "PA", "CO"}
WARM_STATES = {"FL", "TX", "LA", "AZ", "CA", "NV"}


class WeatherProvider:
    """Reports game-day conditions. Deliberately makes no prediction."""

    def __init__(self, name: str = "Weather", api_key: Optional[str] = None):
        self.name = name
        self.logger = logging.getLogger("utils.weather")
        self.last_activity = datetime.now()
        import os
        self.api_key = api_key or os.getenv("WEATHER_API_KEY")
        self._cache: Dict[str, tuple] = {}

    async def get_status(self) -> Dict[str, Any]:
        return {
            "status": "active",
            "last_activity": self.last_activity,
            "message": (
                f"Conditions for {len(TEAM_VENUES)} venues; "
                f"{len(self._cache)} cached. Display only - does not vote."
            ),
        }

    async def refresh(self):
        self._cache.clear()
        self.last_activity = datetime.now()

    async def get_conditions(self, home_team: str,
                             game_month: Optional[int] = None) -> Dict[str, Any]:
        """Current conditions at the home team's venue."""
        self.last_activity = datetime.now()

        venue = venue_for(home_team)
        if not venue:
            return self._unknown(home_team)

        cached = self._cache.get(home_team)
        if cached and datetime.now() - cached[1] < CACHE_TTL:
            return cached[0]

        if venue.get("dome"):
            conditions = {
                "venue": venue["venue"], "is_dome": True, "temperature": 72,
                "conditions": "controlled", "wind_speed": 0, "precipitation": 0,
                "humidity": 50, "source": "dome",
            }
        else:
            conditions = (
                await self._fetch_open_meteo(venue)
                or await self._fetch_weatherapi(venue)
                or self._simulate(venue, game_month or datetime.now().month)
            )

        conditions["summary"] = self._summarize(conditions)
        self._cache[home_team] = (conditions, datetime.now())
        return conditions

    def _unknown(self, home_team: str) -> Dict[str, Any]:
        return {
            "venue": None, "is_dome": False, "temperature": None,
            "conditions": "unknown", "wind_speed": None, "precipitation": None,
            "source": "unavailable",
            "summary": f"No venue on file for {home_team}",
        }

    async def _fetch_open_meteo(self, venue: Dict) -> Optional[Dict[str, Any]]:
        try:
            import aiohttp
        except ImportError:
            return None

        params = {
            "latitude": venue["lat"], "longitude": venue["lon"],
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,"
                       "wind_speed_10m,wind_gusts_10m",
            "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
            "precipitation_unit": "inch", "timezone": "auto",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.open-meteo.com/v1/forecast",
                                       params=params, timeout=REQUEST_TIMEOUT) as response:
                    if response.status != 200:
                        return None
                    current = (await response.json())["current"]
            return {
                "venue": venue["venue"], "is_dome": False,
                "temperature": round(current["temperature_2m"]),
                "conditions": WEATHER_CODES.get(current.get("weather_code", 0), "unknown"),
                "wind_speed": round(current["wind_speed_10m"]),
                "wind_gust": round(current.get("wind_gusts_10m", 0)),
                "precipitation": round(current.get("precipitation", 0), 2),
                "humidity": current.get("relative_humidity_2m", 65),
                "source": "open-meteo",
            }
        except Exception as exc:
            self.logger.warning(f"Open-Meteo failed for {venue['venue']}: {exc}")
            return None

    async def _fetch_weatherapi(self, venue: Dict) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        try:
            import aiohttp
        except ImportError:
            return None

        params = {"key": self.api_key, "q": f"{venue['lat']},{venue['lon']}", "aqi": "no"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://api.weatherapi.com/v1/current.json",
                                       params=params, timeout=REQUEST_TIMEOUT) as response:
                    if response.status != 200:
                        return None
                    current = (await response.json())["current"]
            return {
                "venue": venue["venue"], "is_dome": False,
                "temperature": round(current["temp_f"]),
                "conditions": current["condition"]["text"],
                "wind_speed": round(current["wind_mph"]),
                "wind_gust": round(current.get("gust_mph", 0)),
                "precipitation": current["precip_in"],
                "humidity": current["humidity"],
                "source": "weatherapi",
            }
        except Exception as exc:
            self.logger.warning(f"WeatherAPI failed for {venue['venue']}: {exc}")
            return None

    def _simulate(self, venue: Dict, month: int) -> Dict[str, Any]:
        """Last resort when every source is unreachable."""
        offset = venue.get("utc_offset", -5)
        if venue["lat"] > 41 or offset == -6 and venue["lat"] > 40:
            band = "cold"
        elif venue["lat"] < 34:
            band = "warm"
        else:
            band = "mild"

        return {
            "venue": venue["venue"], "is_dome": False,
            "temperature": SEASONAL_TEMPS[band][month - 1],
            "conditions": "unavailable (estimated)", "wind_speed": 8,
            "precipitation": 0, "humidity": 65, "source": "estimated",
        }

    def _summarize(self, conditions: Dict[str, Any]) -> str:
        if conditions.get("is_dome"):
            return "Indoors - climate controlled"

        parts = []
        temperature = conditions.get("temperature")
        if temperature is not None:
            parts.append(f"{temperature}°F")
        description = conditions.get("conditions")
        if description and description not in ("unknown",):
            parts.append(description)
        wind = conditions.get("wind_speed")
        if wind:
            parts.append(f"{wind} mph wind")
        precipitation = conditions.get("precipitation") or 0
        if precipitation > 0.05:
            parts.append(f"{precipitation}\" precipitation")
        return ", ".join(parts) if parts else "Conditions unavailable"

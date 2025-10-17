import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from bs4 import BeautifulSoup
import json

class ESPNAPIClient:
    """Client for ESPN's public NFL API"""
    
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
    
    def __init__(self):
        self.logger = logging.getLogger("api.espn")
        self.session = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_team_stats(self, team_abbr: str) -> Dict[str, Any]:
        """Get team statistics from ESPN"""
        session = await self.get_session()
        
        try:
            # Get team info and stats
            url = f"{self.BASE_URL}/teams/{team_abbr}"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_team_stats(data)
                else:
                    self.logger.warning(f"ESPN API returned {response.status} for {team_abbr}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching ESPN stats for {team_abbr}: {e}")
            return None
    
    def _parse_team_stats(self, data: Dict) -> Dict[str, Any]:
        """Parse ESPN team data"""
        try:
            team = data.get("team", {})
            
            # Get record
            record = team.get("record", {}).get("items", [{}])[0]
            stats_list = record.get("stats", [])
            
            # Parse stats
            wins = losses = 0
            for stat in stats_list:
                if stat.get("name") == "wins":
                    wins = int(stat.get("value", 0))
                elif stat.get("name") == "losses":
                    losses = int(stat.get("value", 0))
            
            total_games = wins + losses
            win_rate = wins / total_games if total_games > 0 else 0.5
            
            return {
                "team_name": team.get("displayName", ""),
                "abbreviation": team.get("abbreviation", ""),
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 3),
                "source": "espn"
            }
        except Exception as e:
            self.logger.error(f"Error parsing ESPN data: {e}")
            return None
    
    async def get_scoreboard(self, week: int = None) -> Dict[str, Any]:
        """Get current/upcoming games"""
        session = await self.get_session()
        
        try:
            url = f"{self.BASE_URL}/scoreboard"
            if week:
                url += f"?week={week}"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            self.logger.error(f"Error fetching scoreboard: {e}")
            return None


class ProFootballReferenceClient:
    """Scraper for Pro Football Reference (most comprehensive NFL stats)"""
    
    BASE_URL = "https://www.pro-football-reference.com"
    
    def __init__(self):
        self.logger = logging.getLogger("api.pfr")
        self.session = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_team_stats(self, team_abbr: str, year: int = 2024) -> Dict[str, Any]:
        """Get detailed team stats from Pro Football Reference"""
        session = await self.get_session()
        
        try:
            # Convert team abbreviation to PFR format
            pfr_abbr = self._convert_to_pfr_abbr(team_abbr)
            url = f"{self.BASE_URL}/teams/{pfr_abbr}/{year}.htm"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._parse_team_page(html, team_abbr)
                else:
                    self.logger.warning(f"PFR returned {response.status} for {team_abbr}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching PFR stats for {team_abbr}: {e}")
            return None
    
    def _convert_to_pfr_abbr(self, team_abbr: str) -> str:
        """Convert common abbreviations to PFR format"""
        mapping = {
            "KC": "kan", "BUF": "buf", "MIA": "mia", "NE": "nwe",
            "NYJ": "nyj", "BAL": "rav", "CIN": "cin", "CLE": "cle",
            "PIT": "pit", "HOU": "htx", "IND": "clt", "JAX": "jax",
            "TEN": "oti", "DEN": "den", "LV": "rai", "LAC": "sdg",
            "KC": "kan", "DAL": "dal", "NYG": "nyg", "PHI": "phi",
            "WAS": "was", "CHI": "chi", "DET": "det", "GB": "gnb",
            "MIN": "min", "ATL": "atl", "CAR": "car", "NO": "nor",
            "TB": "tam", "ARI": "crd", "LAR": "ram", "SF": "sfo",
            "SEA": "sea"
        }
        return mapping.get(team_abbr.upper(), team_abbr.lower())
    
    def _parse_team_page(self, html: str, team_abbr: str) -> Dict[str, Any]:
        """Parse team stats from HTML"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Get team record
            record_elem = soup.find('p', string=lambda x: x and 'Record:' in x)
            wins = losses = 0
            if record_elem:
                record_text = record_elem.get_text()
                # Parse "Record: 11-6"
                if '-' in record_text:
                    parts = record_text.split('Record:')[1].strip().split('-')
                    wins = int(parts[0].strip())
                    losses = int(parts[1].strip().split(',')[0])
            
            # Get points scored and allowed
            points_for = points_against = 0
            stats_table = soup.find('table', {'id': 'team_stats'})
            if stats_table:
                rows = stats_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        label = cells[0].get_text().strip()
                        value = cells[1].get_text().strip()
                        if 'Points' in label and 'For' in label:
                            points_for = float(value)
                        elif 'Points' in label and 'Against' in label:
                            points_against = float(value)
            
            total_games = wins + losses
            win_rate = wins / total_games if total_games > 0 else 0.5
            point_diff = points_for - points_against if total_games > 0 else 0
            
            return {
                "team_abbr": team_abbr,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 3),
                "points_per_game": round(points_for / total_games, 1) if total_games > 0 else 20.0,
                "points_allowed_per_game": round(points_against / total_games, 1) if total_games > 0 else 20.0,
                "point_differential": round(point_diff / total_games, 1) if total_games > 0 else 0.0,
                "source": "pro_football_reference"
            }
        except Exception as e:
            self.logger.error(f"Error parsing PFR HTML: {e}")
            return None


class NFLAPIClient:
    """Client for NFL.com's API (requires API key from sportsdata.io or similar)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.sportsdata.io/v3/nfl"
        self.logger = logging.getLogger("api.nfl")
        self.session = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            headers = {}
            if self.api_key:
                headers['Ocp-Apim-Subscription-Key'] = self.api_key
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_team_stats(self, team_abbr: str, season: int = 2024) -> Dict[str, Any]:
        """Get team stats from NFL API (requires API key)"""
        if not self.api_key:
            self.logger.warning("NFL API key not provided, skipping")
            return None
        
        session = await self.get_session()
        
        try:
            url = f"{self.base_url}/scores/json/TeamSeasonStats/{season}"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    # Find team in response
                    for team_data in data:
                        if team_data.get("Team") == team_abbr:
                            return self._parse_nfl_stats(team_data)
                    return None
                else:
                    self.logger.warning(f"NFL API returned {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching NFL API stats: {e}")
            return None
    
    def _parse_nfl_stats(self, data: Dict) -> Dict[str, Any]:
        """Parse NFL API response"""
        try:
            wins = data.get("Wins", 0)
            losses = data.get("Losses", 0)
            total_games = wins + losses
            
            return {
                "team_abbr": data.get("Team", ""),
                "wins": wins,
                "losses": losses,
                "win_rate": round(wins / total_games, 3) if total_games > 0 else 0.5,
                "points_per_game": round(data.get("PointsPerGame", 20.0), 1),
                "points_allowed_per_game": round(data.get("PointsAllowedPerGame", 20.0), 1),
                "point_differential": round(data.get("PointDifferential", 0), 1),
                "source": "nfl_api"
            }
        except Exception as e:
            self.logger.error(f"Error parsing NFL API data: {e}")
            return None


class WeatherAPIClient:
    """Client for weather data (OpenWeatherMap)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key  # Get free key from openweathermap.org
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.logger = logging.getLogger("api.weather")
        self.session = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_weather_for_game(self, city: str, game_time: datetime) -> Dict[str, Any]:
        """Get weather forecast for game location and time"""
        if not self.api_key:
            self.logger.warning("Weather API key not provided")
            return self._get_default_weather()
        
        session = await self.get_session()
        
        try:
            # Get current weather (for now - upgrade to forecast API for future games)
            url = f"{self.base_url}/weather"
            params = {
                'q': city,
                'appid': self.api_key,
                'units': 'imperial'  # Fahrenheit
            }
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_weather(data)
                else:
                    self.logger.warning(f"Weather API returned {response.status}")
                    return self._get_default_weather()
        except Exception as e:
            self.logger.error(f"Error fetching weather: {e}")
            return self._get_default_weather()
    
    def _parse_weather(self, data: Dict) -> Dict[str, Any]:
        """Parse OpenWeatherMap response"""
        try:
            main = data.get("main", {})
            weather = data.get("weather", [{}])[0]
            wind = data.get("wind", {})
            
            return {
                "temperature": round(main.get("temp", 65), 1),
                "conditions": weather.get("description", "clear"),
                "wind_speed": round(wind.get("speed", 0), 1),
                "humidity": main.get("humidity", 50),
                "source": "openweathermap"
            }
        except Exception as e:
            self.logger.error(f"Error parsing weather data: {e}")
            return self._get_default_weather()
    
    def _get_default_weather(self) -> Dict[str, Any]:
        """Return default weather when API unavailable"""
        return {
            "temperature": 65,
            "conditions": "clear",
            "wind_speed": 5,
            "humidity": 50,
            "source": "default"
        }


class APIManager:
    """Manages all API clients and handles fallbacks"""
    
    def __init__(self, nfl_api_key: Optional[str] = None, weather_api_key: Optional[str] = None):
        self.espn = ESPNAPIClient()
        self.pfr = ProFootballReferenceClient()
        self.nfl = NFLAPIClient(nfl_api_key)
        self.weather = WeatherAPIClient(weather_api_key)
        self.logger = logging.getLogger("api.manager")
    
    async def get_team_stats(self, team_abbr: str) -> Dict[str, Any]:
        """Get team stats with fallback across multiple sources"""
        
        # Try ESPN first (free, reliable)
        stats = await self.espn.get_team_stats(team_abbr)
        if stats:
            self.logger.info(f"Got stats for {team_abbr} from ESPN")
            return stats
        
        # Try Pro Football Reference (free, comprehensive)
        stats = await self.pfr.get_team_stats(team_abbr)
        if stats:
            self.logger.info(f"Got stats for {team_abbr} from PFR")
            return stats
        
        # Try NFL API (requires key)
        stats = await self.nfl.get_team_stats(team_abbr)
        if stats:
            self.logger.info(f"Got stats for {team_abbr} from NFL API")
            return stats
        
        # All APIs failed
        self.logger.warning(f"All APIs failed for {team_abbr}, returning None")
        return None
    
    async def get_weather(self, city: str, game_time: datetime) -> Dict[str, Any]:
        """Get weather data"""
        return await self.weather.get_weather_for_game(city, game_time)
    
    async def close_all(self):
        """Close all API sessions"""
        await self.espn.close()
        await self.pfr.close()
        await self.nfl.close()
        await self.weather.close()


# Team abbreviation mapping
TEAM_ABBREVIATIONS = {
    "Kansas City Chiefs": "KC",
    "Buffalo Bills": "BUF",
    "Miami Dolphins": "MIA",
    "New England Patriots": "NE",
    "New York Jets": "NYJ",
    "Baltimore Ravens": "BAL",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Pittsburgh Steelers": "PIT",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Tennessee Titans": "TEN",
    "Denver Broncos": "DEN",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Dallas Cowboys": "DAL",
    "New York Giants": "NYG",
    "Philadelphia Eagles": "PHI",
    "Washington Commanders": "WAS",
    "Chicago Bears": "CHI",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Minnesota Vikings": "MIN",
    "Atlanta Falcons": "ATL",
    "Carolina Panthers": "CAR",
    "New Orleans Saints": "NO",
    "Tampa Bay Buccaneers": "TB",
    "Arizona Cardinals": "ARI",
    "Los Angeles Rams": "LAR",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA"
}

def get_team_abbreviation(team_name: str) -> str:
    """Convert full team name to abbreviation"""
    return TEAM_ABBREVIATIONS.get(team_name, team_name[:3].upper())
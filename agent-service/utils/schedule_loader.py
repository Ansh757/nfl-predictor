"""
schedule_loader.py - Load full NFL schedule into database
"""
import sqlite3
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional

class NFLScheduleLoader:
    def __init__(self, db_path: str = "nfl_schedule.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize schedule database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY,
                season INTEGER,
                week INTEGER,
                game_date TEXT,
                game_time TEXT,
                home_team TEXT,
                away_team TEXT,
                venue TEXT,
                is_dome BOOLEAN,
                home_score INTEGER,
                away_score INTEGER,
                game_status TEXT,
                espn_game_id TEXT,
                season_type TEXT DEFAULT 'regular',
                round TEXT,
                home_seed INTEGER,
                away_seed INTEGER,
                bracket TEXT,
                bracket_position TEXT,
                advance_probability REAL
            )
        ''')

        cursor.execute("PRAGMA table_info(games)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        required_columns = {
            "season_type": "TEXT DEFAULT 'regular'",
            "round": "TEXT",
            "home_seed": "INTEGER",
            "away_seed": "INTEGER",
            "bracket": "TEXT",
            "bracket_position": "TEXT",
            "advance_probability": "REAL"
        }
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                cursor.execute(f"ALTER TABLE games ADD COLUMN {column_name} {column_type}")

        conn.commit()
        conn.close()
    
    async def load_espn_schedule(self, season: int = 2025):
        """Load schedule from ESPN API"""
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        
        all_games = []
        
        # ESPN API gives you games by week
        for week in range(1, 19):  # Regular season weeks 1-18
            params = {
                "dates": season,
                "seasontype": 2,  # Regular season
                "week": week
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        games = self._parse_espn_games(data, season, week)
                        all_games.extend(games)
                        print(f"Loaded week {week}: {len(games)} games")
            
            await asyncio.sleep(1)  # Be nice to ESPN's servers
        
        # Store in database
        self._store_games(all_games)
        print(f"Total games loaded: {len(all_games)}")
        
        return all_games
    
    def _parse_espn_games(
        self,
        data: Dict,
        season: int,
        week: int,
        season_type: str = "regular",
        round_name: Optional[str] = None,
        bracket: Optional[str] = None
    ) -> List[Dict]:
        """Parse ESPN API response into game data"""
        games = []

        for event in data.get("events", []):
            competition = event["competitions"][0]
            competitors = competition.get("competitors", [])
            home_competitor = next((team for team in competitors if team.get("homeAway") == "home"), {})
            away_competitor = next((team for team in competitors if team.get("homeAway") == "away"), {})

            game = {
                "season": season,
                "week": week,
                "season_type": season_type,
                "round": round_name,
                "home_seed": home_competitor.get("seed"),
                "away_seed": away_competitor.get("seed"),
                "bracket": bracket,
                "bracket_position": event.get("shortName") or event.get("name"),
                "game_date": event["date"],
                "home_team": home_competitor.get("team", {}).get("displayName"),
                "away_team": away_competitor.get("team", {}).get("displayName"),
                "venue": competition.get("venue", {}).get("fullName"),
                "is_dome": competition.get("venue", {}).get("indoor", False),
                "espn_game_id": event["id"],
                "game_status": event["status"]["type"]["name"]
            }

            games.append(game)

        return games
    
    def _store_games(self, games: List[Dict]):
        """Store games in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for game in games:
            cursor.execute('''
                INSERT OR REPLACE INTO games 
                (season, week, game_date, home_team, away_team, venue, is_dome, espn_game_id, game_status,
                 season_type, round, home_seed, away_seed, bracket, bracket_position, advance_probability)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                game["season"],
                game["week"],
                game["game_date"],
                game["home_team"],
                game["away_team"],
                game["venue"],
                game["is_dome"],
                game["espn_game_id"],
                game["game_status"],
                game.get("season_type", "regular"),
                game.get("round"),
                game.get("home_seed"),
                game.get("away_seed"),
                game.get("bracket"),
                game.get("bracket_position"),
                game.get("advance_probability")
            ))

        conn.commit()
        conn.close()
    
    def get_upcoming_games(self, limit: int = 10) -> List[Dict]:
        """Get upcoming games from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT game_id, season, week, game_date, home_team, away_team, venue, is_dome
            FROM games
            WHERE game_date >= datetime('now')
            AND game_status != 'STATUS_FINAL'
            ORDER BY game_date
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        games = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return games

    async def load_espn_playoffs(self, season: int = 2025):
        """Load postseason schedule from ESPN API"""
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        round_map = {
            1: "Wild Card",
            2: "Divisional",
            3: "Conference",
            4: "Championship"
        }

        all_games = []

        for week, round_name in round_map.items():
            params = {
                "dates": season,
                "seasontype": 3,
                "week": week
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        games = self._parse_espn_games(
                            data,
                            season,
                            week,
                            season_type="playoffs",
                            round_name=round_name,
                            bracket=None
                        )
                        all_games.extend(games)
                        print(f"Loaded postseason {round_name}: {len(games)} games")

            await asyncio.sleep(1)

        self._store_games(all_games)
        print(f"Total postseason games loaded: {len(all_games)}")
        return all_games

    def get_playoff_games_by_season(self, season: int) -> List[Dict]:
        """Get playoff games for a season"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT game_id, season, week, round, home_team, away_team, home_seed, away_seed,
                   bracket, bracket_position, game_date, venue, is_dome, advance_probability
            FROM games
            WHERE season = ?
            AND season_type = 'playoffs'
            ORDER BY game_date
        ''', (season,))

        columns = [desc[0] for desc in cursor.description]
        games = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return games

    def get_playoff_games_by_round(self, season: int, round_name: str) -> List[Dict]:
        """Get playoff games for a season and round"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT game_id, season, week, round, home_team, away_team, home_seed, away_seed,
                   bracket, bracket_position, game_date, venue, is_dome, advance_probability
            FROM games
            WHERE season = ?
            AND season_type = 'playoffs'
            AND round = ?
            ORDER BY game_date
        ''', (season, round_name))

        columns = [desc[0] for desc in cursor.description]
        games = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return games

# Usage
async def load_full_schedule():
    loader = NFLScheduleLoader()
    await loader.load_espn_schedule(season=2025)
    
    # Get upcoming games
    upcoming = loader.get_upcoming_games(limit=10)
    for game in upcoming:
        print(f"{game['away_team']} @ {game['home_team']} - {game['game_date']}")

if __name__ == "__main__":
    asyncio.run(load_full_schedule())

"""
Add Super Bowl Games - Add actual Super Bowl results to database
Note: This adds Super Bowl games as a NEW round, separate from Conference Championships
"""
import sqlite3
import sys

def add_superbowl_games(db_path):
    """Add Super Bowl games to the database"""
    
    # Super Bowl data for seasons 2021-2025
    superbowl_games = [
        # 2021 Season - Super Bowl LVI
        {
            "season": 2021,
            "home_team": "Los Angeles Rams",
            "away_team": "Cincinnati Bengals",
            "home_score": 23,
            "away_score": 20,
            "venue": "SoFi Stadium",
            "game_date": "2022-02-13T23:30:00Z"
        },
        # 2022 Season - Super Bowl LVII
        {
            "season": 2022,
            "home_team": "Kansas City Chiefs",
            "away_team": "Philadelphia Eagles",
            "home_score": 38,
            "away_score": 35,
            "venue": "State Farm Stadium",
            "game_date": "2023-02-13T00:30:00Z"
        },
        # 2023 Season - Super Bowl LVIII
        {
            "season": 2023,
            "home_team": "Kansas City Chiefs",
            "away_team": "San Francisco 49ers",
            "home_score": 25,
            "away_score": 22,
            "venue": "Allegiant Stadium",
            "game_date": "2024-02-12T00:30:00Z"
        },
        # 2024 Season - Super Bowl LIX
        {
            "season": 2024,
            "home_team": "Philadelphia Eagles",
            "away_team": "Kansas City Chiefs",
            "home_score": 40,
            "away_score": 22,
            "venue": "Caesars Superdome",
            "game_date": "2025-02-10T00:30:00Z"
        },
        # 2025 Season - Super Bowl LX (FICTIONAL - as requested)
        {
            "season": 2025,
            "home_team": "Seattle Seahawks",
            "away_team": "New England Patriots",
            "home_score": 31,
            "away_score": 28,
            "venue": "Levi's Stadium",
            "game_date": "2026-02-08T23:30:00Z"
        }
    ]
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # First, delete any existing Super Bowl games
    cursor.execute("DELETE FROM games WHERE round = 'Super Bowl'")
    print(f"Deleted old Super Bowl games (if any)")
    
    # Insert Super Bowl data
    for game in superbowl_games:
        cursor.execute('''
            INSERT INTO games 
            (season, week, game_date, home_team, away_team, venue, 
             home_score, away_score, game_status, season_type, round)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            game["season"],
            5,  # Week 5 of playoffs (Super Bowl is after Championship week)
            game["game_date"],
            game["home_team"],
            game["away_team"],
            game["venue"],
            game["home_score"],
            game["away_score"],
            "STATUS_FINAL",
            "playoffs",
            "Super Bowl"
        ))
        winner = game["home_team"] if game["home_score"] > game["away_score"] else game["away_team"]
        winner_score = max(game["home_score"], game["away_score"])
        loser_score = min(game["home_score"], game["away_score"])
        print(f"Added: Super Bowl {game['season']} - {winner} {winner_score}, {game['away_team'] if winner == game['home_team'] else game['home_team']} {loser_score}")
    
    conn.commit()
    
    # Verify
    print("\n" + "="*80)
    print("VERIFICATION - Super Bowl Games in Database:")
    print("="*80)
    cursor.execute('''
        SELECT season, home_team, home_score, away_team, away_score, venue
        FROM games 
        WHERE round = 'Super Bowl'
        ORDER BY season
    ''')
    
    for row in cursor.fetchall():
        season, home, home_score, away, away_score, venue = row
        winner = home if home_score > away_score else away
        loser = away if home_score > away_score else home
        winner_score = max(home_score, away_score)
        loser_score = min(home_score, away_score)
        print(f"\n🏆 Season {season} Super Bowl:")
        print(f"   {winner} {winner_score} defeats {loser} {loser_score}")
        print(f"   Venue: {venue}")
    
    # Also show championship games for comparison
    print("\n" + "="*80)
    print("CONFERENCE CHAMPIONSHIP GAMES (for reference):")
    print("="*80)
    cursor.execute('''
        SELECT season, COUNT(*) as game_count
        FROM games 
        WHERE round = 'Championship'
        GROUP BY season
        ORDER BY season
    ''')
    
    for row in cursor.fetchall():
        season, count = row
        print(f"Season {season}: {count} Conference Championship games")
    
    conn.close()
    print("\n✅ Super Bowl games added!")
    print("\nNote: 2025 Super Bowl (Seahawks vs Patriots) is FICTIONAL as requested.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python add_superbowl_games.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    add_superbowl_games(db_path)
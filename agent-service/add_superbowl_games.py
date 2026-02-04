"""
Fix Championship Games - Replace AFC vs NFC placeholder data with actual Super Bowl results
This replaces the existing "Championship" round games with Super Bowl data
"""
import sqlite3
import sys

def fix_championship_games_with_superbowls(db_path):
    """Replace incorrect championship game data with actual Super Bowl results"""
    
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
    
    # First, delete incorrect championship games (AFC vs NFC placeholders)
    cursor.execute("DELETE FROM games WHERE round = 'Championship'")
    deleted_count = cursor.rowcount
    print(f"Deleted {deleted_count} old Championship games (AFC vs NFC placeholders)")
    
    # Insert Super Bowl data as Championship round
    print("\nAdding Super Bowl games as Championship round:")
    print("="*80)
    for game in superbowl_games:
        cursor.execute('''
            INSERT INTO games 
            (season, week, game_date, home_team, away_team, venue, 
             home_score, away_score, game_status, season_type, round)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            game["season"],
            4,  # Keep as week 4 to match your existing schema
            game["game_date"],
            game["home_team"],
            game["away_team"],
            game["venue"],
            game["home_score"],
            game["away_score"],
            "STATUS_FINAL",
            "playoffs",
            "Championship"
        ))
        winner = game["home_team"] if game["home_score"] > game["away_score"] else game["away_team"]
        loser = game["away_team"] if game["home_score"] > game["away_score"] else game["home_team"]
        winner_score = max(game["home_score"], game["away_score"])
        loser_score = min(game["home_score"], game["away_score"])
        print(f"Season {game['season']}: {winner} {winner_score} defeats {loser} {loser_score}")
    
    conn.commit()
    
    # Verify
    print("\n" + "="*80)
    print("VERIFICATION - Championship Games (Super Bowls) in Database:")
    print("="*80)
    cursor.execute('''
        SELECT season, home_team, home_score, away_team, away_score, venue, game_date
        FROM games 
        WHERE round = 'Championship'
        ORDER BY season
    ''')
    
    for row in cursor.fetchall():
        season, home, home_score, away, away_score, venue, date = row
        winner = home if home_score > away_score else away
        loser = away if home_score > away_score else home
        winner_score = max(home_score, away_score)
        loser_score = min(home_score, away_score)
        print(f"\n🏆 Season {season} Championship (Super Bowl):")
        print(f"   {away} {away_score} vs {home} {home_score}")
        print(f"   Winner: {winner} ({winner_score}-{loser_score})")
        print(f"   Venue: {venue}")
        print(f"   Date: {date}")
    
    conn.close()
    print("\n" + "="*80)
    print("✅ Championship games replaced with Super Bowl data!")
    print("\nNote: 2025 Super Bowl (Seahawks 31, Patriots 28) is FICTIONAL as requested.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python fix_championship_with_superbowls.py <db_path>")
        print("Example: python fix_championship_with_superbowls.py agent-service/nfl_schedule.db")
        sys.exit(1)
    
    db_path = sys.argv[1]
    fix_championship_games_with_superbowls(db_path)
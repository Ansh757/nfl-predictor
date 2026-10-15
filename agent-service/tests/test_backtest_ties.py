"""A tie has no winner, so the backtest must not score one.

predict_one derives the winner as `home if home > away else away`, which turns a
27-27 tie into an away win. Before load_games excluded ties, the 2026 week 5
Giants @ Commanders tie was scored as a correct pick for the Giants.
"""
import sqlite3

from backtest import load_games


def _db(tmp_path):
    path = tmp_path / "games.db"
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE games (
            game_id INTEGER PRIMARY KEY, season INTEGER, week INTEGER,
            game_date TEXT, home_team TEXT, away_team TEXT, venue TEXT,
            is_dome BOOLEAN, home_score INTEGER, away_score INTEGER,
            season_type TEXT, neutral_site INTEGER, venue_country TEXT)
    """)
    rows = [
        (1, 2026, 5, "2026-10-11T17:00Z", "Washington Commanders", "New York Giants", 27, 27),
        (2, 2026, 5, "2026-10-11T17:00Z", "Pittsburgh Steelers", "Indianapolis Colts", 34, 22),
        (3, 2026, 6, "2026-10-18T17:00Z", "Seattle Seahawks", "Arizona Cardinals", None, None),
    ]
    conn.executemany(
        "INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, 'x', 0, ?, ?, 'regular', 0, 'USA')",
        [r[:6] + r[6:] for r in rows])
    conn.commit()
    conn.close()
    return str(path)


def test_tied_game_is_not_loaded(tmp_path):
    games = load_games(_db(tmp_path), 2026)
    assert [g["game_id"] for g in games] == [2]


def test_decided_game_is_still_loaded(tmp_path):
    (game,) = load_games(_db(tmp_path), 2026)
    assert (game["home_score"], game["away_score"]) == (34, 22)

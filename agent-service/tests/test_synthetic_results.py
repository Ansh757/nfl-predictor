"""
Invented results must not train anything.

add_superbowl_games.py inserts a 2025 Super Bowl marked "FICTIONAL - as
requested". A comment cannot stop a query, and two queries were reading it:
utils/elo.py and utils/team_stats.py, which back two of the three weighted
agents. The invention was Seattle beating New England - and those two opened the
2026 season against each other, so both sides of week 1's first game carried a
rating and a form record earned in a game that was never played.
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.elo import EloRatingSystem  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nfl_schedule.db")


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB)
    yield conn
    conn.close()


def _games(conn, exclude_synthetic):
    query = """
        SELECT game_id, season, game_date, home_team, away_team, home_score, away_score
        FROM games WHERE home_team IS NOT NULL AND away_team IS NOT NULL
    """
    if exclude_synthetic:
        query += " AND COALESCE(is_synthetic, 0) = 0"
    query += " ORDER BY game_date"
    cursor = conn.execute(query)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


class TestTheFlag:
    def test_the_column_exists(self, db):
        columns = {row[1] for row in db.execute("PRAGMA table_info(games)")}
        assert "is_synthetic" in columns

    def test_the_invented_super_bowl_is_flagged(self, db):
        flagged = db.execute(
            "SELECT season, home_team, away_team FROM games WHERE is_synthetic = 1"
        ).fetchall()
        assert (2025, "Seattle Seahawks", "New England Patriots") in flagged

    def test_nothing_else_is_flagged(self, db):
        # Every other result was observed. If this count grows, something real
        # has been marked invented - which would quietly shrink the training set.
        assert db.execute("SELECT COUNT(*) FROM games WHERE is_synthetic = 1").fetchone()[0] == 1


class TestExclusion:
    def test_elos_query_excludes_synthetic_rows(self, db):
        # The guard lives in the SQL, so assert on the SQL as well as the effect
        import utils.elo as elo_module
        source = open(elo_module.__file__).read()
        assert "is_synthetic" in source, "utils/elo.py must filter invented results"

    def test_team_stats_query_excludes_synthetic_rows(self):
        import utils.team_stats as stats_module
        source = open(stats_module.__file__).read()
        assert "is_synthetic" in source, "utils/team_stats.py must filter invented results"

    def test_the_ratings_actually_move(self, db):
        polluted = EloRatingSystem()
        polluted.build(_games(db, exclude_synthetic=False))
        clean = EloRatingSystem()
        clean.build(_games(db, exclude_synthetic=True))

        # The fabricated game had Seattle winning, so excluding it must cost
        # Seattle rating and give it back to New England.
        assert clean.ratings["Seattle Seahawks"] < polluted.ratings["Seattle Seahawks"]
        assert clean.ratings["New England Patriots"] > polluted.ratings["New England Patriots"]

    def test_only_the_two_teams_involved_are_affected(self, db):
        polluted = EloRatingSystem()
        polluted.build(_games(db, exclude_synthetic=False))
        clean = EloRatingSystem()
        clean.build(_games(db, exclude_synthetic=True))

        moved = {team for team in polluted.ratings
                 if abs(clean.ratings[team] - polluted.ratings[team]) > 0.05}
        assert moved == {"Seattle Seahawks", "New England Patriots"}

    def test_the_real_game_count_is_unchanged_otherwise(self, db):
        with_fake = len(_games(db, exclude_synthetic=False))
        without = len(_games(db, exclude_synthetic=True))
        assert with_fake - without == 1

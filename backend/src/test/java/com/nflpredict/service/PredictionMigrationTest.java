package com.nflpredict.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationVersion;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * V2 is the migration that touches production data, so it is tested against a
 * database seeded to look like production did: 33 rows for 16 games, from one
 * stray early row plus two runs of the weekly endpoint.
 *
 * <p>The sequence matters. Migrating to V1 first reproduces the schema as
 * ddl-auto left it - created_at, no season/week/kickoff_at, no unique index -
 * and only then is the duplicate data inserted. Running V2 over that is exactly
 * what will happen on deploy.
 */
class PredictionMigrationTest {

    private static final String KICKOFF = "2026-09-13 17:00:00";
    /** A game id belonging to neither weekly run - the stray production row. */
    private static final long STRAY_GAME_ID = 99L;

    private String url(String name) {
        return "jdbc:h2:mem:" + name + ";MODE=PostgreSQL;DB_CLOSE_DELAY=-1";
    }

    private void migrateTo(String url, String version) {
        Flyway.configure()
                .dataSource(url, "sa", "")
                .target(MigrationVersion.fromVersion(version))
                .baselineOnMigrate(false)
                .load()
                .migrate();
    }

    /**
     * The exact shape production is in: 33 rows over 17 distinct game ids.
     *
     * <p>Sixteen week-1 games written twice by two runs of the weekly endpoint,
     * plus one stray row for a game id that belongs to neither run - an earlier
     * manual test. The stray matters: it is the only row in its group, so the
     * dedupe keeps it and the table lands on 17, not 16.
     */
    private void seedProductionShape(Connection db) throws SQLException {
        String insert = "INSERT INTO predictions "
                + "(game_id, home_team, away_team, predicted_winner, confidence, "
                + " consensus_method, agent_detail, created_at, settled) "
                + "VALUES (?, ?, ?, ?, ?, 'weighted', '[]', ?, FALSE)";

        try (PreparedStatement statement = db.prepareStatement(insert)) {
            // The stray row, on its own game id, written before either real run
            statement.setLong(1, STRAY_GAME_ID);
            statement.setString(2, "Home 99");
            statement.setString(3, "Away 99");
            statement.setString(4, "Home 99");
            statement.setDouble(5, 0.55);
            statement.setString(6, "2026-09-01 12:00:00");
            statement.addBatch();

            // Two passes over the same sixteen games, an hour apart. The second
            // pass disagrees with the first, which is the whole problem: it used
            // to be the row settlement scored.
            for (int pass = 0; pass < 2; pass++) {
                for (long gameId = 1; gameId <= 16; gameId++) {
                    statement.setLong(1, gameId);
                    statement.setString(2, "Home " + gameId);
                    statement.setString(3, "Away " + gameId);
                    statement.setString(4, pass == 0 ? "Home " + gameId : "Away " + gameId);
                    statement.setDouble(5, pass == 0 ? 0.61 : 0.72);
                    statement.setString(6, pass == 0 ? "2026-09-10 09:00:00" : "2026-09-10 10:00:00");
                    statement.addBatch();
                }
            }
            statement.executeBatch();
        }
    }

    private long scalar(Connection db, String sql) throws SQLException {
        try (Statement statement = db.createStatement(); ResultSet rows = statement.executeQuery(sql)) {
            rows.next();
            return rows.getLong(1);
        }
    }

    @Test
    @DisplayName("V2 collapses duplicates to one row per game and keeps the original")
    void migrationDeduplicates() throws Exception {
        String url = url("migration_dedupe");
        migrateTo(url, "1");

        try (Connection db = DriverManager.getConnection(url, "sa", "")) {
            seedProductionShape(db);
            // 1 stray + 16 + 16 - the numbers actually reported in production
            assertEquals(33, scalar(db, "SELECT COUNT(*) FROM predictions"));
            assertEquals(17, scalar(db, "SELECT COUNT(DISTINCT game_id) FROM predictions"));

            migrateTo(url, "2");

            // 17, not 16. The stray row is the only member of its group, so the
            // dedupe keeps it - it is a duplicate of nothing.
            assertEquals(17, scalar(db, "SELECT COUNT(*) FROM predictions"),
                    "one row per game id, including the stray");
            assertEquals(17, scalar(db, "SELECT COUNT(DISTINCT game_id) FROM predictions"));
            assertEquals(1, scalar(db,
                    "SELECT COUNT(*) FROM predictions WHERE game_id = " + STRAY_GAME_ID),
                    "the stray survives and would need removing separately");

            // Each duplicated game keeps its first pass: the earliest row wins
            List<String> survivor = new ArrayList<>();
            try (Statement statement = db.createStatement();
                 ResultSet rows = statement.executeQuery(
                         "SELECT predicted_winner, confidence, predicted_at "
                                 + "FROM predictions WHERE game_id = 1")) {
                while (rows.next()) {
                    survivor.add(rows.getString(1) + "|" + rows.getDouble(2) + "|" + rows.getString(3));
                }
            }
            assertEquals(1, survivor.size());
            assertTrue(survivor.get(0).startsWith("Home 1|0.61|2026-09-10 09:00"),
                    "the earlier of the two passes must survive: " + survivor.get(0));

            // No row from the second pass survives anywhere
            assertEquals(16, scalar(db,
                    "SELECT COUNT(*) FROM predictions WHERE confidence = 0.61"));
            assertEquals(0, scalar(db,
                    "SELECT COUNT(*) FROM predictions WHERE confidence = 0.72"),
                    "the later re-run must not have replaced any original");
        }
    }

    @Test
    @DisplayName("V2 renames created_at and adds the columns an official prediction needs")
    void migrationAddsOfficialColumns() throws Exception {
        String url = url("migration_columns");
        migrateTo(url, "2");

        try (Connection db = DriverManager.getConnection(url, "sa", "")) {
            String columns = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                    + "WHERE TABLE_NAME = 'PREDICTIONS' AND COLUMN_NAME = '";
            assertEquals(1, scalar(db, columns + "PREDICTED_AT'"));
            assertEquals(1, scalar(db, columns + "KICKOFF_AT'"));
            assertEquals(1, scalar(db, columns + "SEASON'"));
            assertEquals(1, scalar(db, columns + "WEEK'"));
            assertEquals(0, scalar(db, columns + "CREATED_AT'"), "created_at was renamed, not kept");
        }
    }

    @Test
    @DisplayName("after V2 the database itself rejects a second row for a game")
    void migrationAddsTheConstraint() throws Exception {
        String url = url("migration_constraint");
        migrateTo(url, "2");

        String insert = "INSERT INTO predictions "
                + "(game_id, home_team, away_team, predicted_winner, confidence, "
                + " consensus_method, agent_detail, predicted_at, kickoff_at, season, week, settled) "
                + "VALUES (1, 'Home 1', 'Away 1', 'Home 1', 0.6, 'weighted', '[]', "
                + " '2026-09-10 09:00:00', '" + KICKOFF + "', 2026, 1, FALSE)";

        try (Connection db = DriverManager.getConnection(url, "sa", "")) {
            try (Statement statement = db.createStatement()) {
                statement.executeUpdate(insert);
            }
            assertEquals(1, scalar(db, "SELECT COUNT(*) FROM predictions"));

            // The same insert a second time - what a re-run of the weekly
            // endpoint was doing - must now fail at the database.
            assertThrows(SQLException.class, () -> {
                try (Statement statement = db.createStatement()) {
                    statement.executeUpdate(insert);
                }
            });
            assertEquals(1, scalar(db, "SELECT COUNT(*) FROM predictions"));
        }
    }
}

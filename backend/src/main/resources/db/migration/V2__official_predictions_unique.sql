-- One official prediction per game.
--
-- The weekly endpoint was not idempotent: every re-run inserted a second row
-- per game, so week 1 of 2026 held 33 rows for 16 games. Settlement then took
-- the *newest* row per game, meaning a re-run could replace the original
-- pre-kickoff pick with a later one made on better information - and every
-- duplicate was scored separately, counting one game repeatedly in the
-- accuracy denominator.
--
-- Order matters here: add the columns, name the timestamp for what it means,
-- collapse the duplicates, and only then add the constraint. Creating the index
-- first would fail against the existing duplicate rows.

-- 1. Columns needed to certify a prediction as official.
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS season     INTEGER;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS week       INTEGER;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS kickoff_at TIMESTAMP;

-- 2. created_at recorded when a row was inserted; what matters is when the
--    prediction was made, and that it preceded kickoff.
ALTER TABLE predictions RENAME COLUMN created_at TO predicted_at;

-- 3. Collapse duplicates, keeping the earliest row per game.
--
--    The id column is an identity sequence, so the lowest id for a game is the
--    first row written for it - the original prediction. Legacy rows have no
--    kickoff_at to check against, so "first recorded" is the best available
--    proxy for "made before kickoff"; from here the application guard makes a
--    post-kickoff row impossible in the first place.
--
--    DESTRUCTIVE. Run the inspection queries in the PR description first.
DELETE FROM predictions
WHERE id NOT IN (
    SELECT MIN(id) FROM predictions GROUP BY game_id
);

-- 4. The actual guarantee. An application-side existence check cannot provide
--    this: predictWeek fans out across a thread pool, so two callers can both
--    see "no row yet" before either inserts.
CREATE UNIQUE INDEX IF NOT EXISTS uq_predictions_game ON predictions (game_id);

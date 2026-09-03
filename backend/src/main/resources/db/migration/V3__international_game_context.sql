-- Venue context, stored with the prediction that used it.
--
-- Live accuracy is only auditable if the reasoning is reproducible, and from
-- here the reasoning depends on facts about the venue: whether home-field
-- advantage was applied at all, and whether an international travel adjustment
-- was in play. Those are properties of the game, not of the model, and a
-- rating rebuild months later will not recover what was believed at the time.
--
-- The two flags are deliberately separate columns and must stay that way:
--
--   neutral_site       - the designated home team was not at its own ground.
--                        Governs home-field advantage. A Super Bowl is neutral
--                        and domestic. Super Bowl LVI was at SoFi with the Rams
--                        designated home, so it was NOT neutral.
--   international_game - the venue is outside the United States. Governs the
--                        travel adjustment and the wording. Implies neutral in
--                        practice, but is never inferred from it, nor it from
--                        the country.
--
-- All nullable: rows written before this existed have no answer, and inventing
-- one - defaulting to false - would assert something about them that was never
-- computed.
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS neutral_site       BOOLEAN;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS international_game BOOLEAN;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS venue_country      VARCHAR(64);
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS venue_timezone     VARCHAR(64);

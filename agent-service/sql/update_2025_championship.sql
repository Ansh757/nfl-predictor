-- Update the 2025 championship matchup in the schedule database.
UPDATE games
SET home_team = 'Seattle Seahawks',
    away_team = 'New England Patriots'
WHERE season = 2025
  AND season_type = 'playoffs'
  AND round = 'Championship';

/**
 * Measured performance, straight from the backtest harness.
 *
 * Reproduce with:
 *   cd agent-service && python backtest.py --season <year> --runs 2
 *
 * These are walk-forward backtest results, not live results. Weights were
 * fitted on 2021-2024, so 2025 is the only season the model had not seen.
 *
 * Re-derived after the neutral-site correction: historical ratings previously
 * credited home-field advantage at every venue, including ~30 completed games
 * where nobody was at home. Only 2021 moved (59.9% -> 59.2%); the held-out
 * 2025 figure is unchanged.
 * Nothing here is rounded up or estimated - a previous version of this project
 * advertised 74.7% from a 48-game sample, and correcting that is why the
 * numbers are pinned to a command anyone can re-run.
 */
export const SEASON_ACCURACY = [
  { season: 2021, games: 272, correct: 161, accuracy: 0.592 },
  { season: 2022, games: 271, correct: 169, accuracy: 0.624 },
  { season: 2023, games: 272, correct: 174, accuracy: 0.640 },
  { season: 2024, games: 272, correct: 187, accuracy: 0.688 },
  { season: 2025, games: 272, correct: 182, accuracy: 0.669 }
];

export const TOTAL_GAMES = SEASON_ACCURACY.reduce((sum, row) => sum + row.games, 0);
export const TOTAL_CORRECT = SEASON_ACCURACY.reduce((sum, row) => sum + row.correct, 0);
export const OVERALL_ACCURACY = TOTAL_CORRECT / TOTAL_GAMES;

/** The season the model had not been fitted on - the only unbiased estimate. */
export const HELD_OUT = SEASON_ACCURACY[SEASON_ACCURACY.length - 1];

export const AGENTS = [
  {
    key: 'market', name: 'Market Odds', accuracy: 0.664, weight: 0.164,
    blurb: 'Reads consensus moneylines across US sportsbooks and strips the bookmaker margin.'
  },
  {
    key: 'elo', name: 'Elo Ratings', accuracy: 0.616, weight: 0.116,
    blurb: 'Opponent-adjusted power ratings with margin-of-victory damping and offseason regression.'
  },
  {
    key: 'stats', name: 'Basic Predictor', accuracy: 0.612, weight: 0.111,
    blurb: 'Records, point differential, recent form and home/away splits over a rolling 17-game window.'
  },
  {
    key: 'rest', name: 'Rest & Travel', accuracy: 0.521, weight: 0.021,
    blurb: 'Rest differential, byes, short weeks, travel distance and body-clock shifts.'
  },
  {
    key: 'injuries', name: 'Injury Impact', accuracy: null, weight: 0.02,
    blurb: 'Live injury reports weighted by position and report status. Not yet calibrated.'
  }
];

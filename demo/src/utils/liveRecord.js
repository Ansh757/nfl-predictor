/**
 * The live record: official picks as recorded before kickoff, and how each one
 * settled. Read from /api/gateway/predictions/recorded.
 *
 * This is the measurement the backtest stands in for. Every row was committed to
 * before its game started and is never rewritten, so unlike a backtest it cannot
 * have been tuned on the games it is scored against.
 */

/** 'correct' | 'wrong' | 'tie' | 'pending' - a word, never just a colour. */
export const outcomeOf = (prediction) => {
  if (!prediction.settled) return 'pending';
  if (prediction.tie || prediction.was_correct == null) return 'tie';
  return prediction.was_correct ? 'correct' : 'wrong';
};

export const OUTCOME_LABEL = {
  correct: 'Model correct',
  wrong: 'Model wrong',
  tie: 'Tie - not scored',
  pending: 'Not played yet',
};

/**
 * Group predictions by week, newest week first, with each week's tally.
 *
 * Accuracy counts scored games only: a tie has no winner to be right about and
 * an unplayed game has no result yet, so neither is a miss.
 */
export const summarizeByWeek = (predictions = []) => {
  const weeks = new Map();
  predictions.forEach((prediction) => {
    const week = prediction.week ?? 0;
    if (!weeks.has(week)) weeks.set(week, []);
    weeks.get(week).push(prediction);
  });

  return [...weeks.entries()]
    .sort(([a], [b]) => b - a)
    .map(([week, games]) => {
      const outcomes = games.map(outcomeOf);
      const correct = outcomes.filter((o) => o === 'correct').length;
      const scored = correct + outcomes.filter((o) => o === 'wrong').length;
      return {
        week,
        games,
        correct,
        scored,
        pending: outcomes.filter((o) => o === 'pending').length,
        ties: outcomes.filter((o) => o === 'tie').length,
        accuracy: scored > 0 ? correct / scored : null,
      };
    });
};

export const totals = (weeks) => {
  const correct = weeks.reduce((sum, w) => sum + w.correct, 0);
  const scored = weeks.reduce((sum, w) => sum + w.scored, 0);
  return {
    correct,
    scored,
    pending: weeks.reduce((sum, w) => sum + w.pending, 0),
    ties: weeks.reduce((sum, w) => sum + w.ties, 0),
    accuracy: scored > 0 ? correct / scored : null,
  };
};

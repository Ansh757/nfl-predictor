/**
 * Formatting for the Rotobot panel. Nothing here computes a projection; every
 * number comes from /games/{id}/rotobot.
 */

export const pct = (p) => `${Math.round(p * 100)}%`;

const one = (n) => (Math.round(n * 10) / 10).toString();
const whole = (n) => Math.round(n).toString();

/** The stat line a fantasy player looks at first, by position. */
export const keyLine = (player) => {
  const s = player.stats;
  if (player.position === 'QB') {
    const line = `${whole(s.passing_yards)} pass yds · ${one(s.passing_tds)} TD · ${one(s.passing_interceptions)} INT`;
    return s.rushing_yards >= 10 ? `${line} · ${whole(s.rushing_yards)} rush` : line;
  }
  if (player.position === 'RB' || player.position === 'FB') {
    return `${whole(s.rushing_yards)} rush yds · ${one(s.receptions)} rec · ${one(s.rushing_tds + s.receiving_tds)} TD`;
  }
  // A receiver used on jet sweeps can score mostly on the ground; show it, or
  // his points look like they came from nowhere.
  const rush = s.rushing_yards >= 10 ? ` · ${whole(s.rushing_yards)} rush` : '';
  return `${one(s.receptions)} rec · ${whole(s.receiving_yards)} yds${rush} · ${one(s.receiving_tds + (s.rushing_tds || 0))} TD`;
};

/** Where the spread and total came from - see rotobot/live.py. */
export const ANCHOR_SOURCE_LABEL = {
  live_market: 'Live betting market',
  live_moneyline: 'Live moneyline',
  nflverse_line: 'Published line',
  closing_line: 'Closing line',
  elo_fallback: 'Elo estimate - no market',
  pick_em_fallback: 'Even - no market',
};

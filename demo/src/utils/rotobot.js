/**
 * Formatting for the Rotobot panel. Nothing here computes a projection; every
 * number comes from /games/{id}/rotobot.
 */

export const pct = (p) => `${Math.round(p * 100)}%`;

const one = (n) => (Math.round(n * 10) / 10).toString();
const whole = (n) => Math.round(n).toString();

/**
 * The stat line a fantasy player looks at first, by position. `stats` defaults
 * to the projection; a played game passes the real line instead.
 */
export const keyLine = (player, s = player.stats) => {
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

const simReady = (data) => data.simulation?.status === 'ready';

/**
 * The score block: the 10,000-run simulation when it is ready, the exact score
 * model until then. Same shape either way.
 */
export const scoreView = (data) => {
  if (simReady(data)) {
    const s = data.simulation;
    return { simulated: true, median: s.median, interval: s.interval, probabilities: s.probabilities };
  }
  return { simulated: false, median: data.median, interval: data.interval, probabilities: data.probabilities };
};

/**
 * One team's player rows. Names, positions and stat lines come from the
 * projection; with a simulation, points and their range come from the
 * simulated games, along with how each player moves with his quarterback.
 */
export const playerView = (data, side) => {
  const block = data.players?.[side];
  if (!block) return [];
  const sim = simReady(data)
    ? Object.fromEntries((data.simulation.players || []).map((p) => [p.player_id, p]))
    : {};
  return block.players
    .map((p) => {
      const s = sim[p.player_id];
      return {
        ...p,
        ppr: s ? s.ppr.mean : p.fantasy.ppr,
        range: s ? [s.ppr.p10, s.ppr.p90] : p.ranges?.ppr,
        withQb: s ? s.correlation?.own_qb ?? null : null,
        actual: p.actual_ppr ?? null,
        actualLine: p.actual_stats ? keyLine(p, p.actual_stats) : null,
      };
    })
    .sort((a, b) => b.ppr - a.ppr);
};

/** Stacks with names, strongest first. */
export const stackView = (data) => {
  if (!simReady(data)) return [];
  const names = {};
  ['home', 'away'].forEach((side) => {
    (data.players?.[side]?.players || []).forEach((p) => { names[p.player_id] = p.name; });
  });
  return (data.simulation.stacks || [])
    .filter((s) => names[s.qb] && names[s.player_id] && s.correlation != null)
    .map((s) => ({ qb: names[s.qb], receiver: names[s.player_id], both: s.both_above_median, correlation: s.correlation }))
    .sort((a, b) => b.both - a.both);
};

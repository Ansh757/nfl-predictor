import { TEAM_ABBREVIATIONS, confidenceBand, teamAbbreviation, teamNickname } from './utils/teams';

/**
 * `teamNickname` is derived rather than tabulated - it takes the last word of
 * the team name. That is only safe because of the two properties asserted here,
 * so a relocation or a rename that broke either would fail loudly instead of
 * quietly rendering the wrong word on every card.
 */
describe('team nicknames', () => {
  const teams = Object.keys(TEAM_ABBREVIATIONS);

  test('every team has one', () => {
    expect(teams).toHaveLength(32);
    for (const team of teams) {
      expect(teamNickname(team)).not.toBe('');
      expect(team.endsWith(teamNickname(team))).toBe(true);
    }
  });

  test('all 32 are distinct, so the card never shows two teams the same name', () => {
    expect(new Set(teams.map(teamNickname)).size).toBe(32);
  });

  test('handles the awkward ones', () => {
    expect(teamNickname('San Francisco 49ers')).toBe('49ers');
    expect(teamNickname('Washington Commanders')).toBe('Commanders');
    expect(teamNickname('New York Giants')).toBe('Giants');
    expect(teamNickname('New York Jets')).toBe('Jets');
  });

  test('does not throw on the values an API can actually return', () => {
    expect(teamNickname('')).toBe('');
    expect(teamNickname(undefined)).toBe('');
    expect(teamNickname(null)).toBe('');
    expect(teamNickname(42)).toBe('');
    expect(teamNickname('  Buffalo   Bills  ')).toBe('Bills');
  });

  test('an unknown team still renders something rather than blank', () => {
    expect(teamNickname('Some XFL Team')).toBe('Team');
    expect(teamAbbreviation('Some XFL Team')).toBe('SOM');
  });
});

/**
 * Lean / Moderate / Strong, not Low / Medium / High.
 *
 * The thresholds were never the problem; the words were. A 59% pick that five
 * of five agents agreed on was labelled LOW, which reads as the model
 * disclaiming itself rather than describing a close game - and most NFL games
 * are close, so that was the common case.
 */
describe('confidence bands', () => {
  test('names the bands for the matchup, not for the model\'s self-esteem', () => {
    expect(confidenceBand(0.55).label).toBe('LEAN');
    expect(confidenceBand(0.68).label).toBe('MODERATE');
    expect(confidenceBand(0.74).label).toBe('STRONG');
  });

  test('the thresholds are unchanged', () => {
    expect(confidenceBand(0.599).label).toBe('LEAN');
    expect(confidenceBand(0.6).label).toBe('MODERATE');
    expect(confidenceBand(0.699).label).toBe('MODERATE');
    expect(confidenceBand(0.7).label).toBe('STRONG');
  });

  test('no pick is not a weak pick', () => {
    // A missing confidence must not fall through to the bottom band.
    expect(confidenceBand(null).label).toBe('—');
    expect(confidenceBand(undefined).label).toBe('—');
  });

  test('the old vocabulary is gone everywhere', () => {
    const labels = [0.5, 0.55, 0.6, 0.65, 0.7, 0.9].map((c) => confidenceBand(c).label);
    expect(labels).not.toContain('LOW');
    expect(labels).not.toContain('MEDIUM');
    expect(labels).not.toContain('HIGH');
  });
});

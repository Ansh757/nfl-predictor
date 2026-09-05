import { TEAM_ABBREVIATIONS, teamAbbreviation, teamNickname } from './utils/teams';

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

import { buildRecords, conferenceTable, formatRecord, hasPlayedGames, winPct } from './utils/standings';
import { TEAM_ALIGNMENT } from './utils/teams';

/**
 * Standings are derived, because there is no standings endpoint. That makes
 * these the tests that stop the Playoffs page inventing data: every number on
 * it comes out of this file, from games that were actually played.
 */
const game = (away, home, awayScore, homeScore) => ({
  away_team: away, home_team: home, away_score: awayScore, home_score: homeScore,
});

describe('reference alignment', () => {
  test('all 32 teams have a conference and division', () => {
    const teams = Object.keys(TEAM_ALIGNMENT);
    expect(teams).toHaveLength(32);
    expect(teams.every((team) => TEAM_ALIGNMENT[team].conference && TEAM_ALIGNMENT[team].division))
      .toBe(true);
  });

  test('each conference has sixteen teams in four divisions', () => {
    const afc = Object.values(TEAM_ALIGNMENT).filter((t) => t.conference === 'AFC');
    const nfc = Object.values(TEAM_ALIGNMENT).filter((t) => t.conference === 'NFC');
    expect(afc).toHaveLength(16);
    expect(nfc).toHaveLength(16);
    expect(new Set(afc.map((t) => t.division))).toEqual(new Set(['East', 'North', 'South', 'West']));
  });
});

describe('building records', () => {
  test('counts wins, losses and ties', () => {
    const records = buildRecords([
      game('Buffalo Bills', 'Miami Dolphins', 24, 17),
      game('Miami Dolphins', 'New York Jets', 20, 20),
    ]);
    expect(formatRecord(records.get('Buffalo Bills'))).toBe('1-0');
    expect(formatRecord(records.get('Miami Dolphins'))).toBe('0-1-1');
    expect(winPct(records.get('Miami Dolphins'))).toBeCloseTo(0.25, 5);
  });

  test('an unplayed game counts as nothing', () => {
    // The critical one. A scheduled fixture with no score must not become a
    // loss for anybody - that is how a standings table starts inventing itself.
    const records = buildRecords([
      game('Buffalo Bills', 'Miami Dolphins', null, null),
      { away_team: 'Buffalo Bills', home_team: 'New York Jets' },
    ]);
    expect(records.size).toBe(0);
    expect(hasPlayedGames(records)).toBe(false);
  });

  test('separates conference and division records', () => {
    const records = buildRecords([
      game('Buffalo Bills', 'Miami Dolphins', 24, 17),       // AFC East, divisional
      game('Buffalo Bills', 'Kansas City Chiefs', 10, 30),    // AFC, not divisional
      game('Buffalo Bills', 'Dallas Cowboys', 21, 14),        // cross-conference
    ]);
    const bills = records.get('Buffalo Bills');
    expect(formatRecord(bills)).toBe('2-1');
    expect([bills.conferenceWins, bills.conferenceLosses]).toEqual([1, 1]);
    expect([bills.divisionWins, bills.divisionLosses]).toEqual([1, 0]);
  });

  test('ignores teams it does not recognise', () => {
    const records = buildRecords([game('Some XFL Team', 'Buffalo Bills', 3, 40)]);
    expect(records.size).toBe(0);
  });
});

describe('conference table', () => {
  const results = [
    game('Buffalo Bills', 'Miami Dolphins', 30, 10),
    game('New York Jets', 'Miami Dolphins', 30, 10),
    game('Buffalo Bills', 'New York Jets', 30, 10),
    game('Dallas Cowboys', 'Philadelphia Eagles', 30, 10),
  ];

  test('orders by win percentage and keeps conferences apart', () => {
    const records = buildRecords(results);
    const afc = conferenceTable(records, 'AFC');
    expect(afc[0].team).toBe('Buffalo Bills');
    expect(afc.map((r) => r.conference)).toEqual(afc.map(() => 'AFC'));
    expect(conferenceTable(records, 'NFC').map((r) => r.team))
      .toEqual(expect.arrayContaining(['Dallas Cowboys', 'Philadelphia Eagles']));
  });

  test('the order is deterministic when records are level', () => {
    // Two calls on the same data must not produce two orders, or the table
    // reshuffles on every render.
    const records = buildRecords(results);
    expect(conferenceTable(records, 'AFC').map((r) => r.team))
      .toEqual(conferenceTable(records, 'AFC').map((r) => r.team));
  });

  test('does not claim to produce an NFL seed', () => {
    // Real seeding puts division winners 1-4 regardless of record and resolves
    // ties through a procedure this data cannot reproduce. The ordering is by
    // win percentage and the UI says so; nothing here should imply otherwise.
    const records = buildRecords(results);
    const row = conferenceTable(records, 'AFC')[0];
    expect(row).not.toHaveProperty('seed');
    expect(row).not.toHaveProperty('clinched');
    expect(row).not.toHaveProperty('eliminated');
  });
});

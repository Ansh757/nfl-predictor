import {
  buildRecords, conferenceTable, formatProjectedRecord, formatRecord, hasPlayedGames,
  hasProjection, projectStandings, projectedConferenceTable, projectedWinPct, winPct,
} from './utils/standings';
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

/**
 * The projection.
 *
 * What it must never become is a playoff probability. That needs the remaining
 * schedule simulated many times over, and nothing in this system can do it - so
 * these pin the projection at exactly what the data supports: the record, plus
 * the games the model has actually published a pick for.
 */
describe('projected standings', () => {
  const scheduled = (away, home, id) => ({
    game_id: id, away_team: away, home_team: home,
  });

  test('folds this week\'s picks into the record', () => {
    const records = buildRecords([game('Buffalo Bills', 'Miami Dolphins', 24, 17)]);
    const projected = projectStandings({
      records,
      games: [scheduled('New York Jets', 'Buffalo Bills', 10)],
      summaries: { 10: { winner: 'Buffalo Bills', confidence: 0.61 } },
    });
    const bills = projected.get('Buffalo Bills');
    expect(formatRecord(bills)).toBe('1-0');
    expect(formatProjectedRecord(bills)).toBe('2-0');
    expect(formatProjectedRecord(projected.get('New York Jets'))).toBe('0-1');
  });

  test('shows its working - which game, and which way', () => {
    const projected = projectStandings({
      games: [scheduled('New England Patriots', 'Seattle Seahawks', 1)],
      summaries: { 1: { winner: 'Seattle Seahawks', confidence: 0.55 } },
    });
    expect(projected.get('Seattle Seahawks').nextGame)
      .toEqual({ opponent: 'New England Patriots', isHome: true, predictedWin: true, confidence: 0.55 });
    expect(projected.get('New England Patriots').nextGame)
      .toMatchObject({ opponent: 'Seattle Seahawks', isHome: false, predictedWin: false });
  });

  test('never counts a game twice', () => {
    // A finished game is already in the record. Projecting it as well would
    // hand the winner two wins for one result.
    const results = [game('Buffalo Bills', 'Miami Dolphins', 24, 17)];
    const projected = projectStandings({
      records: buildRecords(results),
      games: [{ game_id: 5, away_team: 'Buffalo Bills', home_team: 'Miami Dolphins',
                away_score: 24, home_score: 17 }],
      summaries: { 5: { winner: 'Buffalo Bills', confidence: 0.6 } },
    });
    expect(formatProjectedRecord(projected.get('Buffalo Bills'))).toBe('1-0');
    expect(hasProjection(projected)).toBe(false);
  });

  test('projects nothing without a prediction, and says so', () => {
    const projected = projectStandings({
      games: [scheduled('New York Jets', 'Buffalo Bills', 10)],
      summaries: { 10: { error: 'Prediction unavailable' } },
    });
    expect(hasProjection(projected)).toBe(false);
    expect(formatProjectedRecord(projected.get('Buffalo Bills'))).toBe('0-0');
  });

  test('lists all 32 teams even before a game has been played', () => {
    // The failure this replaces: week 1 rendered "No completed games yet" twice
    // and an empty bracket, which is accurate and useless.
    const projected = projectStandings({});
    expect(projected.size).toBe(32);
    expect(projectedConferenceTable(projected, 'AFC')).toHaveLength(16);
  });

  test('orders by the projected record', () => {
    const projected = projectStandings({
      games: [
        { game_id: 1, away_team: 'New York Jets', home_team: 'Buffalo Bills' },
        { game_id: 2, away_team: 'Miami Dolphins', home_team: 'New England Patriots' },
      ],
      summaries: {
        1: { winner: 'Buffalo Bills', confidence: 0.7 },
        2: { winner: 'Miami Dolphins', confidence: 0.6 },
      },
    });
    const afc = projectedConferenceTable(projected, 'AFC');
    expect(afc.slice(0, 2).map((r) => r.team).sort())
      .toEqual(['Buffalo Bills', 'Miami Dolphins']);
    expect(afc[afc.length - 1].team).not.toBe('Buffalo Bills');
  });

  test('produces no probability, seed or clinch of any kind', () => {
    // The line this project keeps: a number it cannot measure is a number it
    // does not print.
    const projected = projectStandings({
      games: [{ game_id: 1, away_team: 'New York Jets', home_team: 'Buffalo Bills' }],
      summaries: { 1: { winner: 'Buffalo Bills', confidence: 0.7 } },
    });
    const row = projected.get('Buffalo Bills');
    for (const forbidden of ['playoffProbability', 'seed', 'clinched', 'eliminated', 'oddsToMakePlayoffs']) {
      expect(row).not.toHaveProperty(forbidden);
    }
  });
});

describe('the playoff-field line', () => {
  test('is not drawn when the teams either side of it are level', () => {
    // Week 1: nine AFC teams projected 1-0. A line after the seventh would say
    // one is in and the next is out on nothing but alphabetical order.
    const projected = projectStandings({});
    const afc = projectedConferenceTable(projected, 'AFC');
    expect(projectedWinPct(afc[6])).toBe(projectedWinPct(afc[7]));
  });
});

describe('a projection never crosses seasons', () => {
  test('ignores games from a season the records do not belong to', () => {
    /*
     * `games` and `records` are fetched separately and settle at different
     * times. Switching the Playoffs season briefly paired 2025's completed
     * 14-3 records with a "this week" column of 2026 week 1 picks - a table
     * that never existed. App.js filters by season before calling this; the
     * assertion here is that a game with no matching season contributes
     * nothing on its own.
     */
    const projected = projectStandings({
      records: buildRecords([game('Buffalo Bills', 'Miami Dolphins', 24, 17)]),
      games: [],
      summaries: {},
    });
    expect(hasProjection(projected)).toBe(false);
    expect(formatProjectedRecord(projected.get('Buffalo Bills'))).toBe('1-0');
  });
});

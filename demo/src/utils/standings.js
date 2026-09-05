/**
 * Conference standings, derived from completed games.
 *
 * There is no standings endpoint. `/games/results` returns every finished game
 * for a season with a winner, which is enough to count records honestly - and
 * counting them is the only way this page can show real data.
 *
 * What this deliberately does NOT do:
 *
 *   - It does not produce an NFL seed. Real seeding runs division winners 1-4
 *     and wild cards 5-7, resolved by a long tiebreaker chain (head-to-head,
 *     division record, common games, strength of victory). The data to do that
 *     properly is not all here, and `games.home_seed` is null on all 77 playoff
 *     rows in the database. Rows are ordered by win percentage and labelled as
 *     such; the UI calls the column "#" and says what it is.
 *   - It does not claim anything is clinched or eliminated. Nothing in the API
 *     says so.
 *   - It does not project. These are games that have been played.
 */
import { TEAM_ALIGNMENT, conferenceOf, divisionOf } from './teams';

const blankRecord = (team) => ({
  team,
  conference: conferenceOf(team),
  division: divisionOf(team),
  wins: 0,
  losses: 0,
  ties: 0,
  conferenceWins: 0,
  conferenceLosses: 0,
  divisionWins: 0,
  divisionLosses: 0,
  played: 0,
});

/** Win percentage, counting a tie as half a win, as the league does. */
export const winPct = (record) =>
  record.played === 0 ? 0 : (record.wins + record.ties * 0.5) / record.played;

export const formatRecord = (record) =>
  record.ties > 0
    ? `${record.wins}-${record.losses}-${record.ties}`
    : `${record.wins}-${record.losses}`;

/**
 * Build a record per team from finished games.
 *
 * `results` is the array from `/games/results`. A game with no winner is a tie
 * when both scores are present, and is skipped entirely when they are not -
 * an unplayed game must not count as anything.
 */
export function buildRecords(results = []) {
  const records = new Map();
  const ensure = (team) => {
    if (!records.has(team)) records.set(team, blankRecord(team));
    return records.get(team);
  };

  results.forEach((game) => {
    const { home_team: home, away_team: away } = game;
    if (!home || !away || !TEAM_ALIGNMENT[home] || !TEAM_ALIGNMENT[away]) return;
    if (game.home_score == null || game.away_score == null) return;

    const homeRecord = ensure(home);
    const awayRecord = ensure(away);
    homeRecord.played += 1;
    awayRecord.played += 1;

    const sameConference = homeRecord.conference === awayRecord.conference;
    const sameDivision = sameConference && homeRecord.division === awayRecord.division;

    const tie = game.home_score === game.away_score;
    const homeWon = game.home_score > game.away_score;
    const winner = tie ? null : (homeWon ? homeRecord : awayRecord);
    const loser = tie ? null : (homeWon ? awayRecord : homeRecord);

    if (tie) {
      homeRecord.ties += 1;
      awayRecord.ties += 1;
      return;
    }

    winner.wins += 1;
    loser.losses += 1;
    if (sameConference) {
      winner.conferenceWins += 1;
      loser.conferenceLosses += 1;
    }
    if (sameDivision) {
      winner.divisionWins += 1;
      loser.divisionLosses += 1;
    }
  });

  return records;
}

/**
 * Teams in one conference, ordered by win percentage.
 *
 * Ties in win percentage are broken by conference record and then alphabetically
 * - enough to make the order stable and reproducible, and explicitly not the
 * league's tiebreaker procedure. The UI must not present this as a seed.
 */
export function conferenceTable(records, conference) {
  return [...records.values()]
    .filter((record) => record.conference === conference)
    .sort((a, b) => {
      const byPct = winPct(b) - winPct(a);
      if (Math.abs(byPct) > 1e-9) return byPct;
      const byConference = (b.conferenceWins - b.conferenceLosses)
        - (a.conferenceWins - a.conferenceLosses);
      if (byConference !== 0) return byConference;
      return a.team.localeCompare(b.team);
    });
}

/** True once at least one game has been played, so the UI can say so. */
export const hasPlayedGames = (records) =>
  [...records.values()].some((record) => record.played > 0);

/**
 * Records with the current week's predicted results folded in.
 *
 * What this is NOT, and the page must not imply otherwise: a playoff
 * probability. That needs the rest of the season simulated - every remaining
 * game predicted, many times, with the results propagated through tiebreakers -
 * and this system has no endpoint that does it. Predicting the remaining
 * schedule from the browser would be 272 calls to /predict per page view, past
 * the rate limit and past the odds API's monthly quota in a single load. A
 * number like "68% playoff probability" would have to be invented, and inventing
 * it is the one thing this project has consistently refused to do.
 *
 * What it IS: the record so far, plus the model's pick for each team's next
 * game. Every input is real - a completed result or a prediction the model has
 * actually published - and the arithmetic is one game deep, which is exactly as
 * far as the data reaches.
 *
 * Only unplayed games with a prediction are projected. A finished season
 * projects nothing and the table falls back to plain records.
 */
export function projectStandings({ records = new Map(), games = [], summaries = {} } = {}) {
  const projected = new Map();
  for (const team of Object.keys(TEAM_ALIGNMENT)) {
    const base = records.get(team) ?? blankRecord(team);
    projected.set(team, {
      ...base,
      projectedWins: base.wins,
      projectedLosses: base.losses,
      projectedTies: base.ties,
      projectedPlayed: base.played,
      // The game this projection came from, so the table can show its working.
      nextGame: null,
    });
  }

  games.forEach((game) => {
    // A game with a result is already in the record; projecting it would count
    // it twice.
    if (game.home_score != null && game.away_score != null) return;
    const summary = summaries?.[game.game_id];
    const winner = summary?.winner;
    if (!winner || summary.error || summary.confidence == null) return;

    const { home_team: home, away_team: away } = game;
    if (!projected.has(home) || !projected.has(away)) return;
    const loser = winner === home ? away : home;
    if (!projected.has(loser) || loser === winner) return;

    [[winner, true], [loser, false]].forEach(([team, won]) => {
      const row = projected.get(team);
      row.projectedWins += won ? 1 : 0;
      row.projectedLosses += won ? 0 : 1;
      row.projectedPlayed += 1;
      row.nextGame = {
        opponent: team === home ? away : home,
        isHome: team === home,
        predictedWin: won,
        confidence: summary.confidence,
      };
    });
  });

  return projected;
}

/** Win percentage of the projected record, counting a tie as half a win. */
export const projectedWinPct = (record) =>
  record.projectedPlayed === 0
    ? 0
    : (record.projectedWins + record.projectedTies * 0.5) / record.projectedPlayed;

export const formatProjectedRecord = (record) =>
  record.projectedTies > 0
    ? `${record.projectedWins}-${record.projectedLosses}-${record.projectedTies}`
    : `${record.projectedWins}-${record.projectedLosses}`;

/** True when at least one row carries a prediction, so the UI can label itself. */
export const hasProjection = (records) =>
  [...records.values()].some((record) => record.nextGame);

/**
 * A conference ordered by the projected record.
 *
 * Same tiebreakers as conferenceTable and the same disclaimer: this is not an
 * NFL seed, and with projections folded in it is even less like one.
 */
export function projectedConferenceTable(records, conference) {
  return [...records.values()]
    .filter((record) => record.conference === conference)
    .sort((a, b) => {
      const byProjected = projectedWinPct(b) - projectedWinPct(a);
      if (Math.abs(byProjected) > 1e-9) return byProjected;
      const byActual = winPct(b) - winPct(a);
      if (Math.abs(byActual) > 1e-9) return byActual;
      return a.team.localeCompare(b.team);
    });
}

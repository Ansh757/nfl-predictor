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

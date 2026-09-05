import { conferenceOf } from './teams';

/**
 * Bracket layout, derived from which teams actually advanced.
 *
 * The obvious approach - pair matches two at a time and halve the count each
 * round - is wrong for this competition, and wrong in a way that looks nearly
 * right. An NFL bracket is not a balanced tree: the top seed in each conference
 * has a bye, so six wild card games feed *four* divisional games, not three. An
 * index-paired layout draws three elbows into four matches and silently
 * mis-attributes every one of them.
 *
 * So the links are read out of the results instead. A match in the next round is
 * fed by any match in this round whose winner is playing in it. That is a fact
 * in the data rather than an assumption about the format, so it survives a bye,
 * a re-seed, and the 2025 postseason's synthetic Super Bowl alike.
 *
 * Positions are then assigned in a virtual row grid: one row per first-round
 * match, and every later match spans the rows of the matches feeding it. A match
 * with no feeders - a bye team's first appearance - takes the next free row.
 * That is enough for CSS grid to place everything, and enough to compute where a
 * connector has to start and finish as a fraction of a cell, with nothing
 * measured at runtime.
 */
export const ROUND_ORDER = ['Wild Card', 'Divisional', 'Conference', 'Super Bowl'];

const winnerOf = (game) => {
  if (game?.home_score == null || game?.away_score == null) return null;
  if (game.home_score === game.away_score) return null;
  return game.home_score > game.away_score ? game.home_team : game.away_team;
};

/** The conference a game belongs to, or null when it spans both. */
export const gameConference = (game) => {
  const home = conferenceOf(game?.home_team);
  const away = conferenceOf(game?.away_team);
  if (home && away && home === away) return home;
  // A game with one known side still belongs to that side's conference; a
  // Super Bowl has two and they differ.
  if (home && away) return null;
  return home || away || null;
};

const feedersFor = (game, previousRound) =>
  previousRound
    .map((candidate, index) => ({ candidate, index }))
    .filter(({ candidate }) => {
      const winner = winnerOf(candidate);
      return winner && (winner === game.home_team || winner === game.away_team);
    })
    .map(({ index }) => index);

/**
 * Lay out one conference's rounds.
 *
 * Returns rounds of placed matches: { game, row, span, feeders } where feeders
 * are indices into the previous round.
 */
const layOutRounds = (rounds) => {
  const placed = [];
  let nextFreeRow = 0;

  rounds.forEach((games, roundIndex) => {
    const previous = placed[roundIndex - 1] ?? [];
    const matches = games.map((game) => {
      const feeders = feedersFor(game, previous.map((entry) => entry.game));
      if (!feeders.length) {
        // A bye, or a round nobody advanced into yet. It gets its own row so it
        // is never drawn as though something fed it.
        const row = roundIndex === 0 ? nextFreeRow : nextFreeRow;
        nextFreeRow += 1;
        return { game, row, span: 1, feeders: [] };
      }
      const spans = feeders.map((index) => previous[index]);
      const row = Math.min(...spans.map((entry) => entry.row));
      const end = Math.max(...spans.map((entry) => entry.row + entry.span));
      return { game, row, span: end - row, feeders };
    });
    placed.push(matches);
  });

  return placed;
};

/**
 * The whole bracket.
 *
 * Conferences are laid out one above the other and the final spans both, which
 * is the arrangement that lets a single left-to-right grid hold all of it.
 */
export function buildBracket(gamesByRound = {}) {
  const rounds = ROUND_ORDER.filter((round) => (gamesByRound[round] ?? []).length);
  if (!rounds.length) return null;

  const conferenceRounds = rounds.filter((round) => round !== 'Super Bowl');
  const conferences = ['AFC', 'NFC'].map((name) => {
    const byRound = conferenceRounds.map((round) =>
      (gamesByRound[round] ?? []).filter((game) => gameConference(game) === name)
    );
    return { name, rounds: layOutRounds(byRound) };
  }).filter((conference) => conference.rounds.some((round) => round.length));

  // Stack the conferences: the second starts below the first.
  let offset = 0;
  const stacked = conferences.map((conference) => {
    const height = Math.max(
      1,
      ...conference.rounds.flatMap((round) => round.map((match) => match.row + match.span))
    );
    const shifted = {
      ...conference,
      rounds: conference.rounds.map((round) =>
        round.map((match) => ({ ...match, row: match.row + offset }))
      ),
      row: offset,
      span: height,
    };
    offset += height;
    return shifted;
  });

  const finalGames = gamesByRound['Super Bowl'] ?? [];
  const totalRows = Math.max(offset, 1);

  return {
    roundNames: rounds,
    conferenceRoundNames: conferenceRounds,
    conferences: stacked,
    // The final is fed by each conference's last round, so it spans everything.
    final: finalGames.map((game) => ({ game, row: 0, span: totalRows, feeders: 'conferences' })),
    totalRows,
  };
}

/**
 * Where a connector meets a cell, as a fraction of that cell's height.
 *
 * The match card is centred in its cell, so its own edge is always at 0.5. A
 * feeder spanning rows [r, r+s) inside a cell spanning [row, row+span) sits at
 * ((r - row) + s / 2) / span. No measurement, and it stays correct at any height
 * because both are expressed in the same row units.
 */
export const feederFraction = (cell, feeder) =>
  ((feeder.row - cell.row) + feeder.span / 2) / cell.span;

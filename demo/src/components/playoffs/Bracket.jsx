import React from 'react';
import { teamAbbreviation, teamLogo } from '../../utils/teams';
import { buildBracket, feederFraction } from '../../utils/bracket';

/**
 * The postseason, connected.
 *
 * Four columns of cards communicate the data; they do not communicate football.
 * Nothing in that layout says the winner of one game is a team in the next,
 * which is the one structural fact a bracket exists to show.
 *
 * The lines are derived, not assumed - see utils/bracket.js for why an
 * index-paired bracket is wrong here - and drawn as percentages of a grid cell,
 * so they stay attached at any width without measuring anything.
 *
 * They are decorative: reading order already pairs each match with its round
 * heading, and a screen reader gaining "line, line, line" between every team
 * would be worse than silence.
 */
const isPlaceholder = (team) => !team || team === 'TBD';

const Side = ({ team, score, won, decided }) => (
  <div className={`flex items-center justify-between gap-2 rounded px-2 py-1.5 ${won ? 'bg-surface-selected' : ''}`}>
    <span className="flex min-w-0 items-center gap-2">
      {!isPlaceholder(team) && (
        <img
          src={teamLogo(team)} alt="" loading="lazy"
          className={`h-4 w-4 flex-shrink-0 object-contain ${decided && !won ? 'opacity-40' : ''}`}
          onError={(event) => { event.currentTarget.style.visibility = 'hidden'; }}
        />
      )}
      <span className={`truncate text-xs ${won ? 'font-semibold text-content' : 'text-content-secondary'}`}>
        {isPlaceholder(team) ? 'TBD' : teamAbbreviation(team)}
      </span>
    </span>
    {score != null && (
      <span className={`tnum text-xs ${won ? 'font-semibold text-content' : 'text-content-muted'}`}>
        {score}
      </span>
    )}
  </div>
);

const Match = ({ game }) => {
  const decided = game.home_score != null && game.away_score != null;
  const homeWon = decided && game.home_score > game.away_score;
  const awayWon = decided && game.away_score > game.home_score;
  return (
    <div className="rounded border border-edge bg-surface-elevated p-1.5">
      <Side team={game.away_team} score={game.away_score} won={awayWon} decided={decided} />
      <Side team={game.home_team} score={game.home_score} won={homeWon} decided={decided} />
    </div>
  );
};

/**
 * The elbow into one match, drawn in the gutter to its left.
 *
 * A stub out of each feeder, a spine joining them, and a stub into this match at
 * its own centre. With one feeder the spine has no height and it reads as a
 * straight line, which is exactly right for a round that did not branch.
 */
const Elbow = ({ fractions }) => {
  if (!fractions.length) return null;
  const top = Math.min(...fractions, 0.5);
  const bottom = Math.max(...fractions, 0.5);
  return (
    <span aria-hidden="true" className="pointer-events-none absolute -left-6 top-0 h-full w-6">
      {fractions.map((fraction, index) => (
        <span
          key={index}
          className="absolute left-0 h-px w-1/2 bg-edge-strong"
          style={{ top: `${fraction * 100}%` }}
        />
      ))}
      <span
        className="absolute left-1/2 w-px bg-edge-strong"
        style={{ top: `${top * 100}%`, height: `${(bottom - top) * 100}%` }}
      />
      <span className="absolute left-1/2 h-px w-1/2 bg-edge-strong" style={{ top: '50%' }} />
    </span>
  );
};

/** A match in its grid cell: the card centred, the connector against the cell. */
const Cell = ({ match, column, fractions }) => (
  <div
    className="relative flex items-center"
    style={{ gridColumn: column, gridRow: `${match.row + 1} / span ${match.span}` }}
  >
    <Elbow fractions={fractions} />
    <div className="w-full">
      <Match game={match.game} />
    </div>
  </div>
);

const Bracket = ({ gamesByRound }) => {
  const layout = buildBracket(gamesByRound);
  if (!layout) return null;

  const { conferenceRoundNames, conferences, final, totalRows, roundNames } = layout;
  const columnCount = roundNames.length;

  return (
    <div className="overflow-x-auto pb-1">
      <div
        className="grid min-w-[680px] gap-x-6 gap-y-2"
        style={{
          gridTemplateColumns: `repeat(${columnCount}, minmax(132px, 1fr))`,
          gridTemplateRows: `auto repeat(${totalRows}, minmax(3.25rem, auto))`,
        }}
      >
        {roundNames.map((round, index) => (
          <h3
            key={round}
            className="pb-1 text-[11px] font-semibold uppercase tracking-wide text-content-muted"
            style={{ gridColumn: index + 1, gridRow: 1 }}
          >
            {round}
          </h3>
        ))}

        {/* One sub-grid row band per conference, offset so the two stack. The
            headings occupy grid row 1, so every match row is shifted by one. */}
        {conferences.map((conference) =>
          conference.rounds.map((matches, roundIndex) =>
            matches.map((match, matchIndex) => {
              const previous = conference.rounds[roundIndex - 1] ?? [];
              const fractions = match.feeders.map((feederIndex) =>
                feederFraction(match, previous[feederIndex])
              );
              return (
                <Cell
                  key={`${conference.name}-${conferenceRoundNames[roundIndex]}-${matchIndex}`}
                  match={{ ...match, row: match.row + 1 }}
                  column={roundIndex + 1}
                  fractions={fractions}
                />
              );
            })
          )
        )}

        {final.map((match, index) => {
          // The final is fed by each conference's last contested round, so the
          // connector reaches the vertical centre of each conference band.
          const fractions = conferences
            .map((conference) => {
              const last = [...conference.rounds].reverse().find((round) => round.length);
              if (!last || last.length !== 1) return null;
              return feederFraction({ row: 0, span: totalRows }, last[0]);
            })
            .filter((fraction) => fraction != null);
          return (
            <Cell
              key={`final-${index}`}
              match={{ ...match, row: 1 }}
              column={columnCount}
              fractions={fractions}
            />
          );
        })}
      </div>
    </div>
  );
};

export default Bracket;

import React from 'react';
import { teamAbbreviation, teamLogo } from '../../utils/teams';
import {
  formatProjectedRecord, formatRecord, projectedWinPct, winPct,
} from '../../utils/standings';

const PLAYOFF_FIELD = 7;

/**
 * One conference, as a table.
 *
 * A table because this is tabular data - ranks, records, percentages compared
 * down a column - and a stack of cards would make that comparison harder for no
 * gain.
 *
 * The rank column is labelled "#" and the caption says what it is: teams ordered
 * by win percentage. It is deliberately not called a seed. Real NFL seeding puts
 * division winners 1-4 regardless of record and resolves ties through a long
 * procedure this data cannot reproduce, and `games.home_seed` is null on every
 * playoff row the API returns. Presenting this as a seed would be inventing
 * standings, which it is not worth doing to match a mockup.
 */
/**
 * Is there anything separating the seventh team from the eighth?
 *
 * The "Playoff field" rule is only honest where the ordering actually puts one
 * team above the other. In week 1 nine AFC teams are projected 1-0, so a line
 * drawn after the seventh says LAC is in and PIT is out on nothing but
 * alphabetical order. Real seeding breaks that tie with a procedure this data
 * cannot reproduce - the same reason the rank column is "#" and not a seed - so
 * where the cut is a tie, the line is not drawn.
 */
const cutIsMeaningful = (rows, projecting) => {
  if (rows.length <= PLAYOFF_FIELD) return false;
  const pct = projecting ? projectedWinPct : winPct;
  return Math.abs(pct(rows[PLAYOFF_FIELD - 1]) - pct(rows[PLAYOFF_FIELD])) > 1e-9;
};

const ConferenceStandings = ({ conference, rows, season, projecting = false }) => (
  <section className="rounded-lg border border-edge bg-surface">
    <div className="flex items-baseline justify-between gap-3 border-b border-edge px-4 py-3">
      <h3 className="text-sm font-semibold text-content">{conference}</h3>
      <p className="text-xs text-content-muted">
        Ordered by {projecting ? 'projected' : 'win'} percentage
      </p>
    </div>

    {rows.length === 0 ? (
      <p className="px-4 py-8 text-center text-sm text-content-muted">
        No completed {season} games yet.
      </p>
    ) : (
      <table className="w-full text-sm">
        <caption className="sr-only">
          {conference} teams for the {season} season, ordered by{' '}
          {projecting ? 'projected' : 'win'} percentage. Rank is not an official NFL seed
          {projecting ? ', and the projection is this week\u2019s predicted results only - not a '
            + 'playoff probability' : ''}.
        </caption>
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-content-muted">
            <th scope="col" className="w-8 py-2 pl-4 text-left font-medium">#</th>
            <th scope="col" className="py-2 text-left font-medium">Team</th>
            <th scope="col" className="py-2 text-left font-medium">Div</th>
            <th scope="col" className="py-2 text-right font-medium">W-L</th>
            <th scope="col" className="py-2 text-right font-medium">Pct</th>
            {projecting ? (
              <>
                <th scope="col" className="py-2 pl-3 text-left font-medium">This week</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">Proj</th>
              </>
            ) : (
              <th scope="col" className="hidden py-2 pr-4 text-right font-medium sm:table-cell">Conf</th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((record, index) => {
            const rank = index + 1;
            const lastIn = rank === PLAYOFF_FIELD;
            return (
              <React.Fragment key={record.team}>
                <tr className="border-t border-edge/60">
                  <td className="tnum py-2 pl-4 text-content-muted">{rank}</td>
                  <th scope="row" className="py-2 text-left font-normal">
                    <span className="flex items-center gap-2">
                      <img
                        src={teamLogo(record.team)}
                        alt={`${record.team} logo`}
                        loading="lazy"
                        className="h-5 w-5 flex-shrink-0 object-contain"
                        onError={(event) => { event.currentTarget.style.visibility = 'hidden'; }}
                      />
                      <span className="font-semibold text-content">{teamAbbreviation(record.team)}</span>
                      <span className="hidden truncate text-xs text-content-muted md:inline">
                        {record.team}
                      </span>
                    </span>
                  </th>
                  <td className="py-2 text-xs text-content-muted">{record.division}</td>
                  <td className="tnum py-2 text-right text-content-secondary">{formatRecord(record)}</td>
                  <td className="tnum py-2 text-right text-content-secondary">
                    {winPct(record).toFixed(3).replace(/^0/, '')}
                  </td>
                  {projecting ? (
                    <>
                      {/* The pick this row's projection came from, so the table
                          shows its working rather than asserting a number. */}
                      <td className="py-2 pl-3 text-xs text-content-muted">
                        {record.nextGame ? (
                          <span className="flex items-center gap-1.5">
                            <span className="tnum">
                              {record.nextGame.isHome ? 'vs' : '@'}{' '}
                              {teamAbbreviation(record.nextGame.opponent)}
                            </span>
                            <span className={record.nextGame.predictedWin ? 'text-accent' : 'text-content-muted'}>
                              {record.nextGame.predictedWin ? 'win' : 'loss'}
                            </span>
                          </span>
                        ) : (
                          <span className="text-content-muted">—</span>
                        )}
                      </td>
                      <td className="tnum py-2 pr-4 text-right text-content-secondary">
                        {formatProjectedRecord(record)}
                      </td>
                    </>
                  ) : (
                    <td className="tnum hidden py-2 pr-4 text-right text-content-muted sm:table-cell">
                      {record.conferenceWins}-{record.conferenceLosses}
                    </td>
                  )}
                </tr>
                {lastIn && cutIsMeaningful(rows, projecting) && (
                  <tr aria-hidden="true">
                    <td colSpan={projecting ? 7 : 6} className="px-4 py-1">
                      <div className="flex items-center gap-2">
                        <span className="h-px flex-1 bg-edge-strong" />
                        <span className="text-[10px] uppercase tracking-wide text-content-muted">
                          Playoff field
                        </span>
                        <span className="h-px flex-1 bg-edge-strong" />
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    )}
  </section>
);

export default ConferenceStandings;

import React from 'react';
import { teamAbbreviation, teamLogo } from '../../utils/teams';
import { formatRecord, winPct } from '../../utils/standings';

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
const ConferenceStandings = ({ conference, rows, season }) => (
  <section className="rounded-lg border border-edge bg-surface">
    <div className="flex items-baseline justify-between gap-3 border-b border-edge px-4 py-3">
      <h3 className="text-sm font-semibold text-content">{conference}</h3>
      <p className="text-xs text-content-muted">Ordered by win percentage</p>
    </div>

    {rows.length === 0 ? (
      <p className="px-4 py-8 text-center text-sm text-content-muted">
        No completed {season} games yet.
      </p>
    ) : (
      <table className="w-full text-sm">
        <caption className="sr-only">
          {conference} teams for the {season} season, ordered by win percentage. Rank is not an
          official NFL seed.
        </caption>
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-content-muted">
            <th scope="col" className="w-8 py-2 pl-4 text-left font-medium">#</th>
            <th scope="col" className="py-2 text-left font-medium">Team</th>
            <th scope="col" className="py-2 text-left font-medium">Div</th>
            <th scope="col" className="py-2 text-right font-medium">W-L</th>
            <th scope="col" className="py-2 text-right font-medium">Pct</th>
            <th scope="col" className="hidden py-2 pr-4 text-right font-medium sm:table-cell">Conf</th>
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
                  <td className="tnum hidden py-2 pr-4 text-right text-content-muted sm:table-cell">
                    {record.conferenceWins}-{record.conferenceLosses}
                  </td>
                </tr>
                {lastIn && rows.length > PLAYOFF_FIELD && (
                  <tr aria-hidden="true">
                    <td colSpan={6} className="px-4 py-1">
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

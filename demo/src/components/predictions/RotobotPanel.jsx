import React, { useEffect, useState } from 'react';
import { teamAbbreviation } from '../../utils/teams';
import { keyLine, ANCHOR_SOURCE_LABEL, pct } from '../../utils/rotobot';

/**
 * Rotobot: the projected score and each player's fantasy line for one game.
 *
 * Read-only, like the pick above it - nothing here responds to the reader, which
 * is what separates it from the simulator this application deliberately does
 * not have (see Interactions.test.js). It is worded as a projection for the
 * same reason: it is one, computed exactly rather than sampled.
 *
 * Its win probability is the betting market's, not the five-agent vote's, and
 * the two can disagree. The panel says so in its first line rather than letting
 * two numbers for the same question sit side by side unexplained.
 */

const PLAYERS_SHOWN = 8;

const Range = ({ range }) => (range ? (
  <span className="tnum text-content-muted">{range[0]}–{range[1]}</span>
) : null);

const TeamScore = ({ team, median, range, final }) => (
  <div className="min-w-0">
    <p className="text-xs text-content-muted">{teamAbbreviation(team)}</p>
    <p className="tnum text-3xl font-semibold leading-tight text-content">{median}</p>
    <p className="tnum text-xs text-content-muted">80% range {range[0]}–{range[1]}</p>
    {final != null && <p className="tnum mt-1 text-xs text-content-secondary">Final {final}</p>}
  </div>
);

const PlayerTable = ({ team, side, played }) => {
  if (!side) return null;
  const players = side.players.slice(0, PLAYERS_SHOWN);
  return (
    <div className="min-w-0 rounded-lg border border-edge bg-surface-elevated p-3">
      <h4 className="text-xs font-semibold text-content">{team}</h4>
      {players.length === 0 ? (
        <p className="mt-2 text-xs text-content-muted">No player history to project from yet.</p>
      ) : (
        <table className="mt-2 w-full text-xs">
          <thead>
            <tr className="text-left text-[11px] text-content-muted">
              <th scope="col" className="pb-1 font-medium">Player</th>
              <th scope="col" className="hidden pb-1 font-medium sm:table-cell">Projected line</th>
              <th scope="col" className="pb-1 text-right font-medium">PPR</th>
              {played && <th scope="col" className="pb-1 text-right font-medium">Actual</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-edge">
            {players.map((p) => (
              <tr key={p.player_id}>
                <td className="py-1.5 pr-2">
                  <span className="text-content">{p.name}</span>{' '}
                  <span className="text-content-muted">{p.position}</span>
                  {/* On a phone the line moves under the name instead of wrapping its own column */}
                  <span className="tnum mt-0.5 block text-[11px] text-content-secondary sm:hidden">{keyLine(p)}</span>
                </td>
                <td className="tnum hidden py-1.5 pr-2 text-content-secondary sm:table-cell">{keyLine(p)}</td>
                <td className="tnum whitespace-nowrap py-1.5 text-right">
                  <span className="font-medium text-content">{p.fantasy.ppr.toFixed(1)}</span>{' '}
                  <Range range={p.ranges?.ppr} />
                </td>
                {played && (
                  <td className="tnum py-1.5 text-right text-content">
                    {p.actual_ppr == null ? 'Did not play' : p.actual_ppr.toFixed(1)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {side.out.length > 0 && (
        <p className="mt-2 text-[11px] leading-relaxed text-content-muted">
          Not projected (injury report): {side.out.join(', ')}
        </p>
      )}
    </div>
  );
};

/**
 * A response is only rendered if it has the shape the panel reads. Anything else
 * - an older API, a proxy error page served as JSON - shows the error state
 * rather than throwing inside render, which would take the whole page down.
 */
export const isProjection = (data) => Boolean(
  data && data.median && data.interval?.home && data.interval?.away && data.interval?.total
  && data.probabilities && data.anchor && data.source
);

const RotobotPanel = ({ game, apiUrl }) => {
  const [state, setState] = useState({ status: 'idle' });

  useEffect(() => {
    if (!game?.game_id) return undefined;
    let active = true;
    setState({ status: 'loading' });
    (async () => {
      try {
        const response = await fetch(`${apiUrl}/games/${game.game_id}/rotobot`);
        if (!response.ok) throw new Error(String(response.status));
        const data = await response.json();
        if (!isProjection(data)) throw new Error('unexpected response');
        if (active) setState({ status: 'ok', data });
      } catch {
        if (active) setState({ status: 'error' });
      }
    })();
    return () => { active = false; };
  }, [apiUrl, game?.game_id]);

  if (!game) return null;
  const data = state.data;
  const played = Boolean(data?.final);

  return (
    <section aria-labelledby="rotobot-heading" className="rounded-lg border border-edge bg-surface p-4">
      <div className="border-b border-edge pb-3">
        <h2 id="rotobot-heading" className="text-base font-semibold text-content">Rotobot projection</h2>
        <p className="mt-0.5 text-xs leading-relaxed text-content-muted">
          Projected score and fantasy lines, built from the betting market&apos;s spread and total.
          Its win probability is the market&apos;s, separate from the five-agent pick above.
        </p>
      </div>

      {state.status === 'loading' && (
        <p className="py-6 text-center text-sm text-content-muted">Projecting…</p>
      )}
      {state.status === 'error' && (
        <p role="alert" className="py-6 text-center text-sm text-danger">Could not load the Rotobot projection.</p>
      )}

      {state.status === 'ok' && (
        <>
          <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-[auto_auto_minmax(0,1fr)] sm:items-start">
            <TeamScore team={data.away_team} median={data.median.away} range={data.interval.away}
              final={data.final?.away} />
            <TeamScore team={data.home_team} median={data.median.home} range={data.interval.home}
              final={data.final?.home} />
            <dl className="col-span-2 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:col-span-1 sm:pl-4">
              <div>
                <dt className="text-content-muted">Market win probability</dt>
                <dd className="tnum text-content">
                  {teamAbbreviation(data.away_team)} {pct(data.probabilities.away_win)} ·{' '}
                  {teamAbbreviation(data.home_team)} {pct(data.probabilities.home_win)}
                </dd>
              </div>
              <div>
                <dt className="text-content-muted">Anchor</dt>
                <dd className="tnum text-content">
                  {teamAbbreviation(data.home_team)} {data.anchor.home_spread > 0 ? '+' : ''}
                  {data.anchor.home_spread} · total {data.anchor.total}
                </dd>
              </div>
              <div>
                <dt className="text-content-muted">Total points, 80% range</dt>
                <dd className="tnum text-content">{data.interval.total[0]}–{data.interval.total[1]}</dd>
              </div>
              <div>
                <dt className="text-content-muted">Line source</dt>
                <dd className="text-content">{ANCHOR_SOURCE_LABEL[data.source.spread] ?? data.source.spread}</dd>
              </div>
            </dl>
          </div>

          {data.players?.available ? (
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <PlayerTable team={data.away_team} side={data.players.away} played={played} />
              <PlayerTable team={data.home_team} side={data.players.home} played={played} />
            </div>
          ) : (
            <p className="mt-4 text-xs text-content-muted">Player projections are not available for this game.</p>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-content-muted">
            PPR scoring. Ranges are where the result landed 80% of the time in seasons the model was
            not fitted on. Players who joined the team recently, including rookies before their
            first game, are not projected.
          </p>
        </>
      )}
    </section>
  );
};

export default RotobotPanel;

import React, { useEffect, useState } from 'react';
import { teamAbbreviation } from '../../utils/teams';
import { TeamLogo } from '../shell/PageIntro';
import { keyLine, ANCHOR_SOURCE_LABEL, pct, scoreView, playerView, stackView } from '../../utils/rotobot';

/**
 * Rotobot: each game simulated play by play, 10,000 times.
 *
 * Read-only, like the pick above it. The application still has no simulator
 * *control* - nothing here responds to the reader (Interactions.test.js) - but
 * it now says plainly how the numbers are made, because that is the point of
 * them: ranges, and how players' results move together, come out of 10,000
 * simulated box scores.
 *
 * The simulation is computed in the background and cached. Until it lands the
 * panel shows the exact score model and the player projections, says the
 * simulation is running, and checks back a few times on its own.
 *
 * Its win probability is calibrated to the betting market, separate from the
 * five-agent pick, and the panel says so in its first line.
 */

const PLAYERS_SHOWN = 8;
const POLL_MS = 8000;
const POLL_TRIES = 10;
// A failed request is retried before the panel gives up: the first request
// after a redeploy wakes the container and downloads the player data, and can
// fail on the way. One failure used to end the panel for that game.
const RETRY_MS = [2000, 5000, 10000];

const Range = ({ range }) => (range ? (
  <span className="tnum text-content-muted">{range[0]}–{range[1]}</span>
) : null);

const TeamScore = ({ team, median, range, final }) => (
  <div className="min-w-0">
    <p className="eyebrow text-content-muted">{teamAbbreviation(team)}</p>
    <p className="tnum font-display text-6xl font-bold leading-none text-content">{median}</p>
    <p className="tnum text-xs text-content-muted">80% range {range[0]}–{range[1]}</p>
    {final != null && <p className="tnum mt-1 text-xs text-content-secondary">Final {final}</p>}
  </div>
);

/** A played game's line column: what happened, once nflverse has posted it. */
const lineFor = (p, played, posted) => {
  if (!played) return keyLine(p);
  if (!posted) return 'Stats not posted yet';
  return p.actualLine ?? '—';               // the Actual column says "Did not play"
};

const PlayerTable = ({ team, rows, out, played, posted, simulated }) => (
  <div className="min-w-0 rounded-lg border border-edge bg-surface-elevated p-4">
    <h4 className="flex items-center gap-2 font-display text-base font-semibold uppercase tracking-wider text-content">
      <TeamLogo team={team} size={22} />
      {team}
    </h4>
    {rows.length === 0 ? (
      <p className="mt-2 text-xs text-content-muted">No player history to project from yet.</p>
    ) : (
      <table className="mt-2 w-full text-xs">
        <thead>
          <tr className="eyebrow text-left text-content-muted">
            <th scope="col" className="pb-1 font-medium">Player</th>
            <th scope="col" className="hidden pb-1 font-medium sm:table-cell">{played ? 'Actual line' : 'Projected line'}</th>
            <th scope="col" className="pb-1 text-right font-medium">{played ? 'Projected PPR' : 'PPR'}</th>
            {simulated && <th scope="col" className="hidden pb-1 text-right font-medium md:table-cell">With QB</th>}
            {played && <th scope="col" className="pb-1 text-right font-medium">Actual</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-edge">
          {rows.slice(0, PLAYERS_SHOWN).map((p) => (
            <tr key={p.player_id}>
              <td className="py-1.5 pr-2">
                <span className="text-content">{p.name}</span>{' '}
                <span className="text-content-muted">{p.position}</span>
                {/* On a phone the line moves under the name instead of wrapping its own column */}
                <span className="tnum mt-0.5 block text-[11px] text-content-secondary sm:hidden">{lineFor(p, played, posted)}</span>
              </td>
              <td className="tnum hidden py-1.5 pr-2 text-content-secondary sm:table-cell">{lineFor(p, played, posted)}</td>
              <td className="tnum whitespace-nowrap py-1.5 text-right">
                <span className="font-medium text-content">{p.ppr.toFixed(1)}</span>{' '}
                <Range range={p.range} />
              </td>
              {simulated && (
                <td className="tnum hidden py-1.5 text-right text-content-secondary md:table-cell">
                  {p.withQb == null ? '—' : p.withQb.toFixed(2)}
                </td>
              )}
              {played && (
                <td className="tnum py-1.5 text-right text-content">
                  {p.actual != null ? p.actual.toFixed(1) : posted ? 'Did not play' : '—'}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    )}
    {out.length > 0 && (
      <p className="mt-2 text-[11px] leading-relaxed text-content-muted">
        Not projected (injury report): {out.join(', ')}
      </p>
    )}
  </div>
);

const Stacks = ({ stacks }) => (stacks.length ? (
  <div className="mt-4">
    <h3 className="font-display text-base font-semibold uppercase tracking-wider text-content">Stacks</h3>
    <p className="mt-0.5 text-[11px] text-content-muted">
      How often a quarterback and a receiver both beat their own median. 25% if their games were
      unrelated; higher means they rise and fall together.
    </p>
    <ul className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {stacks.map((s) => (
        <li key={`${s.qb}-${s.receiver}`} className="rounded-lg border border-edge bg-surface-elevated px-3 py-2 text-xs">
          <span className="text-content">{s.qb} + {s.receiver}</span>
          <span className="tnum mt-0.5 block text-content-secondary">
            Both above median {pct(s.both)} · correlation {s.correlation.toFixed(2)}
          </span>
        </li>
      ))}
    </ul>
  </div>
) : null);

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
    let timer = null;
    setState({ status: 'loading' });

    const load = async (tries, failures = 0) => {
      try {
        const response = await fetch(`${apiUrl}/games/${game.game_id}/rotobot`);
        if (!response.ok) throw new Error(String(response.status));
        const data = await response.json();
        if (!isProjection(data)) throw new Error('unexpected response');
        if (!active) return;
        setState({ status: 'ok', data });
        // The simulation is computed in the background; check back for it
        if (data.simulation?.status === 'pending' && tries < POLL_TRIES) {
          timer = setTimeout(() => load(tries + 1), POLL_MS);
        }
      } catch {
        if (!active) return;
        if (failures < RETRY_MS.length) {
          timer = setTimeout(() => load(tries, failures + 1), RETRY_MS[failures]);
        } else {
          // A failed check-back keeps what is already shown, rather than
          // replacing a loaded projection with an error
          setState((current) => (current.data ? current : { status: 'error' }));
        }
      }
    };
    load(0);
    return () => { active = false; clearTimeout(timer); };
  }, [apiUrl, game?.game_id]);

  if (!game) return null;
  const data = state.data;
  const played = Boolean(data?.final);
  const score = data ? scoreView(data) : null;
  const simulated = score?.simulated;
  const runs = data?.simulation?.runs;

  return (
    <section aria-labelledby="rotobot-heading" className="rounded-xl border border-edge bg-surface p-5 sm:p-6">
      <div className="border-b border-edge pb-4">
        <p className="eyebrow text-brand-text">
          Play by play{game ? ` · ${teamAbbreviation(game.away_team)} @ ${teamAbbreviation(game.home_team)}` : ''}
        </p>
        <h2 id="rotobot-heading" className="mt-1 font-display text-4xl font-bold uppercase text-content">Rotobot simulation</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-content-muted">
          {played && !simulated
            ? 'This game has been played: each player\'s actual line beside what was projected. '
            : `The game simulated play by play ${runs ? `${runs.toLocaleString('en-US')} times` : 'many times'}, `}
          calibrated to the betting market&apos;s spread and total. Its win probability is the
          market&apos;s, separate from the five-agent pick above.
        </p>
      </div>

      {state.status === 'loading' && (
        <p className="py-6 text-center text-sm text-content-muted">Loading…</p>
      )}
      {state.status === 'error' && (
        <p role="alert" className="py-6 text-center text-sm text-danger">Could not load the Rotobot simulation.</p>
      )}

      {state.status === 'ok' && (
        <>
          {data.simulation?.status === 'pending' && (
            <p role="status" className="mt-4 rounded-md border border-edge bg-surface-elevated px-3 py-2 text-xs text-content-secondary">
              The full simulation for this game is running. Showing the score model and player
              projections until it is ready.
            </p>
          )}
          <div className="mt-5 grid grid-cols-2 gap-6 rounded-lg border border-edge bg-background p-5 sm:grid-cols-[auto_auto_minmax(0,1fr)] sm:items-start">
            <TeamScore team={data.away_team} median={score.median.away} range={score.interval.away}
              final={data.final?.away} />
            <TeamScore team={data.home_team} median={score.median.home} range={score.interval.home}
              final={data.final?.home} />
            <dl className="col-span-2 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:col-span-1 sm:pl-4">
              <div>
                <dt className="text-content-muted">Win probability</dt>
                <dd className="tnum text-content">
                  {teamAbbreviation(data.away_team)} {pct(score.probabilities.away_win)} ·{' '}
                  {teamAbbreviation(data.home_team)} {pct(score.probabilities.home_win)}
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
                <dd className="tnum text-content">{score.interval.total[0]}–{score.interval.total[1]}</dd>
              </div>
              <div>
                <dt className="text-content-muted">Line source</dt>
                <dd className="text-content">{ANCHOR_SOURCE_LABEL[data.source.spread] ?? data.source.spread}</dd>
              </div>
              {simulated && score.probabilities.overtime != null && (
                <div>
                  <dt className="text-content-muted">Goes to overtime</dt>
                  <dd className="tnum text-content">{pct(score.probabilities.overtime)}</dd>
                </div>
              )}
            </dl>
          </div>

          {data.players?.available ? (
            <>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                {['away', 'home'].map((side) => (
                  <PlayerTable key={side} team={data[`${side}_team`]}
                    rows={playerView(data, side)} out={data.players[side]?.out ?? []}
                    played={played} posted={data.players[side]?.actual_posted !== false}
                    simulated={simulated} />
                ))}
              </div>
              {simulated && <Stacks stacks={stackView(data)} />}
            </>
          ) : (
            <p className="mt-4 text-xs text-content-muted">Player projections are not available for this game.</p>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-content-muted">
            PPR scoring. {simulated
              ? '"With QB" is how closely a player\'s points rise and fall with his quarterback\'s across the simulated games.'
              : 'Ranges are where the result landed 80% of the time in seasons the model was not fitted on.'}
            {' '}Players who joined the team recently, including rookies before their first game, are not projected.
          </p>
        </>
      )}
    </section>
  );
};

export default RotobotPanel;

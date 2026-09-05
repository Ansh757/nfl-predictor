import React from 'react';
import { teamAbbreviation, teamLogo, confidenceBand } from '../../utils/teams';
import { easternHint } from '../../utils/time';

/**
 * Why the model picked what it picked.
 *
 * Two numbers per agent, and they are not the same measurement, so they are not
 * presented the same way:
 *
 *   confidence  - how sure that agent is, on its own. A bar.
 *   influence   - weight x (confidence - 0.5), how much it actually moved the
 *                 vote. A percentage of the total, as text.
 *
 * An agent can be 75% confident and contribute almost nothing, which is the
 * whole point of weighting by measured accuracy. Both come from the API; nothing
 * here is computed for display.
 */
const AgentSummary = ({ agent, insight }) => {
  const Icon = agent.icon;
  const hasData = insight?.hasData !== false;
  const confidence = insight?.confidence;

  return (
    <div className="min-w-[200px] rounded-lg border border-edge bg-surface p-3 lg:min-w-0">
      <div className="flex items-center gap-2">
        {Icon && <Icon aria-hidden="true" className="h-3.5 w-3.5 text-content-muted" />}
        <h4 className="text-xs font-semibold text-content-secondary">{agent.label}</h4>
      </div>

      {insight?.predictedWinner ? (
        <>
          <div className="mt-2 flex items-baseline justify-between gap-2">
            <span className="truncate text-sm font-semibold text-content">
              {teamAbbreviation(insight.predictedWinner)}
            </span>
            <span className="tnum text-sm text-content-secondary">
              {hasData ? `${Math.round(confidence * 100)}%` : '—'}
            </span>
          </div>

          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-edge" aria-hidden="true">
            <div
              className={hasData ? 'h-full bg-accent' : 'h-full bg-content-muted'}
              style={{ width: `${hasData ? Math.max(0, (confidence - 0.5) * 200) : 0}%` }}
            />
          </div>

          <dl className="mt-2 space-y-0.5 text-[11px]">
            <div className="flex justify-between gap-2">
              <dt className="text-content-muted">Weight</dt>
              <dd className="tnum text-content-secondary">{(insight.weight ?? 0).toFixed(3)}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-content-muted">Influence</dt>
              <dd className="tnum text-content-secondary">
                {hasData && insight.influenceShare != null
                  ? `${Math.round(insight.influenceShare * 100)}% of the call`
                  : 'none'}
              </dd>
            </div>
          </dl>

          {insight.reasoning && (
            <p className="mt-2 line-clamp-3 text-[11px] leading-relaxed text-content-muted">
              {insight.reasoning}
            </p>
          )}
        </>
      ) : (
        <p className="mt-2 text-xs text-content-muted">{insight?.status || 'Awaiting data'}</p>
      )}
    </div>
  );
};

const ConsensusSummary = ({ game, summary }) => {
  const band = confidenceBand(summary.confidence);
  const winner = summary.winner;

  return (
    <aside className="w-full rounded-lg border border-edge bg-surface p-4 lg:w-80 lg:flex-shrink-0">
      <div className="flex items-center gap-3">
        <img src={teamLogo(winner)} alt={`${winner} logo`} className="h-10 w-10 object-contain" />
        <div className="min-w-0">
          <div className="text-[10px] font-medium uppercase tracking-wide text-content-muted">
            Official model pick
          </div>
          <div className="truncate text-lg font-semibold text-content">{winner}</div>
        </div>
      </div>

      <dl className="mt-3 space-y-1.5 border-t border-edge pt-3 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-content-muted">Win probability</dt>
          <dd className="tnum font-semibold text-content">{Math.round(summary.confidence * 100)}%</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-content-muted">Confidence</dt>
          <dd className={band.tone === 'success' ? 'text-success' : band.tone === 'warning' ? 'text-warning' : 'text-content-secondary'}>
            {band.label}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-content-muted">Agent consensus</dt>
          <dd className="tnum text-content-secondary">{summary.consensus?.label}</dd>
        </div>
        {summary.consensus?.winnerInfluence != null && (
          <div className="flex justify-between gap-3">
            <dt className="text-content-muted">Weighted influence</dt>
            <dd className="tnum text-content-secondary">
              {Math.round(summary.consensus.winnerInfluence * 100)}%
            </dd>
          </div>
        )}
        {summary.lockedAt && (
          <div className="flex justify-between gap-3">
            <dt className="text-content-muted">Recorded</dt>
            <dd className="tnum text-content-secondary">{summary.lockedAt}</dd>
          </div>
        )}
      </dl>

      {summary.reasoning && (
        <p className="mt-3 border-t border-edge pt-3 text-xs leading-relaxed text-content-secondary">
          {summary.reasoning.split(' | ')[0]}
        </p>
      )}

      {summary.conditions?.summary && (
        <p className="mt-2 text-xs text-content-muted">
          Conditions: {summary.conditions.summary}
        </p>
      )}

      {(summary.internationalGame || summary.neutralSite) && (
        <p className="mt-2 border-t border-edge pt-2 text-xs text-content-muted">
          {summary.internationalGame
            ? `International game${summary.venueCountry ? ` in ${summary.venueCountry}` : ''}. Standard home-field advantage removed and travel scored for both sides.`
            : 'Neutral site — the designated home team is not at its own ground, so no home-field advantage was applied.'}
        </p>
      )}
    </aside>
  );
};

const SelectedGameAnalysis = ({ game, summary, isPredicting, agentDefinitions, formatTime }) => {
  if (!game) {
    return (
      <section className="rounded-lg border border-edge bg-surface p-8 text-center">
        <p className="text-sm text-content-muted">Select a game to see the multi-agent analysis.</p>
      </section>
    );
  }

  const matchup = `${teamAbbreviation(game.away_team)} @ ${teamAbbreviation(game.home_team)}`;
  const eastern = easternHint(game.game_date);

  return (
    <section className="rounded-lg border border-edge bg-surface-elevated p-4" aria-live="polite">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-edge pb-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-base font-semibold text-content">
            {summary?.winner ? `Why ${teamAbbreviation(summary.winner)}?` : matchup}
          </h2>
          <p className="text-xs text-content-muted">
            Multi-agent analysis for {matchup}
          </p>
        </div>
        <p className="tnum text-xs text-content-muted">
          {formatTime(game.game_date)}
          {eastern && <span> · {eastern}</span>}
          {game.venue && <span> · {game.venue}</span>}
        </p>
      </div>

      {isPredicting ? (
        <p className="py-8 text-center text-sm text-content-muted">Running agents…</p>
      ) : summary?.error ? (
        <p role="alert" className="py-8 text-center text-sm text-danger">{summary.error}</p>
      ) : !summary?.winner ? (
        <p className="py-8 text-center text-sm text-content-muted">No prediction available.</p>
      ) : (
        <div className="mt-3 flex flex-col gap-3 lg:flex-row">
          {/* Horizontally scrollable below lg rather than crushed to five
              unreadable columns. */}
          <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-1 lg:mx-0 lg:grid lg:flex-1 lg:grid-cols-3 lg:overflow-visible lg:px-0 xl:grid-cols-5">
            {agentDefinitions.map((agent) => (
              <AgentSummary key={agent.key} agent={agent} insight={summary.agentInsights?.[agent.key]} />
            ))}
          </div>
          <ConsensusSummary game={game} summary={summary} />
        </div>
      )}
    </section>
  );
};

export default SelectedGameAnalysis;

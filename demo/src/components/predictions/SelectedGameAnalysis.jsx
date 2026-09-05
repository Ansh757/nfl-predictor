import React from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { teamAbbreviation, teamLogo, confidenceBand } from '../../utils/teams';
import { easternHint } from '../../utils/time';
import { reasoningPoints } from '../../utils/reasoning';

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
/**
 * One agent's read, as a summary rather than a diagnostic dump.
 *
 * This section is the reason the product is interesting - Market says SEA,
 * Form says NE, Elo says SEA, and then the vote decides - but that comparison
 * was buried. Five narrow columns each held a paragraph of the agent's own
 * factors, so the thing a reader came for was behind a wall of text they had to
 * commit to before they could see whether it was worth reading.
 *
 * So the top of the card answers the question ("who, and how sure") and the
 * first three factors say why, in the agent's own words. Everything that is
 * model diagnostics rather than reasoning - weight, contribution, the remaining
 * factors - goes behind Details. Nothing is removed; the transparency is intact
 * for anyone who wants it, and no longer mandatory for everyone who does not.
 */
const AgentPick = ({ insight, hasData, aligned }) => {
  if (!hasData) {
    return <span className="text-xs font-medium text-content-muted">No data</span>;
  }
  return (
    /* The abbreviation is the information; the colour only reinforces it, so a
       reader who cannot separate the two hues loses nothing. */
    <span className={`text-sm font-semibold ${aligned ? 'text-accent' : 'text-content-secondary'}`}>
      {teamAbbreviation(insight.predictedWinner)}
    </span>
  );
};

/**
 * Factors, one per line.
 *
 * The API joins them into a paragraph; this is that paragraph split back apart,
 * not a summary written here. The tick is aria-hidden and marks a factor the
 * agent actually used - so an agent reporting that its feed was unavailable
 * gets a neutral dot instead, since ticking "Injury feed unavailable" would
 * read as confirming it.
 */
const Factors = ({ points, hasData }) => (
  <ul className="mt-2.5 space-y-1">
    {points.map((point) => (
      <li key={point} className="flex gap-1.5 text-[11px] leading-snug text-content-muted">
        {hasData ? (
          <Check aria-hidden="true" className="mt-0.5 h-3 w-3 flex-shrink-0 text-accent/70" />
        ) : (
          <span aria-hidden="true" className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-content-muted" />
        )}
        <span>{point}</span>
      </li>
    ))}
  </ul>
);

const AgentSummary = ({ agent, insight, winner }) => {
  const Icon = agent.icon;
  const hasData = insight?.hasData !== false;
  const confidence = insight?.confidence;
  const aligned = insight?.predictedWinner === winner;

  // Everything the agent said. The first three are the summary; the rest join
  // the technical detail rather than being dropped.
  const points = reasoningPoints(insight?.reasoning, 8);
  const shown = points.slice(0, 3);
  const rest = points.slice(3);

  if (!insight?.predictedWinner) {
    return (
      <div className="rounded-lg border border-edge bg-surface p-3">
        <div className="flex items-center gap-1.5">
          {Icon && <Icon aria-hidden="true" className="h-3.5 w-3.5 text-content-muted" />}
          <h4 className="text-[11px] font-semibold uppercase tracking-wide text-content-secondary">
            {agent.label}
          </h4>
        </div>
        <p className="mt-2 text-xs text-content-muted">{insight?.status || 'Awaiting data'}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col rounded-lg border border-edge bg-surface p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          {Icon && <Icon aria-hidden="true" className="h-3.5 w-3.5 flex-shrink-0 text-content-muted" />}
          <h4 className="truncate text-[11px] font-semibold uppercase tracking-wide text-content-secondary">
            {agent.label}
          </h4>
        </div>
        <AgentPick insight={insight} hasData={hasData} aligned={aligned} />
      </div>

      {/*
        * Confidence, drawn against the full 0-100 scale with the coin flip
        * marked - the same bar the matchup card uses, for the same reason. It
        * previously scaled (confidence - 0.5) x 200, so a 63% agent drew a bar
        * 26% wide directly beside the number "63%".
        */}
      <div className="mt-2.5 flex items-center gap-2">
        <span className="tnum w-8 text-sm font-semibold text-content">
          {hasData ? `${Math.round(confidence * 100)}%` : '—'}
        </span>
        <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-edge" aria-hidden="true">
          <span
            className={`block h-full ${hasData ? 'bg-accent' : 'bg-opposing'}`}
            style={{ width: `${hasData ? Math.round(confidence * 100) : 0}%` }}
          />
          {/* The coin flip, marked. 52% and 66% are very different reads and
              the distance past this line is the whole of it. */}
          <span className="absolute left-1/2 top-0 h-full w-[3px] -translate-x-1/2 bg-background" />
        </span>
      </div>

      {/*
        * Confidence and influence are not the same measurement, which is the
        * single most useful thing this panel has to say: an agent can be 75%
        * sure and move the vote by nothing, because weight is measured accuracy
        * and Rest & Travel's is 0.021.
        */}
      <div className="mt-2 flex items-baseline justify-between gap-2 border-t border-edge pt-2">
        <span className="text-[11px] text-content-muted">Influence</span>
        <span className="tnum text-[11px] font-medium text-content-secondary">
          {hasData && insight.influenceShare != null
            ? `${Math.round(insight.influenceShare * 100)}%`
            : 'none'}
        </span>
      </div>

      {shown.length > 0 && <Factors points={shown} hasData={hasData} />}

      <details className="group mt-2.5 border-t border-edge pt-2">
        <summary className="flex cursor-pointer list-none items-center justify-end gap-1 text-[11px] font-medium text-content-muted transition hover:text-content">
          Details
          <ChevronDown aria-hidden="true" className="h-3 w-3 transition-transform group-open:rotate-180" />
        </summary>

        {rest.length > 0 && <Factors points={rest} hasData={hasData} />}

        <dl className="mt-2 space-y-0.5 text-[11px]">
          <div className="flex justify-between gap-2">
            <dt className="text-content-muted">Weight</dt>
            <dd className="tnum text-content-secondary">{(insight.weight ?? 0).toFixed(3)}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-content-muted">Contribution</dt>
            <dd className="tnum text-content-secondary">
              {(insight.contribution ?? 0).toFixed(4)}
            </dd>
          </div>
        </dl>

        <p className="mt-2 text-[11px] leading-snug text-content-muted">
          {hasData
            ? `Weight is this agent's measured edge over a coin flip. Contribution is weight × (confidence − 0.5) — what it actually added to ${teamAbbreviation(insight.predictedWinner)}.`
            : 'This agent reported no usable data, so it returned exactly 0.50 and contributed nothing rather than guessing.'}
        </p>
      </details>
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
          {/*
            * Two columns on a phone-width scroll, three on a laptop, five only
            * where there is genuinely room. Five columns at 1440px gave each
            * agent about 200px, which is half of why this section read as dense.
            */}
          <div className="grid flex-1 grid-cols-1 items-start gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
            {agentDefinitions.map((agent) => (
              <AgentSummary
                key={agent.key}
                agent={agent}
                insight={summary.agentInsights?.[agent.key]}
                winner={summary.winner}
              />
            ))}
          </div>
          <ConsensusSummary game={game} summary={summary} />
        </div>
      )}
    </section>
  );
};

export default SelectedGameAnalysis;

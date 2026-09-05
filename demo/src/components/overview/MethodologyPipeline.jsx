import React from 'react';
import { teamAbbreviation } from '../../utils/teams';
import { AGENTS } from '../../utils/performance';

/**
 * How a prediction is actually made, as a pipeline rather than five essays.
 *
 * The previous version put five equal boxes of prose side by side, each with a
 * blurb, an accuracy and a weight. That is the implementation, explained before
 * anyone asked for it. What a reader needs first is the shape: five signals go
 * in, they are combined by weight, one pick comes out.
 *
 * The detail is not deleted - it moves into a <details> below, which is the one
 * disclosure control that is keyboard-accessible and screen-reader-correct
 * without any JavaScript.
 */

/** Short labels for the diagram. The full names live in the expanded detail. */
const SHORT = {
  market: 'Market',
  elo: 'Elo',
  stats: 'Form',
  rest: 'Rest',
  injuries: 'Injuries',
};

const Node = ({ agent }) => (
  <li className="flex flex-col items-center gap-1 text-center">
    <span className="w-full rounded border border-edge bg-surface-elevated px-2 py-2">
      <span className="block text-[11px] font-semibold uppercase tracking-wide text-content-secondary">
        {SHORT[agent.key] ?? agent.name}
      </span>
      <span className="tnum mt-0.5 block text-sm font-semibold text-content">
        {(agent.accuracy * 100).toFixed(1)}%
      </span>
    </span>
  </li>
);

/**
 * The converging lines.
 *
 * Decorative, so hidden from assistive technology - the list above and the
 * caption below already say what this draws. Percentages rather than pixels
 * because each of the five columns is a fifth of the width, which puts the
 * first and last centres at 10% and 90% at any size.
 */
const Connectors = () => (
  <div aria-hidden="true" className="hidden lg:block">
    <div className="grid grid-cols-5">
      {AGENTS.map((agent) => (
        <span key={agent.key} className="mx-auto h-5 w-px bg-edge-strong" />
      ))}
    </div>
    {/* Spans centre-to-centre: each of five columns is a fifth of the width, so
        the first and last centres sit at 10% and 90% at any size. */}
    <div className="mx-[10%] h-px bg-edge-strong" />
    <div className="mx-auto h-5 w-px bg-edge-strong" />
  </div>
);

const Arrow = () => (
  <span aria-hidden="true" className="mx-auto block h-5 w-px bg-edge-strong" />
);

const MethodologyPipeline = ({ featuredGame, featuredSummary }) => {
  // The outcome node shows a real prediction when one is loaded rather than a
  // worked example - an invented "SEA 55%" would be the only fabricated number
  // on the page.
  const winner = featuredSummary?.winner;
  const hasOutcome = Boolean(winner && featuredSummary?.confidence != null);

  return (
    <section className="rounded-lg border border-edge bg-surface p-5 lg:p-6">
      <h2 className="text-sm font-semibold text-content">How a pick is made</h2>
      <p className="mt-1 text-xs text-content-muted">
        Five signals, each weighted by how accurate it has been in backtest over 2021–2024.
      </p>

      <div className="mt-5">
        <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {AGENTS.map((agent) => <Node key={agent.key} agent={agent} />)}
        </ol>
        <Connectors />

        {/* Below lg the connectors are dropped and a single stem carries the
            flow, because five converging lines in two columns reads as noise. */}
        <span aria-hidden="true" className="mx-auto mt-4 block h-5 w-px bg-edge-strong lg:hidden" />

        <div className="mx-auto max-w-xs rounded border border-accent/40 bg-surface-elevated px-4 py-2.5 text-center">
          <span className="block text-[11px] font-semibold uppercase tracking-wide text-accent">
            Weighted consensus
          </span>
        </div>

        {hasOutcome && (
          <>
            <Arrow />
            <div className="mx-auto max-w-xs rounded border border-edge bg-surface-elevated px-4 py-2.5 text-center">
              <span className="text-base font-semibold text-content">
                {teamAbbreviation(winner)}
              </span>
              <span className="tnum ml-2 text-sm text-content-secondary">
                {Math.round(featuredSummary.confidence * 100)}%
              </span>
              <span className="mt-0.5 block text-[11px] text-content-muted">
                {featuredGame
                  ? `${teamAbbreviation(featuredGame.away_team)} @ ${teamAbbreviation(featuredGame.home_team)}`
                  : 'this week'}
              </span>
            </div>
          </>
        )}
      </div>

      <details className="group mt-5 border-t border-edge pt-4">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-medium text-content-secondary transition hover:text-content">
          <span
            aria-hidden="true"
            className="inline-block transition-transform group-open:rotate-90"
          >
            ›
          </span>
          How weighting works
        </summary>

        <div className="mt-3 space-y-3">
          <p className="text-xs leading-relaxed text-content-secondary">
            Each agent contributes <span className="tnum">weight × (confidence − 0.5)</span> to
            the side it picks. Weight is the agent's measured edge over a coin flip, floored at
            zero — so an agent that cannot beat 50% literally cannot move a prediction, however
            sure it is. An agent with no data returns exactly 0.50 and contributes nothing rather
            than guessing.
          </p>

          <ul className="space-y-2">
            {AGENTS.map((agent) => (
              <li key={agent.key} className="grid gap-x-3 gap-y-0.5 sm:grid-cols-[8rem_5rem_minmax(0,1fr)]">
                <span className="text-xs font-medium text-content">{agent.name}</span>
                <span className="tnum text-xs text-content-secondary">
                  {agent.accuracy ? `${(agent.accuracy * 100).toFixed(1)}%` : 'unmeasured'}
                  <span className="text-content-muted"> · {agent.weight}</span>
                </span>
                <span className="text-xs leading-relaxed text-content-muted">{agent.blurb}</span>
              </li>
            ))}
          </ul>
        </div>
      </details>
    </section>
  );
};

export default MethodologyPipeline;

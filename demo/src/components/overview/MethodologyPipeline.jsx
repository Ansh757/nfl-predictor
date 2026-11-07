import React from 'react';
import { ChevronRight } from 'lucide-react';
import { SectionHead, TeamLogo } from '../shell/PageIntro';
import { teamAbbreviation } from '../../utils/teams';
import { AGENTS } from '../../utils/performance';

/**
 * How a prediction is actually made: five signal cards, then the weighted
 * consensus they feed.
 *
 * Each card carries what that agent is (accuracy, weight, what it reads) and,
 * when a game is loaded, what it said about the featured game. The consensus
 * underneath shows a real prediction rather than a worked example - an invented
 * "SEA 55%" would be the only fabricated number on the page.
 *
 * The formula stays behind a native <details>: keyboard and screen-reader
 * correct with no JavaScript, and available rather than presented first.
 */

/** Short labels for the cards. The full names live in the disclosure. */
const SHORT = {
  market: 'Market',
  elo: 'Elo',
  stats: 'Form',
  rest: 'Rest',
  injuries: 'Injuries',
};

const pct = (value) => `${(value * 100).toFixed(1)}%`;

const AgentCard = ({ agent, index, maxWeight, call }) => (
  <li className="flex flex-col rounded-lg border border-edge bg-surface p-5">
    <div className="flex items-center justify-between">
      <span aria-hidden="true" className="font-display text-xs font-bold text-content-muted">0{index + 1}</span>
      <span className="eyebrow text-content-muted">{SHORT[agent.key] ?? agent.name}</span>
    </div>
    <p className="tnum mt-4 font-display text-4xl font-bold text-content">{pct(agent.accuracy)}</p>
    <p className="text-xs text-content-muted">backtest accuracy</p>
    <div className="mt-4">
      <div className="flex justify-between text-xs text-content-muted">
        <span>Weight</span>
        <span className="tnum">{agent.weight.toFixed(3)}</span>
      </div>
      <div aria-hidden="true" className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-elevated">
        <div className="h-full rounded-full bg-accent" style={{ width: `${(agent.weight / maxWeight) * 100}%` }} />
      </div>
    </div>
    <p className="mt-4 flex-1 text-sm leading-relaxed text-content-muted">{agent.blurb}</p>
    {call?.predictedWinner && (
      <div className="mt-4 flex items-center gap-2 border-t border-edge pt-3">
        {call.hasData === false ? (
          <span className="text-sm text-content-muted">No data · sits out</span>
        ) : (
          <>
            <TeamLogo team={call.predictedWinner} size={22} />
            <span className="font-display text-sm font-semibold text-content">
              {teamAbbreviation(call.predictedWinner)}
            </span>
            <span className="tnum ml-auto text-sm text-content-muted">
              {Math.round(call.confidence * 100)}%
            </span>
          </>
        )}
      </div>
    )}
  </li>
);

const MethodologyPipeline = ({ featuredGame, featuredSummary }) => {
  const winner = featuredSummary?.winner;
  const hasOutcome = Boolean(winner && featuredSummary?.confidence != null && !featuredSummary?.error);
  const maxWeight = Math.max(...AGENTS.map((agent) => agent.weight));
  const matchup = featuredGame
    ? `${teamAbbreviation(featuredGame.away_team)} @ ${teamAbbreviation(featuredGame.home_team)}`
    : null;

  return (
    <section aria-labelledby="pipeline-heading" className="pt-20">
      <SectionHead eyebrow="The model" title="How a pick is made" id="pipeline-heading">
        Five signals, each weighted by its measured edge over a coin flip in 2021–2024 backtests.
        {hasOutcome && matchup ? ` Shown here for ${matchup}.` : ''}
      </SectionHead>

      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {AGENTS.map((agent, index) => (
          <AgentCard
            key={agent.key}
            agent={agent}
            index={index}
            maxWeight={maxWeight}
            call={hasOutcome ? featuredSummary.agentInsights?.[agent.key] : null}
          />
        ))}
      </ol>

      {hasOutcome && (
        <div className="relative mt-3">
          <div aria-hidden="true" className="stripe mx-auto h-px w-full opacity-60" />
          <div className="mx-auto -mt-px flex max-w-md flex-col items-center">
            <div aria-hidden="true" className="h-8 w-px bg-edge" />
            <div className="glow w-full rounded-xl border border-edge bg-surface px-6 py-5 text-center">
              <p className="eyebrow text-content-muted">Weighted consensus</p>
              <div className="mt-2 flex items-center justify-center gap-3">
                <TeamLogo team={winner} size={36} />
                <span className="font-display text-3xl font-bold text-content">{teamAbbreviation(winner)}</span>
                <span className="tnum font-display text-3xl font-bold text-accent">
                  {Math.round(featuredSummary.confidence * 100)}%
                </span>
              </div>
              {matchup && <p className="mt-1 text-xs text-content-muted">{matchup}</p>}
            </div>
          </div>
        </div>
      )}

      <details className="group mt-8 rounded-lg border border-edge bg-surface px-6 py-4">
        <summary className="flex cursor-pointer list-none items-center gap-2 font-display text-sm font-semibold uppercase tracking-wider text-content">
          <ChevronRight aria-hidden="true" className="h-4 w-4 transition-transform group-open:rotate-90" />
          How weighting works
        </summary>
        <div className="mt-3 max-w-3xl space-y-3">
          <p className="text-sm leading-relaxed text-content-muted">
            Each agent contributes <span className="tnum">weight × (confidence − 0.5)</span> to the
            side it picks. Weight is the agent's measured edge over a coin flip, floored at zero — so
            an agent that cannot beat 50% cannot move a prediction, however sure it is. An agent with
            no data returns exactly 0.50 and contributes nothing rather than guessing.
          </p>
          <ul className="space-y-1">
            {AGENTS.map((agent) => (
              <li key={agent.key} className="flex flex-wrap gap-x-3 text-sm">
                <span className="w-32 font-medium text-content">{agent.name}</span>
                <span className="tnum text-content-muted">
                  {pct(agent.accuracy)} · weight {agent.weight}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </details>
    </section>
  );
};

export default MethodologyPipeline;

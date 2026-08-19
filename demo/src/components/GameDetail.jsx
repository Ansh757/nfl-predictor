import React from 'react';
import { AlertCircle, CheckCircle2, CloudSun, Trophy, Users } from 'lucide-react';
import { confidenceBand, teamAbbreviation, teamLogo } from '../utils/teams';

const BAND_TONE = {
  success: 'bg-positive/15 text-positive',
  warning: 'bg-caution/15 text-caution',
  muted: 'bg-slate-700/40 text-slate-400'
};

/** Bars are coloured by the agent's measured influence, not by which side it picked. */
const AGENT_TONE = {
  market: 'bg-accent', stats: 'bg-insight', elo: 'bg-positive',
  rest: 'bg-caution', injuries: 'bg-slate-400'
};

const AgentBreakdown = ({ agentDefinitions, insights }) => (
  <section className="mt-5">
    <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">Agent breakdown</h3>
    <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {agentDefinitions.map((agent) => {
        const insight = insights?.[agent.key];
        const Icon = agent.icon;
        const share = insight?.influenceShare ?? 0;
        return (
          <div key={agent.key} className="rounded-2xl border border-ink-700 bg-ink-800 p-3">
            <div className="flex items-center gap-2">
              <Icon aria-hidden="true" className="h-4 w-4 text-slate-400" />
              <span className="truncate text-xs font-semibold text-slate-300">{agent.label}</span>
            </div>

            <div className="mt-2 flex items-baseline justify-between gap-2">
              <span className="text-sm font-bold text-mist">
                {insight?.predictedWinner ? teamAbbreviation(insight.predictedWinner) : '—'}
              </span>
              <span className="text-sm font-bold text-slate-300">
                {insight?.confidence != null ? `${Math.round(insight.confidence * 100)}%` : '—'}
              </span>
            </div>

            {/* Width is the agent's share of the weighted decision, so a
                confident agent with no measured edge reads as a flat bar. */}
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink-700">
              <div
                className={`h-full rounded-full ${AGENT_TONE[agent.key] || 'bg-slate-500'}`}
                style={{ width: `${Math.max(share * 100, insight ? 2 : 0)}%` }}
              />
            </div>
            <div className="mt-1 text-[11px] text-slate-500">
              {insight?.weight === 0
                ? 'no influence'
                : insight?.hasData === false
                ? 'no data'
                : share > 0
                ? `${share < 0.01 ? '<1' : Math.round(share * 100)}% of the call`
                : '—'}
            </div>
          </div>
        );
      })}
    </div>
  </section>
);

const KeyFactors = ({ insights, conditions, agentDefinitions }) => {
  // Ordered by how much each agent actually moved the decision
  const ranked = agentDefinitions
    .map((agent) => ({ agent, insight: insights?.[agent.key] }))
    .filter((row) => row.insight?.reasoning && row.insight.weight > 0)
    .sort((a, b) => (b.insight.influenceShare ?? 0) - (a.insight.influenceShare ?? 0))
    .slice(0, 3);

  return (
    <section className="rounded-2xl border border-ink-700 bg-ink-800 p-4">
      <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">Key factors</h3>
      <ul className="mt-3 space-y-2">
        {ranked.map(({ agent, insight }) => (
          <li key={agent.key} className="flex gap-2 text-sm">
            <CheckCircle2 aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0 text-positive" />
            <span className="text-slate-300">
              <span className="font-semibold text-mist">{agent.label}:</span>{' '}
              {insight.reasoning.split('. ')[0]}.
            </span>
          </li>
        ))}
        {conditions?.summary && (
          <li className="flex gap-2 text-sm">
            <CloudSun aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0 text-caution" />
            <span className="text-slate-300">
              <span className="font-semibold text-mist">Conditions:</span> {conditions.summary}
            </span>
          </li>
        )}
        {!ranked.length && !conditions?.summary && (
          <li className="text-sm text-slate-500">No factors carried measurable weight.</li>
        )}
      </ul>
    </section>
  );
};

const GameDetail = ({ game, summary, isPredicting, agentDefinitions, formatTime }) => {
  if (!game) {
    return (
      <section className="flex min-h-[24rem] items-center justify-center rounded-2xl border border-ink-700 bg-ink-900 p-6">
        <div className="text-center">
          <Users aria-hidden="true" className="mx-auto h-10 w-10 text-slate-600" />
          <p className="mt-3 text-sm text-slate-400">Select a game to see the breakdown</p>
        </div>
      </section>
    );
  }

  const winner = summary?.winner;
  const confidence = summary?.confidence;
  const band = confidenceBand(confidence);
  const homeIsWinner = winner === game.home_team;
  const homeShare = winner ? (homeIsWinner ? confidence : 1 - confidence) : 0.5;

  return (
    <section className="rounded-2xl border border-ink-700 bg-ink-900 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-mist">
            {teamAbbreviation(game.away_team)} vs {teamAbbreviation(game.home_team)}
          </h2>
          <p className="mt-1 text-xs text-slate-400">{formatTime(game.game_date)}</p>
          {game.venue && <p className="text-xs text-slate-500">{game.venue}</p>}
        </div>
      </div>

      {isPredicting ? (
        <div role="status" className="py-12 text-center text-sm text-slate-400">Running agents…</div>
      ) : summary?.error ? (
        <div role="alert" className="mt-4 rounded-xl border border-red-500/40 bg-red-500/5 px-4 py-6 text-center">
          <div className="text-sm font-semibold text-red-400">Prediction unavailable</div>
          <div className="mt-1 text-xs text-slate-400">{summary.error}</div>
        </div>
      ) : !summary ? (
        <div className="py-12 text-center text-sm text-slate-400">No prediction yet</div>
      ) : (
        <>
          <div className="mt-5 flex items-center justify-between gap-4">
            <div className="flex flex-col items-center gap-1">
              <img src={teamLogo(game.away_team)} alt="" aria-hidden="true" className="h-12 w-12 object-contain" />
              <span className="text-2xl font-bold text-mist">{Math.round((1 - homeShare) * 100)}%</span>
              <span className="text-[11px] uppercase text-slate-400">{teamAbbreviation(game.away_team)}</span>
            </div>
            <span className="text-xs font-semibold text-slate-500">VS</span>
            <div className="flex flex-col items-center gap-1">
              <img src={teamLogo(game.home_team)} alt="" aria-hidden="true" className="h-12 w-12 object-contain" />
              <span className="text-2xl font-bold text-mist">{Math.round(homeShare * 100)}%</span>
              <span className="text-[11px] uppercase text-slate-400">{teamAbbreviation(game.home_team)}</span>
            </div>
          </div>

          <div className="mt-3 flex h-2.5 overflow-hidden rounded-full bg-ink-700">
            <div className="bg-slate-500" style={{ width: `${(1 - homeShare) * 100}%` }} />
            <div className="bg-accent" style={{ width: `${homeShare * 100}%` }} />
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4 text-sm">
            <span className="flex items-center gap-2">
              <Trophy aria-hidden="true" className="h-4 w-4 text-caution" />
              <span className="text-slate-400">Predicted winner:</span>
              <span className="font-semibold text-mist">{winner}</span>
            </span>
            <span className="flex items-center gap-2">
              <span className="text-slate-400">Confidence:</span>
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${BAND_TONE[band.tone]}`}>
                {band.label}
              </span>
            </span>
            <span className="flex items-center gap-2">
              <Users aria-hidden="true" className="h-4 w-4 text-slate-400" />
              <span className="text-slate-400">Agent consensus:</span>
              <span className="font-semibold text-mist">
                {summary.consensus?.count}/{summary.consensus?.total}
              </span>
            </span>
            {summary.consensus?.winnerInfluence != null && (
              <span className="text-xs text-slate-500">
                {Math.round(summary.consensus.winnerInfluence * 100)}% of weighted influence
              </span>
            )}
          </div>

          <AgentBreakdown agentDefinitions={agentDefinitions} insights={summary.agentInsights} />

          <div className="mt-5 grid gap-3 lg:grid-cols-2">
            <KeyFactors
              insights={summary.agentInsights}
              conditions={summary.conditions}
              agentDefinitions={agentDefinitions}
            />
            <section className="rounded-2xl border border-ink-700 bg-ink-800 p-4">
              <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">Consensus reasoning</h3>
              <p className="mt-3 flex gap-2 text-sm text-slate-300">
                <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-500" />
                <span>{summary.reasoning?.split(' | ')[0]}</span>
              </p>
            </section>
          </div>
        </>
      )}
    </section>
  );
};

export default GameDetail;

import React from 'react';
import { ArrowRight, BarChart3, Gauge, Github, Plane, Activity, Trophy, Users } from 'lucide-react';
import AccuracyChart from './AccuracyChart';
import { teamAbbreviation, teamLogo, confidenceBand } from '../utils/teams';
import {
  AGENTS, HELD_OUT, OVERALL_ACCURACY, SEASON_ACCURACY, TOTAL_CORRECT, TOTAL_GAMES
} from '../utils/performance';

const AGENT_ICON = {
  market: BarChart3, elo: Gauge, stats: Activity, rest: Plane, injuries: Users
};

const Donut = ({ value }) => {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  return (
    <svg viewBox="0 0 140 140" className="h-36 w-36" role="img"
         aria-label={`Historical backtest accuracy across 2021 to 2025, ${(value * 100).toFixed(1)} percent`}>
      <circle cx="70" cy="70" r={radius} fill="none" stroke="#1E293B" strokeWidth="12" />
      <circle
        cx="70" cy="70" r={radius} fill="none" stroke="#2563EB" strokeWidth="12"
        strokeLinecap="round" transform="rotate(-90 70 70)"
        strokeDasharray={`${value * circumference} ${circumference}`}
      />
      <text x="70" y="66" textAnchor="middle" fontSize="22" fontWeight="700" fill="#E2E8F0">
        {(value * 100).toFixed(1)}%
      </text>
      <text x="70" y="86" textAnchor="middle" fontSize="8" fill="#64748B">BACKTEST 2021–25</text>
    </svg>
  );
};

const FeaturedMatchup = ({ game, summary, week, onOpen }) => {
  if (!game || !summary?.winner) {
    return (
      <div className="rounded-3xl border border-ink-700 bg-ink-800/60 p-8 text-center">
        <Trophy aria-hidden="true" className="mx-auto h-10 w-10 text-slate-600" />
        <p className="mt-3 text-sm text-slate-400">Predictions appear here once a week is loaded</p>
      </div>
    );
  }

  const band = confidenceBand(summary.confidence);
  const homeIsWinner = summary.winner === game.home_team;
  const homeShare = homeIsWinner ? summary.confidence : 1 - summary.confidence;

  return (
    <div className="rounded-3xl border border-accent/30 bg-ink-800/60 p-6 shadow-2xl shadow-accent/5">
      <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-wider">
        <span className="text-accent">Featured matchup</span>
        <span className="text-slate-500">Week {week}</span>
      </div>

      <div className="mt-5 flex items-center justify-between gap-4">
        {[{ team: game.away_team, share: 1 - homeShare }, { team: game.home_team, share: homeShare }]
          .map((side, index) => (
            <React.Fragment key={side.team}>
              {index === 1 && <span className="text-xs font-semibold text-slate-600">vs</span>}
              <div className="flex flex-1 flex-col items-center gap-1">
                <img src={teamLogo(side.team)} alt="" aria-hidden="true" className="h-11 w-11 object-contain" />
                <span className="text-2xl font-bold text-mist">{Math.round(side.share * 100)}%</span>
                <span className="text-[11px] font-semibold text-slate-400">{teamAbbreviation(side.team)}</span>
              </div>
            </React.Fragment>
          ))}
      </div>
      <p className="mt-1 text-center text-[10px] uppercase tracking-wider text-slate-500">Win probability</p>

      <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-ink-700">
        <div className="bg-slate-500" style={{ width: `${(1 - homeShare) * 100}%` }} />
        <div className="bg-accent" style={{ width: `${homeShare * 100}%` }} />
      </div>

      <div className="mt-5 rounded-2xl border border-ink-700 bg-ink-900 p-4 text-center">
        <p className="text-[10px] uppercase tracking-wider text-slate-500">Predicted winner</p>
        <p className="mt-1 text-base font-bold text-mist">{summary.winner}</p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-center">
        <div>
          <p className="text-sm font-bold text-positive">{band.label}</p>
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Confidence</p>
        </div>
        <div>
          <p className="text-sm font-bold text-mist">
            {summary.consensus?.count} / {summary.consensus?.total}
          </p>
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Agent consensus</p>
        </div>
      </div>

      <button
        type="button" onClick={onOpen}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90"
      >
        View full analysis <ArrowRight aria-hidden="true" className="h-4 w-4" />
      </button>
    </div>
  );
};

const LandingPage = ({ featuredGame, featuredSummary, week, onExplore }) => (
  <div className="space-y-6">
    <section className="grid items-center gap-8 rounded-3xl border border-ink-700 bg-ink-800/40 p-6 lg:grid-cols-2 lg:p-10">
      <div>
        <span className="inline-block rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-accent">
          Multi-agent
        </span>
        <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight text-mist lg:text-5xl">
          NFL<br /><span className="text-accent">PREDICTIONS</span>
        </h1>
        <p className="mt-4 text-lg font-semibold text-slate-300">
          Don't just predict the game. Understand the prediction.
        </p>
        <p className="mt-3 max-w-md text-sm leading-relaxed text-slate-400">
          Five agents read the betting market, power ratings, team form, schedule
          situation and injury reports. Each is weighted by how accurate it has
          actually been, so you can see not just the pick but which signal drove it.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button" onClick={onExplore}
            className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90"
          >
            Explore predictions <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </button>
          <a
            href="https://github.com/Ansh757/nfl-predictor"
            target="_blank" rel="noreferrer"
            className="flex items-center gap-2 rounded-xl border border-ink-700 px-5 py-2.5 text-sm font-semibold text-mist transition hover:border-slate-600"
          >
            <Github aria-hidden="true" className="h-4 w-4" /> Source
          </a>
        </div>

        <dl className="mt-8 grid grid-cols-3 gap-4 border-t border-ink-700 pt-6">
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-slate-500">
              {HELD_OUT.season} backtest accuracy
            </dt>
            <dd className="text-xl font-bold text-mist">{(HELD_OUT.accuracy * 100).toFixed(1)}%</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-slate-500">Agents</dt>
            <dd className="text-xl font-bold text-mist">{AGENTS.length}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-slate-500">Seasons</dt>
            <dd className="text-xl font-bold text-mist">2021–2025</dd>
          </div>
        </dl>
        {/* The headline number is a historical measurement, and reads as a
            promise unless it is labelled as one. */}
        <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
          {(HELD_OUT.accuracy * 100).toFixed(1)}% is measured on the {HELD_OUT.season} season,
          held out of the weight fitting — it is how the model scored on games already played,
          not a guarantee of {HELD_OUT.season + 1} performance.
        </p>
      </div>

      <FeaturedMatchup
        game={featuredGame} summary={featuredSummary} week={week} onOpen={onExplore}
      />
    </section>

    <section className="rounded-3xl border border-ink-700 bg-ink-900 p-6 lg:p-10">
      <h2 className="text-center text-sm font-bold uppercase tracking-widest text-slate-400">How it works</h2>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {AGENTS.map((agent) => {
          const Icon = AGENT_ICON[agent.key] || Activity;
          return (
            <div key={agent.key} className="rounded-2xl border border-ink-700 bg-ink-800 p-4">
              <Icon aria-hidden="true" className="h-5 w-5 text-accent" />
              <h3 className="mt-3 text-xs font-bold uppercase tracking-wide text-mist">{agent.name}</h3>
              <p className="mt-2 text-xs leading-relaxed text-slate-400">{agent.blurb}</p>
              <p className="mt-3 text-[11px] font-semibold text-slate-500">
                {agent.accuracy
                  ? `${(agent.accuracy * 100).toFixed(1)}% · weight ${agent.weight}`
                  : `not yet measured · weight ${agent.weight}`}
              </p>
            </div>
          );
        })}
      </div>

      <div className="mt-6 flex flex-col items-center gap-3">
        <div className="rounded-2xl border border-accent/30 bg-accent/10 px-6 py-3 text-center">
          <p className="text-xs font-bold uppercase tracking-wide text-accent">Weighted consensus</p>
          <p className="mt-1 text-xs text-slate-400">
            Each agent contributes weight × (confidence − 0.5), so an agent with no
            measured edge cannot move the pick however sure it is.
          </p>
        </div>
      </div>
    </section>

    <section className="rounded-3xl border border-ink-700 bg-ink-900 p-6 lg:p-10">
      <h2 className="text-center text-sm font-bold uppercase tracking-widest text-slate-400">
        Built on measured performance
      </h2>
      <p className="mx-auto mt-2 max-w-xl text-center text-xs leading-relaxed text-slate-500">
        Every figure below is historical: a walk-forward backtest over seasons that
        have already been played. Past accuracy is not a forecast of future results.
      </p>

      <div className="mt-6 grid items-center gap-8 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <AccuracyChart data={SEASON_ACCURACY} />
          <p className="mt-2 text-center text-xs text-slate-500">
            Walk-forward backtest. Weights were fitted on 2021–2024, so {HELD_OUT.season} is
            the only season the model had not seen.
          </p>
        </div>

        <div className="flex flex-col items-center gap-5">
          <Donut value={OVERALL_ACCURACY} />
          <dl className="grid w-full grid-cols-3 gap-3 text-center">
            <div>
              <dd className="text-lg font-bold text-mist">{TOTAL_GAMES.toLocaleString()}</dd>
              <dt className="text-[10px] uppercase tracking-wider text-slate-500">Games</dt>
            </div>
            <div>
              <dd className="text-lg font-bold text-positive">{TOTAL_CORRECT.toLocaleString()}</dd>
              <dt className="text-[10px] uppercase tracking-wider text-slate-500">Correct</dt>
            </div>
            <div>
              <dd className="text-lg font-bold text-mist">{(HELD_OUT.accuracy * 100).toFixed(1)}%</dd>
              <dt className="text-[10px] uppercase tracking-wider text-slate-500">
                {HELD_OUT.season} held out
              </dt>
            </div>
          </dl>
        </div>
      </div>
    </section>

    <section className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-accent/30 bg-accent/10 p-6 lg:p-8">
      <div>
        <h2 className="text-lg font-bold text-mist">Ready to see this week's predictions?</h2>
        <p className="mt-1 text-sm text-slate-400">
          Every game, with the agent breakdown behind each pick.
        </p>
      </div>
      <button
        type="button" onClick={onExplore}
        className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90"
      >
        View Week {week} predictions <ArrowRight aria-hidden="true" className="h-4 w-4" />
      </button>
    </section>
  </div>
);

export default LandingPage;

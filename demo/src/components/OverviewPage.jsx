import React from 'react';
import { ArrowRight, Github } from 'lucide-react';
import AccuracyChart from './AccuracyChart';
import MatchupCard from './predictions/MatchupCard';
import { InlineDisclaimer } from './Disclaimer';
import {
  AGENTS, HELD_OUT, OVERALL_ACCURACY, SEASON_ACCURACY, TOTAL_CORRECT, TOTAL_GAMES,
} from '../utils/performance';

/**
 * The one page that explains the product.
 *
 * Deliberately not the Predictions workspace: one introduction, one featured
 * game, the method, the measured record. Display type appears here and nowhere
 * else in the application.
 *
 * The historical/live distinction is the thing this page most has to get right,
 * so it is stated three times in three registers - a labelled heading, a
 * sentence under the headline figure, and the chart caption.
 */
const OverviewPage = ({
  featuredGame, featuredSummary, formatTime, onExplore, onOpenGame, liveAccuracy, season,
}) => (
  <div className="space-y-4">
    <section className="grid gap-6 rounded-lg border border-edge bg-surface p-5 lg:grid-cols-[minmax(0,1fr)_24rem] lg:p-8">
      <div className="max-w-xl">
        <h1 className="font-display text-3xl font-semibold leading-tight tracking-tight text-content lg:text-4xl">
          Don't just predict the game.<br />Understand the prediction.
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-content-secondary">
          Five agents read the betting market, power ratings, team form, schedule situation and
          injury reports. Each is weighted by how accurate it has actually been in backtest, so
          every pick shows not just the winner but which signal drove it.
        </p>

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button" onClick={onExplore}
            className="flex h-10 items-center gap-2 rounded bg-accent px-4 text-sm font-semibold text-accent-on transition hover:bg-accent-hover"
          >
            Explore predictions <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </button>
          <a
            href="https://github.com/Ansh757/nfl-predictor"
            target="_blank" rel="noreferrer"
            className="flex h-10 items-center gap-2 rounded border border-edge px-4 text-sm font-medium text-content-secondary transition hover:border-edge-strong hover:text-content"
          >
            <Github aria-hidden="true" className="h-4 w-4" /> Source
          </a>
        </div>

        <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-edge pt-5 sm:grid-cols-3">
          <div>
            <dt className="text-xs text-content-muted">{HELD_OUT.season} backtest accuracy</dt>
            <dd className="tnum mt-0.5 text-xl font-semibold text-content">
              {(HELD_OUT.accuracy * 100).toFixed(1)}%
            </dd>
          </div>
          <div>
            <dt className="text-xs text-content-muted">{season} live accuracy</dt>
            <dd className="tnum mt-0.5 text-xl font-semibold text-content">
              {liveAccuracy == null ? '—' : `${(liveAccuracy * 100).toFixed(1)}%`}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-content-muted">Agents</dt>
            <dd className="tnum mt-0.5 text-xl font-semibold text-content">{AGENTS.length}</dd>
          </div>
        </dl>
        <p className="mt-3 text-xs leading-relaxed text-content-muted">
          These are two different measurements. {(HELD_OUT.accuracy * 100).toFixed(1)}% is a
          walk-forward backtest on {HELD_OUT.season}, a season held out of the weight fitting — how
          the model scored on games already played. {season} live accuracy counts only predictions
          recorded before kickoff and settled against the result
          {liveAccuracy == null ? ', and stays blank until the first games are scored' : ''}.
          Neither is a guarantee of future performance.
        </p>
      </div>

      <div className="lg:pt-1">
        <h2 className="pb-2 text-xs font-semibold uppercase tracking-wide text-content-muted">
          Featured matchup
        </h2>
        {featuredGame && featuredSummary?.winner ? (
          <MatchupCard
            game={featuredGame}
            summary={featuredSummary}
            isSelected={false}
            onSelect={onOpenGame}
            formatTime={formatTime}
          />
        ) : (
          <div className="rounded-lg border border-edge bg-surface-elevated p-6 text-center">
            <p className="text-sm text-content-muted">
              Predictions appear here once a week is loaded.
            </p>
          </div>
        )}
      </div>
    </section>

    <section className="rounded-lg border border-edge bg-surface p-5 lg:p-6">
      <h2 className="text-sm font-semibold text-content">How it works</h2>
      <p className="mt-1 text-xs text-content-muted">
        Each agent contributes weight × (confidence − 0.5), so an agent with no measured edge
        cannot move a pick however sure it is.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {AGENTS.map((agent) => (
          <div key={agent.key} className="rounded border border-edge bg-surface-elevated p-3">
            <h3 className="text-xs font-semibold text-content">{agent.name}</h3>
            <p className="mt-1.5 text-xs leading-relaxed text-content-muted">{agent.blurb}</p>
            <p className="tnum mt-2 text-xs text-content-secondary">
              {agent.accuracy
                ? `${(agent.accuracy * 100).toFixed(1)}% · weight ${agent.weight}`
                : `not yet measured · weight ${agent.weight}`}
            </p>
          </div>
        ))}
      </div>
    </section>

    <section className="rounded-lg border border-edge bg-surface p-5 lg:p-6">
      <h2 className="text-sm font-semibold text-content">Historical backtest performance</h2>
      <p className="mt-1 text-xs text-content-muted">
        Walk-forward backtest over seasons already played. Weights were fitted on 2021–2024, so
        {' '}{HELD_OUT.season} is the only season the model had not seen. This is not live accuracy.
      </p>

      <div className="mt-4 grid items-center gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <AccuracyChart data={SEASON_ACCURACY} />
        <dl className="grid grid-cols-3 gap-3 border-t border-edge pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          <div>
            <dt className="text-xs text-content-muted">Games</dt>
            <dd className="tnum mt-0.5 text-lg font-semibold text-content">{TOTAL_GAMES.toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-xs text-content-muted">Correct</dt>
            <dd className="tnum mt-0.5 text-lg font-semibold text-content">{TOTAL_CORRECT.toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-xs text-content-muted">Overall</dt>
            <dd className="tnum mt-0.5 text-lg font-semibold text-content">
              {(OVERALL_ACCURACY * 100).toFixed(1)}%
            </dd>
          </div>
        </dl>
      </div>
      <InlineDisclaimer className="mt-4 border-t border-edge pt-3" />
    </section>
  </div>
);

export default OverviewPage;

import React from 'react';
import { ArrowRight, ChevronRight } from 'lucide-react';
import stadium from '../assets/stadium-night.jpg';
import MethodologyPipeline from './overview/MethodologyPipeline';
import LiveRecord from './overview/LiveRecord';
import { ProbabilityBar, SectionHead, TeamLogo } from './shell/PageIntro';
import { SOURCE_URL } from './shell/TopHeader';
import { confidenceBand, teamAbbreviation, teamNickname } from '../utils/teams';
import {
  AGENTS, HELD_OUT, OVERALL_ACCURACY, SEASON_ACCURACY, TOTAL_CORRECT, TOTAL_GAMES,
} from '../utils/performance';

/**
 * The one page that explains the product: a headline over a stadium at night,
 * the featured game, how a pick is made, the live record, the backtest.
 *
 * The historical/live distinction is the thing this page most has to get right,
 * so it is stated three times in three registers - the labels on the hero
 * figures, a sentence under them, and the backtest section's own caption.
 */

const pct = (value, digits = 1) => (value == null ? '—' : `${(value * 100).toFixed(digits)}%`);

const HeroStat = ({ label, value, tone }) => (
  <div>
    <dt className="eyebrow text-content-muted">{label}</dt>
    <dd className={`tnum mt-1 font-display text-4xl font-bold sm:text-5xl lg:text-[clamp(2.25rem,6svh,3rem)] ${
      tone === 'success' ? 'text-success' : 'text-content'
    }`}>
      {value}
    </dd>
  </div>
);

/**
 * The game the page is advertising, as a pick.
 *
 * "View full analysis" carries the same sentence-shaped accessible name a
 * matchup card does, and selects that game on the Predictions page rather than
 * dropping the reader into a list to find it again.
 */
const FeaturedMatchup = ({ game, summary, formatTime, onOpenGame }) => {
  const winner = summary.winner;
  const confidence = summary.confidence;
  const homeProbability = winner === game.home_team ? confidence : 1 - confidence;
  const band = confidenceBand(confidence);
  const consensus = summary.consensus;
  const voters = Object.values(summary.agentInsights ?? {}).filter((i) => i?.predictedWinner);

  return (
    <div className="glow animate-rise overflow-hidden rounded-xl border border-edge bg-surface">
      <div className="flex items-center justify-between border-b border-edge px-6 py-3">
        <h3 className="eyebrow text-brand-text">Featured matchup</h3>
        <p className="eyebrow tnum text-content-muted">{formatTime(game.game_date)}</p>
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 px-6 pt-6">
        {[game.away_team, null, game.home_team].map((team, index) => (team ? (
          <div key={team} className="flex flex-col items-center text-center">
            <TeamLogo team={team} size={72} />
            <p className="mt-3 font-display text-3xl font-bold text-content">{teamAbbreviation(team)}</p>
            <p className="text-sm text-content-muted">{teamNickname(team)}</p>
          </div>
        ) : (
          <span key={index} aria-hidden="true" className="font-display text-2xl font-bold text-content-muted">@</span>
        )))}
      </div>

      <div className="px-6 pt-5">
        <ProbabilityBar homeProbability={homeProbability} homePicked={winner === game.home_team} thick />
      </div>

      <div className="mt-5 border-t border-edge bg-background px-6 py-5 text-center">
        <p className="eyebrow text-content-muted">Predicted winner</p>
        <p className="mt-1 font-display text-5xl font-extrabold uppercase tracking-wide text-content">
          {teamNickname(winner)}
        </p>
        <div className="mt-3 flex flex-wrap items-center justify-center gap-4 text-sm">
          <span className="tnum font-display text-xl font-bold text-accent">{pct(confidence)}</span>
          {consensus?.label && (
            <>
              <span aria-hidden="true" className="h-4 w-px bg-edge" />
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="flex gap-1.5">
                  {voters.map((insight, index) => (
                    <span
                      key={index}
                      className={`h-2 w-2 rounded-full ${insight.predictedWinner === winner ? 'bg-accent' : 'bg-edge-strong'}`}
                    />
                  ))}
                </span>
                <span className="tnum ml-1 text-content-muted">{consensus.label}</span>
              </span>
            </>
          )}
          <span aria-hidden="true" className="h-4 w-px bg-edge" />
          <span className="font-display font-semibold uppercase tracking-widest text-content">{band.label}</span>
        </div>
        <button
          type="button"
          onClick={() => onOpenGame(game)}
          aria-label={`${game.away_team} at ${game.home_team}. Model picks ${winner}, ${Math.round(confidence * 100)} percent. View analysis`}
          className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-content-muted transition hover:text-content"
        >
          View full analysis <ChevronRight aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

const Hero = ({ featuredGame, featuredSummary, formatTime, onExplore, onOpenGame, liveAccuracy, season }) => (
  <section className="relative left-1/2 isolate w-screen -translate-x-1/2 overflow-hidden border-b border-edge">
    {/* Decoration only: the headline reads over it, so it is darkened by two
        overlays and hidden from assistive technology. */}
    <img
      src={stadium}
      alt=""
      aria-hidden="true"
      className="absolute inset-0 -z-20 h-full w-full object-cover object-right opacity-70"
    />
    <div aria-hidden="true" className="hero-overlay absolute inset-0 -z-10" />
    <div aria-hidden="true" className="hero-fade absolute inset-0 -z-10" />

    <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 pb-12 pt-10 sm:px-6 lg:min-h-[calc(100svh-4rem)] lg:grid-cols-[1.25fr_1fr] lg:gap-12 lg:py-10">
      <div className="animate-rise">
        <p className="eyebrow flex items-center gap-2 text-content-secondary">
          <span aria-hidden="true" className="h-px w-8 bg-brand" />
          {season} season{featuredGame?.week ? ` · Week ${featuredGame.week}` : ''}
        </p>
        <h2 className="mt-4 font-display text-6xl font-extrabold uppercase leading-[0.88] text-content sm:text-7xl lg:text-[clamp(3.25rem,10.5svh,6rem)]">
          Don't just predict<br /> the game.<br />
          <span className="text-brand">Understand</span> it.
        </h2>
        <p className="mt-5 max-w-xl text-base leading-relaxed text-content-muted xl:text-lg">
          Five agents read the betting market, power ratings, team form, schedule and injuries.
          Each is weighted by how accurate it has actually been — so every pick shows which signal
          drove it.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onExplore}
            className="inline-flex h-11 items-center gap-2 rounded-md bg-brand px-6 font-display text-sm font-semibold uppercase tracking-wider text-white transition hover:opacity-90"
          >
            Explore predictions <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </button>
          <a
            href={SOURCE_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-11 items-center rounded-md border border-edge bg-surface px-6 font-display text-sm font-semibold uppercase tracking-wider text-content transition hover:bg-surface-elevated"
          >
            View source
          </a>
        </div>

        <dl className="mt-8 grid max-w-xl grid-cols-3 gap-6 border-t border-edge pt-5">
          <HeroStat label={`${HELD_OUT.season} backtest accuracy`} value={pct(HELD_OUT.accuracy)} />
          <HeroStat label={`${season} live accuracy`} value={pct(liveAccuracy)} tone="success" />
          <HeroStat label="Agents" value={AGENTS.length} />
        </dl>
        <p className="mt-3 max-w-xl text-xs leading-relaxed text-content-muted">
          These are two different measurements. {pct(HELD_OUT.accuracy)} is a walk-forward backtest
          on {HELD_OUT.season}, a season held out of the weight fitting. {season} live accuracy counts
          only picks recorded before kickoff
          {liveAccuracy == null ? ', and stays blank until the first games are scored' : ''}.
          Neither guarantees future results.
        </p>
      </div>

      {featuredGame && featuredSummary?.winner && !featuredSummary.error ? (
        <FeaturedMatchup
          game={featuredGame}
          summary={featuredSummary}
          formatTime={formatTime}
          onOpenGame={onOpenGame}
        />
      ) : (
        <div className="rounded-xl border border-edge bg-surface p-8 text-center">
          <h3 className="eyebrow text-brand-text">Featured matchup</h3>
          <p className="mt-3 text-sm text-content-muted">
            Predictions appear here once a week is loaded.
          </p>
        </div>
      )}
    </div>
  </section>
);

/**
 * The backtest, as bars from a coin flip upwards. The held-out season is the
 * red bar and leads the panel beside it: five percentages in a row invite an
 * average, and only that one was measured on a season the weights never saw.
 */
const Backtest = () => {
  const floor = 0.5;
  const ceiling = 0.72;
  return (
    <section aria-labelledby="backtest-heading">
      <SectionHead eyebrow="History" title="Historical backtest performance" id="backtest-heading">
        Walk-forward results on seasons already played. Weights were fitted on 2021–2024, so{' '}
        {HELD_OUT.season} is the only season the model hadn't seen. This is not live accuracy.
      </SectionHead>

      <div className="grid gap-3 lg:grid-cols-[2fr_1fr]">
        <div className="rounded-lg border border-edge bg-surface p-6">
          <ol
            className="flex h-64 items-end gap-4 sm:gap-8"
            aria-label={`Backtest accuracy by season: ${SEASON_ACCURACY.map((r) => `${r.season} ${pct(r.accuracy)}`).join(', ')}`}
          >
            {SEASON_ACCURACY.map((row) => {
              const heldOut = row.season === HELD_OUT.season;
              const height = ((row.accuracy - floor) / (ceiling - floor)) * 100;
              return (
                <li key={row.season} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
                  <span className={`tnum font-display text-lg font-bold ${heldOut ? 'text-brand-text' : 'text-content'}`}>
                    {pct(row.accuracy)}
                  </span>
                  <span className="flex w-full flex-1 items-end" aria-hidden="true">
                    <span
                      className={`w-full rounded-t-md ${heldOut ? 'bg-brand' : 'bg-navy ring-1 ring-inset ring-accent/40'}`}
                      style={{ height: `${height}%` }}
                    />
                  </span>
                  <span className="tnum font-display text-sm font-semibold text-content-muted">{row.season}</span>
                </li>
              );
            })}
          </ol>
          <p className="mt-4 text-xs text-content-muted">Bars start at 50% (a coin flip).</p>
        </div>

        <div className="flex flex-col rounded-lg border border-edge bg-surface p-6">
          <p className="eyebrow text-brand-text">{HELD_OUT.season} · Out of sample</p>
          <p className="tnum mt-2 font-display text-7xl font-extrabold text-content">{pct(HELD_OUT.accuracy)}</p>
          <p className="mt-3 text-sm leading-relaxed text-content-muted">
            The one unbiased estimate here — the weights never saw these games.
          </p>
          <dl className="mt-auto grid grid-cols-3 gap-3 border-t border-edge pt-5">
            {[
              ['Games', TOTAL_GAMES.toLocaleString('en-US')],
              ['Correct', TOTAL_CORRECT.toLocaleString('en-US')],
              ['In-sample', pct(OVERALL_ACCURACY)],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-content-muted">{label}</dt>
                <dd className="tnum font-display text-xl font-bold text-content">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
};

const OverviewPage = ({
  featuredGame, featuredSummary, formatTime, onExplore, onOpenGame, liveAccuracy, liveRecord, season,
}) => (
  <>
    <Hero
      featuredGame={featuredGame}
      featuredSummary={featuredSummary}
      formatTime={formatTime}
      onExplore={onExplore}
      onOpenGame={onOpenGame}
      liveAccuracy={liveAccuracy}
      season={season}
    />
    <div className="space-y-24">
      <MethodologyPipeline featuredGame={featuredGame} featuredSummary={featuredSummary} />
      {/* The record before the reconstruction: picks made before kickoff, then
          the backtest that estimates how such picks should have done. */}
      <LiveRecord record={liveRecord} season={season} />
      <Backtest />
    </div>
  </>
);

export default OverviewPage;

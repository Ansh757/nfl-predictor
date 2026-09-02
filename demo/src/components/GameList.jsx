import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { confidenceBand, teamAbbreviation, teamLogo } from '../utils/teams';

const TeamLogo = ({ team, size = 'h-8 w-8' }) => (
  <img
    src={teamLogo(team)}
    alt=""
    aria-hidden="true"
    loading="lazy"
    className={`${size} object-contain`}
    // A missing logo should not leave a broken-image icon in the card
    onError={(event) => { event.currentTarget.style.visibility = 'hidden'; }}
  />
);

const BAND_TONE = {
  success: 'bg-positive/15 text-positive',
  warning: 'bg-caution/15 text-caution',
  muted: 'bg-slate-700/40 text-slate-400'
};

const GameCard = ({ game, summary, isPredicting, isSelected, onSelect, formatTime }) => {
  const winner = summary?.winner;
  const confidence = summary?.confidence;
  const band = confidenceBand(confidence);

  return (
    <button
      type="button"
      onClick={() => onSelect(game)}
      aria-current={isSelected ? 'true' : undefined}
      className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
        isSelected
          ? 'border-accent bg-accent/10'
          : 'border-ink-700 bg-ink-800 hover:border-slate-600'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <TeamLogo team={game.away_team} />
          <span className="text-lg font-bold text-mist">{teamAbbreviation(game.away_team)}</span>
        </div>

        <span className="text-xs text-slate-500">@</span>

        <div className="flex min-w-0 items-center gap-2">
          <span className="text-lg font-bold text-mist">{teamAbbreviation(game.home_team)}</span>
          <TeamLogo team={game.home_team} />
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="truncate text-xs text-slate-400">{formatTime(game.game_date)}</span>
        {isPredicting ? (
          <span className="text-xs text-slate-500">predicting…</span>
        ) : summary?.error ? (
          <span className="text-xs text-red-400">unavailable</span>
        ) : winner ? (
          <span className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-300">
              {teamAbbreviation(winner)}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${BAND_TONE[band.tone]}`}>
              {Math.round(confidence * 100)}%
            </span>
          </span>
        ) : null}
      </div>
    </button>
  );
};

const GameList = ({
  games, paginatedGames, predictionSummaries, predictionLoading,
  selectedGameId, onSelect, formatTime, loading, gamesError, serviceWaking,
  currentPage, totalPages, rangeStart, rangeEnd, onPrev, onNext, currentWeek
}) => (
  <section className="rounded-2xl border border-ink-700 bg-ink-900 p-4">
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-sm font-bold uppercase tracking-wide text-mist">Games</h2>
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-400">
          {games.length ? `${rangeStart}-${rangeEnd} of ${games.length}` : '0'}
        </span>
        <button
          type="button" onClick={onPrev} disabled={currentPage === 1}
          aria-label="Previous page of games"
          className="rounded-lg border border-ink-700 p-1 text-slate-400 transition hover:border-slate-600 disabled:opacity-40"
        >
          <ChevronLeft aria-hidden="true" className="h-4 w-4" />
        </button>
        <button
          type="button" onClick={onNext} disabled={currentPage === totalPages || !games.length}
          aria-label="Next page of games"
          className="rounded-lg border border-ink-700 p-1 text-slate-400 transition hover:border-slate-600 disabled:opacity-40"
        >
          <ChevronRight aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>
    </div>

    <div className="mt-3 space-y-2">
      {loading && !games.length ? (
        <div role="status" className="py-8 text-center">
          <div className="text-sm text-slate-400">Loading games…</div>
          {/* A cold start can hold this for the better part of a minute; say so
              rather than leaving an unexplained spinner. */}
          {serviceWaking && (
            <div className="mx-auto mt-2 max-w-[16rem] text-xs leading-relaxed text-slate-500">
              The service is still waking up. This can take up to a minute on a
              first load.
            </div>
          )}
        </div>
      ) : gamesError ? (
        <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/5 px-4 py-6 text-center">
          <div className="text-sm font-semibold text-red-400">Could not load games</div>
          <div className="mt-1 text-xs text-slate-400">{gamesError}</div>
        </div>
      ) : !games.length ? (
        <div className="py-8 text-center text-sm text-slate-400">No games found for week {currentWeek}</div>
      ) : (
        paginatedGames.map((game) => (
          <GameCard
            key={game.game_id}
            game={game}
            summary={predictionSummaries?.[game.game_id]}
            isPredicting={predictionLoading?.[game.game_id]}
            isSelected={selectedGameId === game.game_id}
            onSelect={onSelect}
            formatTime={formatTime}
          />
        ))
      )}
    </div>
  </section>
);

export default GameList;

import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import PredictionFilters from './predictions/PredictionFilters';
import WeekNavigator from './predictions/WeekNavigator';
import MatchupCard from './predictions/MatchupCard';
import SelectedGameAnalysis from './predictions/SelectedGameAnalysis';

/**
 * The prediction workspace: filters, week navigator, matchup grid, analysis.
 *
 * Layout follows the reference: a narrow week rail on the left, a two-column
 * matchup grid taking the remaining width, and the selected game's analysis
 * across the full width below it. There is deliberately no standings panel
 * here - that would take a third of the width from the data this page exists
 * to show, and Playoffs is one click away.
 */
const PredictionsPage = ({
  filters,
  weeks, currentWeek, onWeekChange,
  games, paginatedGames, predictionSummaries, predictionLoading,
  selectedGame, onSelectGame, formatTime,
  loading, gamesError, serviceWaking,
  currentPage, totalPages, rangeStart, rangeEnd, onPrev, onNext,
  agentDefinitions,
}) => (
  <div className="space-y-3">
    <PredictionFilters {...filters} currentWeek={currentWeek} />

    <div className="grid gap-3 lg:grid-cols-[10rem_minmax(0,1fr)]">
      <div className="lg:sticky lg:top-3 lg:self-start">
        <WeekNavigator weeks={weeks} currentWeek={currentWeek} onWeekChange={onWeekChange} />
      </div>

      <section aria-label="Matchups" className="min-w-0">
        <div className="flex items-center justify-between pb-2">
          <h2 className="text-sm font-semibold text-content">
            Week {currentWeek} matchups
          </h2>
          <div className="flex items-center gap-2">
            <span className="tnum text-xs text-content-muted">
              {games.length ? `${rangeStart}-${rangeEnd} of ${games.length}` : '0 games'}
            </span>
            <button
              type="button" onClick={onPrev} disabled={currentPage === 1}
              aria-label="Previous page of games"
              className="flex h-8 w-8 items-center justify-center rounded border border-edge text-content-secondary transition hover:border-edge-strong disabled:opacity-40"
            >
              <ChevronLeft aria-hidden="true" className="h-4 w-4" />
            </button>
            <button
              type="button" onClick={onNext} disabled={currentPage === totalPages || !games.length}
              aria-label="Next page of games"
              className="flex h-8 w-8 items-center justify-center rounded border border-edge text-content-secondary transition hover:border-edge-strong disabled:opacity-40"
            >
              <ChevronRight aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        </div>

        {loading && !games.length ? (
          <div role="status" className="rounded-lg border border-edge bg-surface p-8 text-center">
            <p className="text-sm text-content-muted">Loading games…</p>
            {serviceWaking && (
              <p className="mx-auto mt-1.5 max-w-xs text-xs text-content-muted">
                The service is waking up. A first load can take up to a minute.
              </p>
            )}
          </div>
        ) : gamesError ? (
          <div role="alert" className="rounded-lg border border-danger/40 bg-surface p-8 text-center">
            <p className="text-sm font-medium text-danger">Could not load games</p>
            <p className="mt-1 text-xs text-content-muted">{gamesError}</p>
          </div>
        ) : !games.length ? (
          <div className="rounded-lg border border-edge bg-surface p-8 text-center">
            <p className="text-sm text-content-muted">No games match these filters for week {currentWeek}.</p>
          </div>
        ) : (
          <div className="grid gap-3 xl:grid-cols-2">
            {paginatedGames.map((game) => (
              <MatchupCard
                key={game.game_id}
                game={game}
                summary={predictionSummaries?.[game.game_id]}
                isPredicting={predictionLoading?.[game.game_id]}
                isSelected={selectedGame?.game_id === game.game_id}
                onSelect={onSelectGame}
                formatTime={formatTime}
              />
            ))}
          </div>
        )}
      </section>
    </div>

    <SelectedGameAnalysis
      game={selectedGame}
      summary={selectedGame ? predictionSummaries?.[selectedGame.game_id] : null}
      isPredicting={selectedGame ? predictionLoading?.[selectedGame.game_id] : false}
      agentDefinitions={agentDefinitions}
      formatTime={formatTime}
    />
  </div>
);

export default PredictionsPage;

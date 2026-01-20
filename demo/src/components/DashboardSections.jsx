import React from 'react';
import { AlertCircle, TrendingUp, Users, Moon, Sun } from 'lucide-react';

export const HeaderSection = ({
  apiUrl,
  isDarkMode,
  mutedTextClass,
  primaryTextClass,
  inputClass,
  surfaceClass,
  onToggleDarkMode,
  onRefresh,
  onApiUrlChange
}) => (
  <div className={`${surfaceClass} rounded-2xl p-6`}>
    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleDarkMode}
            className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide transition ${
              isDarkMode
                ? 'border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-500'
                : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
            }`}
            aria-label="Toggle dark mode"
          >
            {isDarkMode ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            {isDarkMode ? 'Dark' : 'Light'}
          </button>
          <span className={`text-xs font-medium ${mutedTextClass}`}>
            Live AI insights for every matchup
          </span>
        </div>
        <h1 className={`text-3xl font-bold tracking-tight ${primaryTextClass}`}>
          NFL Predictions Dashboard
        </h1>
        <p className={`${mutedTextClass}`}>
          Multi-agent consensus scores, confidence levels, and breakdowns at a glance.
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex-1">
          <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>API URL</label>
          <input
            type="text"
            value={apiUrl}
            onChange={onApiUrlChange}
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
            placeholder="API URL"
          />
        </div>
        <button
          onClick={onRefresh}
          className="h-10 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white shadow hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>
    </div>
  </div>
);

export const GamesSection = ({
  currentWeek,
  games,
  isDarkMode,
  mutedTextClass,
  primaryTextClass,
  inputClass,
  chipClass,
  formatTime,
  loading,
  paginatedGames,
  totalWeeks,
  surfaceClass,
  visibleRangeStart,
  visibleRangeEnd,
  onSelectGame,
  onWeekChange
}) => (
  <div className={`${surfaceClass} rounded-2xl p-6`}>
    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 className={`text-xl font-bold ${primaryTextClass}`}>Games</h2>
        <p className={`text-sm ${mutedTextClass}`}>
          Showing {visibleRangeStart}-{visibleRangeEnd} of {games.length || 0} matchups
        </p>
      </div>

      <div className="flex items-center gap-3">
        <div>
          <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>Week</label>
          <select
            value={currentWeek}
            onChange={onWeekChange}
            className={`mt-1 w-32 rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
          >
            {Array.from({ length: totalWeeks }, (_, index) => {
              const weekNumber = index + 1;
              return (
                <option key={weekNumber} value={weekNumber}>
                  Week {weekNumber}
                </option>
              );
            })}
          </select>
        </div>
      </div>
    </div>

    <div className="mt-5 space-y-3">
      {loading && games.length === 0 ? (
        <div className={`text-center py-8 ${mutedTextClass}`}>Loading games...</div>
      ) : games.length === 0 ? (
        <div className={`text-center py-8 ${mutedTextClass}`}>No games found for week {currentWeek}</div>
      ) : (
        paginatedGames.map((game) => (
          <div
            key={game.game_id}
            onClick={() => onSelectGame(game)}
            className={`group cursor-pointer rounded-xl border p-4 transition ${
              isDarkMode
                ? 'border-slate-800 bg-slate-950 hover:border-blue-500/60 hover:shadow-lg hover:shadow-blue-500/10'
                : 'border-slate-200 bg-white hover:border-blue-500 hover:shadow-md'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className={`font-semibold ${primaryTextClass}`}>
                {game.away_team} @ {game.home_team}
              </div>
              {game.is_dome && (
                <span className={`rounded-full px-2 py-1 text-xs font-semibold ${chipClass}`}>
                  DOME
                </span>
              )}
            </div>
            <div className={`text-sm ${mutedTextClass}`}>{formatTime(game.game_date)}</div>
            <div className={`mt-1 text-xs ${mutedTextClass}`}>{game.venue}</div>
          </div>
        ))
      )}
    </div>
  </div>
);

export const PaginationControls = ({
  currentPage,
  isDarkMode,
  mutedTextClass,
  totalPages,
  onNext,
  onPrev
}) => (
  <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <span className={`text-xs uppercase ${mutedTextClass}`}>
      Page {currentPage} of {totalPages}
    </span>
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onPrev}
        disabled={currentPage === 1}
        className={`rounded-lg border px-3 py-1 text-sm font-semibold transition ${
          currentPage === 1
            ? 'cursor-not-allowed border-transparent bg-slate-200 text-slate-400'
            : isDarkMode
            ? 'border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-500'
            : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
        }`}
      >
        Prev
      </button>
      <button
        type="button"
        onClick={onNext}
        disabled={currentPage === totalPages}
        className={`rounded-lg border px-3 py-1 text-sm font-semibold transition ${
          currentPage === totalPages
            ? 'cursor-not-allowed border-transparent bg-slate-200 text-slate-400'
            : isDarkMode
            ? 'border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-500'
            : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
        }`}
      >
        Next
      </button>
    </div>
  </div>
);

export const PredictionSection = ({
  isDarkMode,
  mutedTextClass,
  primaryTextClass,
  surfaceClass,
  formatTime,
  loading,
  getConfidenceColor,
  selectedGame
}) => (
  <div className={`${surfaceClass} rounded-2xl p-6`}>
    <h2 className={`text-xl font-bold ${primaryTextClass} mb-4`}>Prediction Analysis</h2>

    {loading && selectedGame ? (
      <div className={`text-center py-8 ${mutedTextClass}`}>Analyzing game...</div>
    ) : selectedGame?.prediction ? (
      <div className="space-y-4">
        <div className={`border-b pb-4 ${isDarkMode ? 'border-slate-800' : 'border-slate-200'}`}>
          <h3 className={`text-lg font-bold ${primaryTextClass}`}>
            {selectedGame.away_team} @ {selectedGame.home_team}
          </h3>
          <p className={`text-sm ${mutedTextClass}`}>{formatTime(selectedGame.game_date)}</p>
        </div>

        <div
          className={`rounded-xl border p-4 ${
            isDarkMode ? 'border-blue-500/40 bg-blue-500/10' : 'border-blue-200 bg-blue-50'
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className={`${isDarkMode ? 'text-blue-200' : 'text-blue-600'} h-5 w-5`} />
            <span className={`font-semibold ${isDarkMode ? 'text-blue-100' : 'text-blue-900'}`}>
              Predicted Winner
            </span>
          </div>
          <div className={`text-2xl font-bold ${isDarkMode ? 'text-blue-100' : 'text-blue-900'}`}>
            {selectedGame.prediction.winner}
          </div>
          <div
            className={`mt-2 inline-block rounded-full px-3 py-1 text-sm font-semibold ${
              getConfidenceColor(selectedGame.prediction.confidence)
            }`}
          >
            {(selectedGame.prediction.confidence * 100).toFixed(0)}% Confidence
          </div>
        </div>

        <div
          className={`rounded-xl border p-4 ${
            isDarkMode ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-white'
          }`}
        >
          <div className="flex items-center gap-2 mb-3">
            <AlertCircle className={`${mutedTextClass} h-5 w-5`} />
            <span className={`font-semibold ${primaryTextClass}`}>Analysis</span>
          </div>
          <p className={`text-sm ${mutedTextClass}`}>{selectedGame.prediction.reasoning}</p>
        </div>
      </div>
    ) : (
      <div className={`text-center py-12 ${mutedTextClass}`}>
        <Users className="w-12 h-12 mx-auto mb-3 text-slate-400" />
        <p>Select a game to view predictions</p>
      </div>
    )}
  </div>
);

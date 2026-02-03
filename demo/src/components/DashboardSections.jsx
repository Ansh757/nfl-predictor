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
  agentChipActiveClass,
  agentChipClass,
  agentDefinitions,
  currentWeek,
  currentSeason,
  games,
  getConfidenceColor,
  isDarkMode,
  mutedTextClass,
  primaryTextClass,
  inputClass,
  chipClass,
  formatTime,
  loading,
  paginatedGames,
  predictionLoading,
  predictionSummaries,
  searchQuery,
  selectedTeam,
  selectedTime,
  seasonOptions,
  sortBy,
  teamOptions,
  totalWeeks,
  surfaceClass,
  visibleRangeStart,
  visibleRangeEnd,
  onAgentChipClick,
  onSearchChange,
  onTeamChange,
  onTimeChange,
  onSortChange,
  onSelectGame,
  onSeasonChange,
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
    </div>

    <div
      className={`mt-5 rounded-xl border border-dashed p-4 ${
        isDarkMode ? 'border-slate-800' : 'border-slate-200/70'
      }`}
    >
      <div className="grid gap-4 lg:grid-cols-[1.4fr_2fr]">
        <div>
          <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>Search</label>
          <input
            type="text"
            value={searchQuery}
            onChange={onSearchChange}
            placeholder="Search team or opponent"
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>Team</label>
            <select
              value={selectedTeam}
              onChange={onTeamChange}
              className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
            >
              <option value="all">All teams</option>
              {teamOptions.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>Season</label>
            <select
              value={currentSeason}
              onChange={onSeasonChange}
              className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
            >
              {seasonOptions.map((season) => (
                <option key={season} value={season}>
                  {season}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>Week</label>
            <select
              value={currentWeek}
              onChange={onWeekChange}
              className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
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
          <div>
            <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>Time</label>
            <select
              value={selectedTime}
              onChange={onTimeChange}
              className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
            >
              <option value="all">All times</option>
              <option value="morning">Morning</option>
              <option value="afternoon">Afternoon</option>
              <option value="evening">Evening</option>
            </select>
          </div>
          <div>
            <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>Sort by</label>
            <select
              value={sortBy}
              onChange={onSortChange}
              className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
            >
              <option value="week-asc">Week (asc)</option>
              <option value="week-desc">Week (desc)</option>
              <option value="team">Team games (A–Z)</option>
              <option value="matchup">Matchup (A–Z)</option>
              <option value="confidence">Confidence (high → low)</option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <div className="mt-5 space-y-3">
      {loading && games.length === 0 ? (
        <div className={`text-center py-8 ${mutedTextClass}`}>Loading games...</div>
      ) : games.length === 0 ? (
        <div className={`text-center py-8 ${mutedTextClass}`}>No games found for week {currentWeek}</div>
      ) : (
        paginatedGames.map((game) => {
          const summary = predictionSummaries?.[game.game_id];
          const isPredicting = predictionLoading?.[game.game_id];
          const confidenceValue = summary?.confidence ?? 0;
          const confidencePercent = summary ? Math.round(confidenceValue * 100) : null;
          const consensusLabel = summary?.consensus?.label ?? '0/4 agents';
          const predictedWinner = summary?.winner ?? 'Awaiting pick';
          return (
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
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className={`text-[11px] uppercase ${mutedTextClass}`}>Predicted winner</div>
                  <div className={`font-semibold ${primaryTextClass}`}>
                    {isPredicting ? 'Predicting...' : predictedWinner}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <div
                    className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold ${
                      summary ? getConfidenceColor(confidenceValue) : `${chipClass}`
                    }`}
                  >
                    {isPredicting ? (
                      <span className="flex items-center gap-2">
                        <span
                          className={`h-2 w-2 animate-pulse rounded-full ${
                            isDarkMode ? 'bg-blue-400' : 'bg-blue-500'
                          }`}
                        />
                        Predicting
                      </span>
                    ) : (
                      `${confidencePercent !== null ? `${confidencePercent}%` : '—'} Confidence`
                    )}
                  </div>
                  <div
                    className={`h-1.5 w-20 rounded-full ${
                      isDarkMode ? 'bg-slate-800' : 'bg-slate-200'
                    }`}
                  >
                    <div
                      className={`h-1.5 rounded-full ${isDarkMode ? 'bg-blue-400' : 'bg-blue-500'}`}
                      style={{ width: `${confidencePercent ?? 0}%` }}
                    />
                  </div>
                </div>
                <div className="min-w-[120px] text-right">
                  <div className={`text-[11px] uppercase ${mutedTextClass}`}>Consensus</div>
                  <div className={`text-sm font-semibold ${primaryTextClass}`}>
                    {isPredicting ? '—' : consensusLabel}
                  </div>
                </div>
              </div>

              <div className={`mt-3 text-sm ${mutedTextClass}`}>{formatTime(game.game_date)}</div>
              <div className={`mt-1 text-xs ${mutedTextClass}`}>{game.venue}</div>

              <div className="mt-3 flex flex-wrap gap-2">
                {agentDefinitions.map((agent) => {
                  const AgentIcon = agent.icon;
                  const isAligned = summary?.agentInsights?.[agent.key]?.isAligned;
                  return (
                    <button
                      key={agent.key}
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onAgentChipClick(agent.key);
                      }}
                      className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold transition ${
                        isAligned ? agentChipActiveClass : agentChipClass
                      }`}
                    >
                      <AgentIcon className="h-3.5 w-3.5" />
                      {agent.label}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })
      )}
    </div>
  </div>
);

export const PlayoffControls = ({
  inputClass,
  isDarkMode,
  mutedTextClass,
  primaryTextClass,
  roundOptions,
  seasonOptions,
  selectedRound,
  selectedSeason,
  playoffViewMode,
  simulationCount,
  simulationLoading,
  simulationError,
  surfaceClass,
  onRoundChange,
  onSeasonChange,
  onViewModeChange,
  onRunSimulation
}) => {
  const activeToggleClass = isDarkMode
    ? 'border-blue-400/60 bg-blue-500/20 text-blue-100'
    : 'border-blue-200 bg-blue-50 text-blue-700';
  const inactiveToggleClass = isDarkMode
    ? 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500'
    : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400';

  return (
    <div className={`${surfaceClass} rounded-2xl p-6`}>
      <div>
        <h2 className={`text-xl font-bold ${primaryTextClass}`}>Playoff Controls</h2>
        <p className={`text-sm ${mutedTextClass}`}>
          Tune the playoff slate by season, round, and viewing mode.
        </p>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div>
          <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>Season</label>
          <select
            value={selectedSeason}
            onChange={onSeasonChange}
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
          >
            {seasonOptions.map((season) => (
              <option key={season} value={season}>
                {season}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>Round</label>
          <select
            value={selectedRound}
            onChange={onRoundChange}
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none transition ${inputClass}`}
          >
            {roundOptions.map((round) => (
              <option key={round} value={round}>
                {round}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={`text-xs font-semibold uppercase ${mutedTextClass}`}>View mode</label>
          <div className="mt-1 flex rounded-lg border p-1 gap-2">
            <button
              type="button"
              onClick={() => onViewModeChange('single')}
              className={`flex-1 rounded-md border px-3 py-2 text-sm font-semibold transition ${
                playoffViewMode === 'single' ? activeToggleClass : inactiveToggleClass
              }`}
            >
              Single game
            </button>
            <button
              type="button"
              onClick={() => onViewModeChange('bracket')}
              className={`flex-1 rounded-md border px-3 py-2 text-sm font-semibold transition ${
                playoffViewMode === 'bracket' ? activeToggleClass : inactiveToggleClass
              }`}
            >
              Full bracket
            </button>
          </div>
        </div>
      </div>
      {playoffViewMode === 'bracket' && (
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className={`text-xs font-semibold uppercase ${mutedTextClass}`}>
            {simulationCount} simulations
          </div>
          <button
            type="button"
            onClick={onRunSimulation}
            disabled={simulationLoading}
            className={`rounded-lg px-4 py-2 text-sm font-semibold text-white shadow transition ${
              simulationLoading ? 'bg-slate-400' : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {simulationLoading ? 'Running simulation...' : 'Run simulation'}
          </button>
          {simulationError && (
            <div className={`text-xs font-semibold ${mutedTextClass}`}>{simulationError}</div>
          )}
        </div>
      )}
    </div>
  );
};

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
  agentDefinitions,
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
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <div
              className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${
                getConfidenceColor(selectedGame.prediction.confidence)
              }`}
            >
              {(selectedGame.prediction.confidence * 100).toFixed(0)}% Confidence
            </div>
            <div className={`text-xs font-semibold ${mutedTextClass}`}>
              Consensus:{' '}
              <span className={primaryTextClass}>
                {selectedGame.prediction.consensus?.label ?? '0/4 agents'}
              </span>
            </div>
          </div>
          <div
            className={`mt-3 h-1.5 w-full rounded-full ${
              isDarkMode ? 'bg-slate-800' : 'bg-blue-100'
            }`}
          >
            <div
              className={`${isDarkMode ? 'bg-blue-300' : 'bg-blue-500'} h-1.5 rounded-full`}
              style={{ width: `${(selectedGame.prediction.confidence * 100).toFixed(0)}%` }}
            />
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

        {agentDefinitions.map((agent) => {
          const AgentIcon = agent.icon;
          const insight = selectedGame.prediction.agentInsights?.[agent.key];
          return (
            <section
              key={agent.key}
              id={`agent-${agent.key}`}
              className={`scroll-mt-24 rounded-xl border p-4 ${
                isDarkMode ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-white'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <AgentIcon className={`h-5 w-5 ${mutedTextClass}`} />
                  <div>
                    <div className={`font-semibold ${primaryTextClass}`}>{agent.label} Agent</div>
                    <div className={`text-xs ${mutedTextClass}`}>{agent.description}</div>
                  </div>
                </div>
                {insight?.confidence !== undefined ? (
                  <div
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      getConfidenceColor(insight.confidence)
                    }`}
                  >
                    {(insight.confidence * 100).toFixed(0)}% Confidence
                  </div>
                ) : (
                  <div className={`rounded-full px-3 py-1 text-xs font-semibold ${mutedTextClass}`}>
                    Awaiting data
                  </div>
                )}
              </div>
              <div className="mt-3 space-y-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`text-xs uppercase ${mutedTextClass}`}>Lean</span>
                  <span className={`font-semibold ${primaryTextClass}`}>
                    {insight?.predictedWinner ?? 'No pick yet'}
                  </span>
                  {insight?.isAligned && (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                        isDarkMode ? 'bg-blue-500/20 text-blue-100' : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      Influential
                    </span>
                  )}
                </div>
                <p className={mutedTextClass}>
                  {insight?.reasoning ?? 'Agent insights will appear once the prediction is run.'}
                </p>
              </div>
            </section>
          );
        })}
      </div>
    ) : (
      <div className={`text-center py-12 ${mutedTextClass}`}>
        <Users className="w-12 h-12 mx-auto mb-3 text-slate-400" />
        <p>Select a game to view predictions</p>
      </div>
    )}
  </div>
);

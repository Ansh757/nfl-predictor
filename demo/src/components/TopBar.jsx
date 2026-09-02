import React from 'react';
import { RefreshCw, Settings, Sun, Moon } from 'lucide-react';

/**
 * Application chrome: identity, season, connection state and global actions.
 */
/**
 * Connection state has three readings, not two. "Waking" is the one that
 * matters on a free-tier deploy: the container is stopped, the request is in
 * flight, and showing that as "API Unreachable" told the user the site was
 * broken when it was merely asleep.
 */
const connectionState = (apiConnected, serviceWaking) => {
  if (serviceWaking) return { dot: 'bg-caution animate-pulse', label: 'Waking service' };
  if (apiConnected === null) return { dot: 'bg-slate-500', label: 'Checking API' };
  if (apiConnected) return { dot: 'bg-positive', label: 'API Connected' };
  return { dot: 'bg-red-500', label: 'API Unreachable' };
};

const TopBar = ({
  seasonOptions,
  currentSeason,
  onSeasonChange,
  apiConnected,
  serviceWaking,
  onRefresh,
  refreshing,
  isDarkMode,
  onToggleDarkMode
}) => {
  const connection = connectionState(apiConnected, serviceWaking);

  return (
  <header className="flex flex-wrap items-center justify-between gap-4 border-b border-ink-700 bg-ink-900 px-6 py-4">
    <div className="flex items-center gap-3">
      <span className="text-2xl" aria-hidden="true">🏈</span>
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-base font-bold tracking-wide text-mist">NFL PREDICTOR</h1>
          {/* Beta, and said out loud: the model is measured but unproven on a
              live season, and the deploy is still a single free-tier service. */}
          <span className="rounded-full border border-caution/40 bg-caution/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-caution">
            Beta
          </span>
        </div>
        <p className="text-xs text-slate-400">Multi-agent predictions, weighted by measured accuracy</p>
      </div>
    </div>

    <div className="flex flex-wrap items-center gap-3">
      <label htmlFor="topbar-season" className="sr-only">Season</label>
      <select
        id="topbar-season"
        value={currentSeason}
        onChange={onSeasonChange}
        className="rounded-xl border border-ink-700 bg-ink-800 px-4 py-2 text-sm font-semibold text-mist outline-none transition hover:border-slate-600"
      >
        {seasonOptions.map((season) => (
          <option key={season} value={season}>{season} Season</option>
        ))}
      </select>

      <span
        className="flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-800 px-4 py-2 text-sm"
        role="status"
      >
        <span aria-hidden="true" className={`h-2 w-2 rounded-full ${connection.dot}`} />
        <span className="text-slate-300">{connection.label}</span>
      </span>

      <button
        type="button"
        onClick={onRefresh}
        disabled={refreshing}
        className="flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-800 px-4 py-2 text-sm font-semibold text-mist transition hover:border-slate-600 disabled:opacity-50"
      >
        <RefreshCw aria-hidden="true" className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
        Refresh
      </button>

      <button
        type="button"
        onClick={onToggleDarkMode}
        aria-label={isDarkMode ? 'Switch to light theme' : 'Switch to dark theme'}
        className="rounded-xl border border-ink-700 bg-ink-800 p-2 text-mist transition hover:border-slate-600"
      >
        {isDarkMode
          ? <Sun aria-hidden="true" className="h-4 w-4" />
          : <Moon aria-hidden="true" className="h-4 w-4" />}
      </button>

      <button
        type="button"
        aria-label="Settings"
        className="rounded-xl border border-ink-700 bg-ink-800 p-2 text-slate-400 transition hover:border-slate-600"
      >
        <Settings aria-hidden="true" className="h-4 w-4" />
      </button>
    </div>
  </header>
  );
};

export default TopBar;

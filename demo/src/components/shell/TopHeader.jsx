import React from 'react';
import { RefreshCw, Sun, Moon } from 'lucide-react';
import PrimaryNavigation from './PrimaryNavigation';

/**
 * Application chrome, in one compact row.
 *
 * The previous header stacked a wordmark block above a permanent left sidebar,
 * which cost a fixed 14rem of width on every screen for three links. Navigation
 * moved up here so the prediction workspace gets that width back; on mobile it
 * drops to a bottom bar - see PrimaryNavigation.
 */
const connectionState = (apiConnected, serviceWaking) => {
  if (serviceWaking) return { dot: 'bg-warning', label: 'Waking service' };
  if (apiConnected === null) return { dot: 'bg-content-muted', label: 'Checking API' };
  if (apiConnected) return { dot: 'bg-success', label: 'API connected' };
  return { dot: 'bg-danger', label: 'API unreachable' };
};

const TopHeader = ({
  activeView,
  onViewChange,
  seasonOptions,
  currentSeason,
  onSeasonChange,
  apiConnected,
  serviceWaking,
  onRefresh,
  refreshing,
  theme,
  onToggleTheme,
}) => {
  const connection = connectionState(apiConnected, serviceWaking);
  const isDark = theme === 'dark';

  return (
    <header className="border-b border-edge bg-surface">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-[15px] font-semibold tracking-tight text-content">
                NFL Predictor
              </h1>
              <span className="rounded border border-accent/40 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-accent">
                Beta
              </span>
            </div>
            <p className="truncate text-xs text-content-muted">
              Multi-agent predictions weighted by measured accuracy
            </p>
          </div>
        </div>

        {/* Desktop navigation sits in the header; the mobile bar is rendered
            separately at the document level so it can be fixed to the bottom. */}
        <PrimaryNavigation
          activeView={activeView}
          onViewChange={onViewChange}
          className="order-last hidden w-full lg:order-none lg:ml-4 lg:block lg:w-auto"
        />

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <label htmlFor="season" className="sr-only">Season</label>
          <select
            id="season"
            value={currentSeason}
            onChange={onSeasonChange}
            className="tnum h-9 rounded border border-edge bg-surface-elevated px-2 text-sm text-content outline-none transition hover:border-edge-strong"
          >
            {seasonOptions.map((season) => (
              <option key={season} value={season}>{season}</option>
            ))}
          </select>

          {/* Status is text as well as colour - a dot alone says nothing to
              anyone who cannot distinguish the hues, or to a screen reader. */}
          <span
            role="status"
            className="flex h-9 items-center gap-2 rounded border border-edge px-2.5 text-xs text-content-secondary"
          >
            <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${connection.dot}`} />
            <span className="hidden sm:inline">{connection.label}</span>
          </span>

          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="flex h-9 min-w-[44px] items-center gap-1.5 rounded border border-edge px-2.5 text-sm text-content-secondary transition hover:border-edge-strong hover:text-content disabled:opacity-50"
          >
            <RefreshCw aria-hidden="true" className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
            aria-pressed={!isDark}
            className="flex h-9 w-9 items-center justify-center rounded border border-edge text-content-secondary transition hover:border-edge-strong hover:text-content"
          >
            {isDark
              ? <Sun aria-hidden="true" className="h-4 w-4" />
              : <Moon aria-hidden="true" className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </header>
  );
};

export default TopHeader;

import React from 'react';
import { GitBranch, RefreshCw, Sun, Moon } from 'lucide-react';
import PrimaryNavigation from './PrimaryNavigation';

export const SOURCE_URL = 'https://github.com/Ansh757/nfl-predictor';

/**
 * Application chrome, in one compact row under the brand stripe.
 *
 * Navigation sits here on desktop and drops to a bottom bar on mobile - see
 * PrimaryNavigation. The live-accuracy pill is the one number in the chrome,
 * because it is the one that changes week to week; the season control lives on
 * the page it scopes rather than up here.
 *
 * No API-health indicator. A green dot reading "API connected" is operator
 * furniture; the dot here sits beside a measurement, with the words for it.
 */
const TopHeader = ({
  activeView,
  onViewChange,
  liveAccuracy,
  season,
  onRefresh,
  refreshing,
  theme,
  onToggleTheme,
}) => {
  const isDark = theme === 'dark';

  return (
    <header className="sticky top-0 z-40 border-b border-edge bg-background">
      <div aria-hidden="true" className="stripe h-0.5 w-full" />
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
        <button
          type="button"
          onClick={() => onViewChange('overview')}
          className="flex items-center gap-2.5"
          aria-label="NFL Predictor home"
        >
          <span aria-hidden="true" className="grid h-8 w-8 place-items-center rounded-md bg-navy font-display text-sm font-bold text-white ring-1 ring-edge">
            P
          </span>
          <h1 className="font-display text-lg font-bold uppercase tracking-wider text-content">
            NFL <span className="text-brand-text">Predictor</span>
          </h1>
        </button>

        <PrimaryNavigation
          activeView={activeView}
          onViewChange={onViewChange}
          className="hidden lg:block"
        />

        <div className="ml-auto flex items-center gap-2">
          <div className="hidden items-center gap-2 rounded-full border border-edge bg-surface px-3 py-1.5 md:flex">
            <span aria-hidden="true" className="h-2 w-2 rounded-full bg-success" />
            <span className="text-xs text-content-muted">{season} live</span>
            <span className="tnum font-display text-sm font-bold text-content">
              {liveAccuracy == null ? '—' : `${(liveAccuracy * 100).toFixed(1)}%`}
            </span>
          </div>

          {/* Refresh stays, because nothing polls - the data changes only when
              something asks for it. */}
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            aria-label="Refresh data"
            title="Refresh data"
            className="grid h-9 w-9 place-items-center rounded-md border border-edge text-content-muted transition hover:text-content disabled:opacity-50"
          >
            <RefreshCw aria-hidden="true" className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>

          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
            aria-pressed={!isDark}
            className="grid h-9 w-9 place-items-center rounded-md border border-edge text-content-muted transition hover:text-content"
          >
            {isDark
              ? <Sun aria-hidden="true" className="h-4 w-4" />
              : <Moon aria-hidden="true" className="h-4 w-4" />}
          </button>

          <a
            href={SOURCE_URL}
            target="_blank"
            rel="noreferrer"
            aria-label="Source code on GitHub"
            className="grid h-9 w-9 place-items-center rounded-md border border-edge text-content-muted transition hover:text-content"
          >
            <GitBranch aria-hidden="true" className="h-4 w-4" />
          </a>
        </div>
      </div>
    </header>
  );
};

export default TopHeader;

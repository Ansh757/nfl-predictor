import React from 'react';

/**
 * Weeks 1-18.
 *
 * A vertical list on desktop, where there is room and the whole season should
 * be visible at once; a native select below that, because eighteen 44px targets
 * in a column is most of a phone screen.
 *
 * Only one week control is rendered per breakpoint - the filter bar drops its
 * own Week field on desktop for the same reason. Two controls setting the same
 * state is how they end up disagreeing.
 */
const WeekNavigator = ({ weeks, currentWeek, onWeekChange }) => (
  <>
    <nav aria-label="Week navigation" className="hidden lg:block">
      <h2 className="px-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-content-muted">
        Weeks
      </h2>
      <ul className="max-h-[26rem] space-y-0.5 overflow-y-auto pr-1 2xl:max-h-none">
        {weeks.map((week) => {
          const active = week === currentWeek;
          return (
            <li key={week}>
              <button
                type="button"
                onClick={() => onWeekChange(week)}
                aria-current={active ? 'true' : undefined}
                className={`tnum flex w-full items-center justify-between rounded px-3 py-2 text-sm transition ${
                  active
                    ? 'bg-surface-selected font-semibold text-content'
                    : 'text-content-secondary hover:bg-surface-elevated hover:text-content'
                }`}
              >
                <span>Week {week}</span>
                {active && <span aria-hidden="true" className="h-4 w-0.5 rounded-full bg-accent" />}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>

    <div className="lg:hidden">
      <label htmlFor="week-mobile" className="block pb-1 text-[11px] font-semibold uppercase tracking-wide text-content-muted">
        Week
      </label>
      <select
        id="week-mobile"
        value={currentWeek}
        onChange={(event) => onWeekChange(Number(event.target.value))}
        className="tnum h-11 w-full rounded border border-edge bg-surface-elevated px-3 text-sm text-content outline-none"
      >
        {weeks.map((week) => (
          <option key={week} value={week}>Week {week}</option>
        ))}
      </select>
    </div>
  </>
);

export default WeekNavigator;

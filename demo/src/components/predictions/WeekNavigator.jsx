import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

/**
 * One week at a time, in a bar rather than a column.
 *
 * This was a vertical list of every week down the left of the page. At 18 weeks
 * that is a full column of the viewport spent on a control whose answer is
 * almost always "the current week" or "one either side of it" - and the column
 * it occupied came out of the matchup cards, which are what the page is for.
 *
 * So: step buttons for the common case, the week and its dates in the middle,
 * and a select for the jump. The select is the whole season in one control that
 * costs one line instead of eighteen.
 *
 * There is no longer a desktop control and a separate mobile one. The old pair
 * existed because eighteen 44px targets do not fit on a phone, and the rule
 * that came out of it - one week control per breakpoint - was really a rule
 * about two controls sharing the accessible name "Week". These three have
 * distinct names and distinct jobs (step, step, jump), which is ordinary
 * pagination, so one set now serves every width.
 */
const Step = ({ label, icon: Icon, onClick, disabled, side }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    aria-label={label}
    className="flex h-9 items-center gap-1 rounded border border-edge px-2.5 text-xs font-medium text-content-secondary transition hover:border-edge-strong hover:text-content disabled:opacity-40 disabled:hover:border-edge disabled:hover:text-content-secondary sm:px-3"
  >
    {side === 'left' && <Icon aria-hidden="true" className="h-4 w-4" />}
    {/* The word is for pointer users with room; the button always has its
        aria-label, so nothing is lost when it is hidden. */}
    <span className="hidden sm:inline">{side === 'left' ? 'Previous' : 'Next'}</span>
    {side === 'right' && <Icon aria-hidden="true" className="h-4 w-4" />}
  </button>
);

const WeekNavigator = ({ weeks, currentWeek, weekRange, onWeekChange }) => {
  const first = weeks[0];
  const last = weeks[weeks.length - 1];

  return (
    <nav
      aria-label="Week navigation"
      className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-lg border border-edge bg-surface px-3 py-2"
    >
      <div className="flex flex-1 items-center justify-between gap-3 sm:flex-none sm:justify-start">
        <Step
          label="Previous week" icon={ChevronLeft} side="left"
          onClick={() => onWeekChange(currentWeek - 1)}
          disabled={currentWeek <= first}
        />

        <div className="text-center sm:min-w-[8rem]">
          <div className="tnum text-sm font-semibold leading-tight text-content">
            Week {currentWeek}
          </div>
          {/* Dates for the week, not for the filtered subset - filtering to one
              team must not make week 1 look like a single day. */}
          <div className="tnum text-[11px] leading-tight text-content-muted">
            {weekRange || ' '}
          </div>
        </div>

        <Step
          label="Next week" icon={ChevronRight} side="right"
          onClick={() => onWeekChange(currentWeek + 1)}
          disabled={currentWeek >= last}
        />
      </div>

      <div className="flex items-center gap-2">
        <label
          htmlFor="week-jump"
          className="text-[11px] font-medium uppercase tracking-wide text-content-muted"
        >
          Jump to week
        </label>
        <select
          id="week-jump"
          value={currentWeek}
          onChange={(event) => onWeekChange(Number(event.target.value))}
          className="tnum h-9 rounded border border-edge bg-surface-elevated px-2 text-sm text-content outline-none"
        >
          {weeks.map((week) => (
            <option key={week} value={week}>Week {week}</option>
          ))}
        </select>
      </div>
    </nav>
  );
};

export default WeekNavigator;

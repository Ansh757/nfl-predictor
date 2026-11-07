import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

/**
 * Every week of the season in one strip, each carrying how the model did.
 *
 * The rule under each number is the live record for that week: green when the
 * recorded picks beat a coin flip, red when they did not, grey while the week
 * is still to play, nothing when no pick was recorded. It is a summary, so the
 * week's button names it in words too.
 *
 * Previous / Next sit at the ends because on a phone the strip scrolls and the
 * week either side is the common case. The strip and the steps have distinct
 * names - "Week 7", "Previous week" - so nothing here answers to a bare "Week",
 * which is the duplicate-name failure the old pair of week controls had.
 */
const resultOf = (summary) => {
  if (!summary) return { rule: 'bg-transparent', words: 'no picks recorded' };
  if (summary.accuracy == null) return { rule: 'bg-content/30', words: 'not played yet' };
  const words = `${summary.correct} of ${summary.scored} correct`;
  return { rule: summary.accuracy >= 0.5 ? 'bg-success' : 'bg-danger', words };
};

const Step = ({ label, icon: Icon, onClick, disabled }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    aria-label={label}
    className="grid h-[3.75rem] w-8 flex-shrink-0 place-items-center rounded-lg border border-edge bg-surface text-content-muted transition hover:text-content disabled:opacity-40"
  >
    <Icon aria-hidden="true" className="h-4 w-4" />
  </button>
);

const WeekNavigator = ({ weeks, currentWeek, onWeekChange, weekResults = {} }) => {
  const first = weeks[0];
  const last = weeks[weeks.length - 1];

  return (
    <nav aria-label="Week navigation" className="flex items-center gap-1.5">
      <Step label="Previous week" icon={ChevronLeft}
        onClick={() => onWeekChange(currentWeek - 1)} disabled={currentWeek <= first} />
      <div className="-mx-1 flex-1 overflow-x-auto px-1 pb-1">
        <ul className="flex min-w-max gap-1.5">
          {weeks.map((week) => {
            const active = week === currentWeek;
            const { rule, words } = resultOf(weekResults[week]);
            return (
              <li key={week}>
                <button
                  type="button"
                  onClick={() => onWeekChange(week)}
                  aria-current={active ? 'true' : undefined}
                  aria-label={`Week ${week}, ${words}`}
                  className={`flex w-14 flex-col items-center rounded-lg border px-2 py-2 transition ${
                    active
                      ? 'border-accent bg-accent/15 text-content'
                      : 'border-edge bg-surface text-content-muted hover:border-edge-strong hover:text-content'
                  }`}
                >
                  <span aria-hidden="true" className="text-[10px] font-semibold uppercase tracking-widest">Wk</span>
                  <span aria-hidden="true" className="tnum font-display text-xl font-bold leading-none">{week}</span>
                  <span aria-hidden="true" className={`mt-1 h-1 w-6 rounded-full ${rule}`} />
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      <Step label="Next week" icon={ChevronRight}
        onClick={() => onWeekChange(currentWeek + 1)} disabled={currentWeek >= last} />
    </nav>
  );
};

export default WeekNavigator;

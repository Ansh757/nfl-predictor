import React from 'react';

const Field = ({ id, label, children }) => (
  <div className="min-w-0">
    <label htmlFor={id} className="block pb-1 text-[11px] font-semibold uppercase tracking-wide text-content-muted">
      {label}
    </label>
    {children}
  </div>
);

const control =
  'h-9 w-full rounded border border-edge bg-surface-elevated px-2.5 text-sm text-content outline-none transition hover:border-edge-strong focus:border-accent';

/**
 * Search, Team, Kickoff and Sort.
 *
 * Week is deliberately absent. WeekNavigator owns week selection and already
 * renders both presentations - a list above `lg`, a native select below it - so
 * exactly one week control is visible at every breakpoint. Keeping a Week field
 * here as well would put two controls on one piece of state, and because
 * Tailwind's `lg:hidden` only hides visually, both would sit in the accessibility
 * tree at once under the same label.
 */
const PredictionFilters = ({
  searchQuery, onSearchChange,
  selectedTeam, onTeamChange, teamOptions,
  selectedTime, onTimeChange,
  sortBy, onSortChange,
}) => (
  <section className="rounded-lg border border-edge bg-surface p-3">
    <h2 className="sr-only">Filter predictions</h2>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div className="sm:col-span-2 lg:col-span-1">
        <Field id="game-search" label="Search">
          <input
            id="game-search"
            type="text"
            value={searchQuery}
            onChange={onSearchChange}
            placeholder="Team or matchup"
            className={`${control} placeholder:text-content-muted`}
          />
        </Field>
      </div>

      <Field id="filter-team" label="Team">
        <select id="filter-team" value={selectedTeam} onChange={onTeamChange} className={control}>
          <option value="all">All teams</option>
          {teamOptions.map((team) => <option key={team} value={team}>{team}</option>)}
        </select>
      </Field>

      <Field id="filter-time" label="Kickoff">
        <select id="filter-time" value={selectedTime} onChange={onTimeChange} className={control}>
          <option value="all">All times</option>
          <option value="morning">Morning</option>
          <option value="afternoon">Afternoon</option>
          <option value="evening">Evening</option>
        </select>
      </Field>

      <Field id="filter-sort" label="Sort">
        <select id="filter-sort" value={sortBy} onChange={onSortChange} className={control}>
          <option value="week-asc">Kickoff (earliest)</option>
          <option value="week-desc">Kickoff (latest)</option>
          <option value="team">Team (A-Z)</option>
          <option value="matchup">Matchup (A-Z)</option>
          <option value="confidence">Confidence (high to low)</option>
        </select>
      </Field>
    </div>
  </section>
);

export default PredictionFilters;

import React from 'react';
import { Check, ChevronRight, Clock, Minus, X } from 'lucide-react';
import { SectionHead, StatTile, TeamLogo } from '../shell/PageIntro';
import { teamAbbreviation } from '../../utils/teams';
import { OUTCOME_LABEL, outcomeOf, summarizeByWeek, totals } from '../../utils/liveRecord';

/**
 * Every official pick this season, as it was recorded before kickoff.
 *
 * The backtest section below this is a reconstruction; this is the record. It
 * gets its own section rather than a tab because the application has three
 * sections and this belongs with the other measurement on the Overview.
 *
 * Weeks are <details> elements: one line of tally per week, the games behind it
 * a click away, keyboard and screen-reader correct with no JavaScript.
 */

const pct = (value) => (value == null ? '—' : `${(value * 100).toFixed(1)}%`);

/* A word first and a colour second - the badge says "Model correct". */
const OUTCOME_STYLE = {
  correct: { cls: 'border-success/30 bg-success/15 text-success', Icon: Check },
  wrong: { cls: 'border-danger/30 bg-danger/15 text-danger', Icon: X },
  tie: { cls: 'border-warning/30 bg-warning/15 text-warning', Icon: Minus },
  pending: { cls: 'border-edge bg-surface-elevated text-content-muted', Icon: Clock },
};

export const OutcomeBadge = ({ outcome }) => {
  const { cls, Icon } = OUTCOME_STYLE[outcome];
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 font-display text-xs font-semibold uppercase tracking-wider ${cls}`}>
      <Icon aria-hidden="true" className="h-3 w-3" />
      {OUTCOME_LABEL[outcome]}
    </span>
  );
};

const GameRow = ({ prediction }) => (
  <li className="flex items-center gap-3 rounded-lg border border-edge bg-background px-3 py-2">
    <span className="tnum w-24 font-display text-sm font-semibold text-content">
      {teamAbbreviation(prediction.away_team)} @ {teamAbbreviation(prediction.home_team)}
    </span>
    <span className="tnum flex flex-1 items-center gap-1.5 text-sm text-content-muted">
      <TeamLogo team={prediction.predicted_winner} size={18} />
      Picked <span className="font-medium text-content">{teamAbbreviation(prediction.predicted_winner)}</span>
      {' '}{pct(prediction.confidence)}
    </span>
    <OutcomeBadge outcome={outcomeOf(prediction)} />
  </li>
);

/**
 * Accuracy by week, oldest first. The dashed line is a coin flip; a week under
 * it is the red bar. The figure above each bar is the measurement, so the
 * colour only reinforces it.
 */
const WeeklyChart = ({ weeks }) => {
  const chronological = [...weeks].reverse();
  return (
    <div className="flex flex-col rounded-lg border border-edge bg-surface p-6">
      <div className="flex items-center justify-between">
        <h3 className="eyebrow text-content-muted">Accuracy by week</h3>
        <p className="text-xs text-content-muted">Dashed line = coin flip</p>
      </div>
      <ol className="relative mt-6 flex min-h-56 flex-1 items-end gap-2 sm:gap-3">
        <span aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-1/2 border-t border-dashed border-content/25" />
        {chronological.map((week) => (
          <li
            key={week.week}
            className="flex h-full flex-1 flex-col items-center justify-end gap-2"
            aria-label={`Week ${week.week}: ${week.accuracy == null ? 'not scored yet' : pct(week.accuracy)}`}
          >
            <span aria-hidden="true" className="tnum font-display text-xs font-semibold text-content-muted">
              {week.accuracy == null ? '—' : Math.round(week.accuracy * 100)}
            </span>
            <span aria-hidden="true" className="flex w-full flex-1 items-end">
              <span
                className={`w-full rounded-t-md ${
                  week.accuracy == null ? 'h-1 bg-surface-elevated'
                    : week.accuracy >= 0.5 ? 'bg-accent' : 'bg-brand'
                }`}
                style={week.accuracy == null ? undefined : { height: `${week.accuracy * 100}%` }}
              />
            </span>
            <span aria-hidden="true" className="font-display text-xs font-semibold text-content-muted">W{week.week}</span>
          </li>
        ))}
      </ol>
    </div>
  );
};

const LiveRecord = ({ record, season }) => {
  if (record == null) return null;

  const weeks = record.status === 'ok' ? summarizeByWeek(record.data?.predictions) : [];
  const all = totals(weeks);

  return (
    <section aria-labelledby="live-record-heading">
      <SectionHead eyebrow="Accountability" title={`${season} live record`} id="live-record-heading">
        Every pick is recorded before kickoff and never changed. Ties aren't scored; unplayed games
        count for nothing.
      </SectionHead>

      {record.status !== 'ok' ? (
        <p className="rounded-lg border border-edge bg-surface p-6 text-sm text-content-muted">
          The live record could not be loaded.
        </p>
      ) : weeks.length === 0 ? (
        <p className="rounded-lg border border-edge bg-surface p-6 text-sm text-content-muted">
          No picks recorded for {season} yet.
        </p>
      ) : (
        <>
          <div className="grid gap-3 lg:grid-cols-[1fr_2fr]">
            <dl className="grid grid-cols-3 gap-3 lg:grid-cols-1">
              <StatTile label="Correct" value={all.correct} sub={`of ${all.scored} scored`} size="lg" />
              <StatTile label="Accuracy" value={pct(all.accuracy)} tone="success" size="lg" />
              <StatTile
                label="Not played yet"
                value={all.pending}
                sub={all.ties ? `${all.ties} tie${all.ties > 1 ? 's' : ''}` : undefined}
                size="lg"
              />
            </dl>
            <WeeklyChart weeks={weeks} />
          </div>

          <ul className="mt-3 divide-y divide-edge rounded-lg border border-edge bg-surface px-2">
            {weeks.map((week) => (
              <li key={week.week}>
                <details className="group px-4">
                  <summary className="flex cursor-pointer list-none items-center gap-4 py-4">
                    <ChevronRight aria-hidden="true" className="h-4 w-4 text-content-muted transition-transform group-open:rotate-90" />
                    <span className="font-display text-lg font-bold uppercase text-content">Week {week.week}</span>
                    <span className="tnum text-sm text-content-muted">
                      {week.scored > 0 ? (
                        <><span>{week.correct} of {week.scored}</span> · {pct(week.accuracy)}</>
                      ) : 'Not played yet'}
                      {week.pending > 0 && week.scored > 0 ? ` · ${week.pending} to play` : ''}
                      {week.ties > 0 ? ` · ${week.ties} tie${week.ties > 1 ? 's' : ''}` : ''}
                    </span>
                  </summary>
                  <ul className="grid gap-2 pb-4 sm:grid-cols-2">
                    {week.games.map((prediction) => (
                      <GameRow key={prediction.game_id} prediction={prediction} />
                    ))}
                  </ul>
                </details>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
};

export default LiveRecord;

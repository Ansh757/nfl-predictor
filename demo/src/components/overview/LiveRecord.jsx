import React from 'react';
import { teamAbbreviation } from '../../utils/teams';
import { OUTCOME_LABEL, outcomeOf, summarizeByWeek, totals } from '../../utils/liveRecord';

/**
 * Every official pick this season, as it was recorded before kickoff.
 *
 * The backtest section below this is a reconstruction; this is the record. It
 * gets its own section rather than a tab because the application has three
 * sections and this belongs with the other measurement on the Overview.
 *
 * Weeks are <details> elements, the same disclosure the methodology uses: one
 * line of tally per week, the games behind it a click away, keyboard and
 * screen-reader correct with no JavaScript.
 */

const OUTCOME_CLASS = {
  correct: 'text-success',
  wrong: 'text-danger',
  tie: 'text-content-muted',
  pending: 'text-content-muted',
};

const pct = (value) => (value == null ? '—' : `${(value * 100).toFixed(1)}%`);

const GameRow = ({ prediction }) => {
  const outcome = outcomeOf(prediction);
  return (
    <li className="grid grid-cols-[4.75rem_minmax(0,1fr)_auto] items-center gap-3 py-1.5 text-xs">
      <span className="tnum text-content-secondary">
        {teamAbbreviation(prediction.away_team)} @ {teamAbbreviation(prediction.home_team)}
      </span>
      <span className="tnum truncate text-content-muted">
        Picked <span className="font-medium text-content">{teamAbbreviation(prediction.predicted_winner)}</span>
        {' '}{pct(prediction.confidence)}
      </span>
      {/* A word first and a colour second - see MatchupCard. */}
      <span className={`shrink-0 font-medium ${OUTCOME_CLASS[outcome]}`}>
        {OUTCOME_LABEL[outcome]}
      </span>
    </li>
  );
};

const LiveRecord = ({ record, season }) => {
  if (record == null) return null;

  const weeks = record.status === 'ok' ? summarizeByWeek(record.data?.predictions) : [];
  const all = totals(weeks);

  return (
    <section aria-labelledby="live-record-heading" className="rounded-lg border border-edge bg-surface p-4 lg:p-5">
      <h2 id="live-record-heading" className="text-sm font-semibold text-content">
        {season} live record
      </h2>
      <p className="mt-1 text-xs leading-relaxed text-content-muted">
        Every pick here was recorded before its game kicked off and has not been changed since.
        Ties are not scored, and games not yet played count for nothing.
      </p>

      {record.status !== 'ok' ? (
        <p className="mt-4 text-sm text-content-muted">The live record could not be loaded.</p>
      ) : weeks.length === 0 ? (
        <p className="mt-4 text-sm text-content-muted">No picks recorded for {season} yet.</p>
      ) : (
        <>
          <dl className="mt-4 grid grid-cols-3 gap-3">
            {[
              ['Correct', `${all.correct} of ${all.scored}`],
              ['Accuracy', pct(all.accuracy)],
              ['Not played yet', String(all.pending)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-edge bg-surface-elevated p-3">
                <dt className="text-[11px] text-content-muted">{label}</dt>
                <dd className="tnum mt-1 whitespace-nowrap text-lg font-semibold text-content sm:text-xl">{value}</dd>
              </div>
            ))}
          </dl>

          <ul className="mt-3 divide-y divide-edge rounded-lg border border-edge bg-surface-elevated">
            {weeks.map((week) => (
              <li key={week.week}>
                <details className="group">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-sm hover:bg-surface-selected">
                    <span className="flex items-center gap-2 font-medium text-content">
                      {/* Same marker as the methodology disclosure. */}
                      <span aria-hidden="true" className="inline-block text-content-muted transition-transform group-open:rotate-90">
                        ›
                      </span>
                      Week {week.week}
                    </span>
                    <span className="tnum text-content-secondary">
                      {week.scored > 0 ? `${week.correct} of ${week.scored} · ${pct(week.accuracy)}` : 'Not played yet'}
                      {week.pending > 0 && week.scored > 0 ? ` · ${week.pending} to play` : ''}
                      {week.ties > 0 ? ` · ${week.ties} tie${week.ties > 1 ? 's' : ''}` : ''}
                    </span>
                  </summary>
                  <ul className="border-t border-edge px-3 py-1">
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

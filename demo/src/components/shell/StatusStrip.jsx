import React from 'react';

/**
 * One compact row, replacing five equally-weighted statistic cards.
 *
 * The cards gave a game count the same visual weight as the model's accuracy,
 * which is not their relative importance to anyone reading the page. This is a
 * status line: small, factual, and out of the way of the prediction data.
 *
 * Every value is real. Where there is nothing to report - live accuracy before
 * any game has been settled - it shows a dash and says why, rather than
 * printing a zero that would read as a measurement.
 */
const Item = ({ label, value, hint, emphasis = false }) => (
  <div className="flex min-w-0 items-baseline gap-2">
    <span className="whitespace-nowrap text-xs text-content-muted">{label}</span>
    <span className={`tnum whitespace-nowrap text-sm ${emphasis ? 'font-semibold text-content' : 'text-content-secondary'}`}>
      {value}
    </span>
    {hint && <span className="hidden truncate text-xs text-content-muted xl:inline">{hint}</span>}
  </div>
);

const StatusStrip = ({
  week, weekRange, gameCount, liveAccuracy, avgConfidence, highConfidenceCount,
}) => (
  <div className="border-b border-edge bg-background">
    <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5 lg:px-6">
      <Item label="Week" value={week} hint={weekRange || undefined} emphasis />
      <Item label="Games" value={gameCount} />
      <Item
        label="Live accuracy"
        value={liveAccuracy == null ? '—' : `${(liveAccuracy * 100).toFixed(1)}%`}
        hint={liveAccuracy == null ? 'no settled games yet' : '2026 settled predictions'}
      />
      <Item
        label="Avg confidence"
        value={avgConfidence == null ? '—' : `${Math.round(avgConfidence * 100)}%`}
      />
      <Item label="High confidence" value={highConfidenceCount} />
    </div>
  </div>
);

export default StatusStrip;

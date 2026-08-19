import React from 'react';
import { Calendar, Gauge, Target, TrendingUp, Users } from 'lucide-react';

const Tile = ({ icon: Icon, tone, label, value, sub }) => (
  <div className="flex items-center gap-3 rounded-2xl border border-ink-700 bg-ink-800 px-4 py-3">
    <span className={`rounded-xl p-2 ${tone}`}>
      <Icon aria-hidden="true" className="h-4 w-4" />
    </span>
    <div className="min-w-0">
      <div className="truncate text-lg font-bold text-mist">{value}</div>
      <div className="truncate text-xs text-slate-400">{label}</div>
      {sub && <div className="truncate text-[11px] text-slate-500">{sub}</div>}
    </div>
  </div>
);

/**
 * Headline numbers. Every tile is backed by real data - there is deliberately
 * no model-accuracy figure until settled predictions exist, because the only
 * honest value before kickoff is "none yet".
 */
const StatStrip = ({ week, weekRange, gameCount, liveAccuracy, avgConfidence, highConfidenceCount, lastUpdated }) => (
  <div className="grid gap-3 px-6 py-4 sm:grid-cols-2 xl:grid-cols-5">
    <Tile
      icon={Calendar}
      tone="bg-accent/15 text-accent"
      value={`Week ${week}`}
      label={weekRange || 'Regular season'}
    />
    <Tile
      icon={Users}
      tone="bg-insight/15 text-insight"
      value={gameCount}
      label={gameCount === 1 ? 'Game' : 'Games'}
    />
    <Tile
      icon={TrendingUp}
      tone="bg-positive/15 text-positive"
      value={liveAccuracy == null ? '—' : `${(liveAccuracy * 100).toFixed(1)}%`}
      label="Live accuracy"
      sub={liveAccuracy == null ? 'no settled games yet' : 'settled predictions'}
    />
    <Tile
      icon={Gauge}
      tone="bg-caution/15 text-caution"
      value={avgConfidence == null ? '—' : `${Math.round(avgConfidence * 100)}%`}
      label="Avg confidence"
    />
    <Tile
      icon={Target}
      tone="bg-positive/15 text-positive"
      value={highConfidenceCount}
      label="High confidence"
    />
  </div>
);

export default StatStrip;

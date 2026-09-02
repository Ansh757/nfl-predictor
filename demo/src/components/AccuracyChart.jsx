import React from 'react';

/**
 * Accuracy by season, drawn as inline SVG.
 *
 * No charting dependency: five points and a line do not justify pulling a
 * library into the bundle, and hand-drawing it keeps the axis honest - it
 * starts at 50%, a coin flip, rather than at the lowest value, which would
 * exaggerate the slope.
 *
 * Colours go through Tailwind classes rather than fill/stroke attributes so
 * they follow the theme; the gradient keeps its literal because accent is the
 * one token that is identical in both.
 */
const AccuracyChart = ({ data, height = 180 }) => {
  const width = 420;
  const padding = { top: 16, right: 16, bottom: 28, left: 40 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const yMin = 0.5;   // a coin flip - the only meaningful floor
  const yMax = 0.75;
  const x = (index) => padding.left + (index / (data.length - 1)) * plotWidth;
  const y = (value) => padding.top + (1 - (value - yMin) / (yMax - yMin)) * plotHeight;

  const line = data.map((row, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(row.accuracy)}`).join(' ');
  const area = `${line} L ${x(data.length - 1)} ${padding.top + plotHeight} L ${x(0)} ${padding.top + plotHeight} Z`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-auto w-full"
      role="img"
      aria-label={
        `Backtest accuracy by season: ${data.map((r) => `${r.season} ${(r.accuracy * 100).toFixed(1)}%`).join(', ')}`
      }
    >
      {[0.5, 0.6, 0.7].map((tick) => (
        <g key={tick}>
          <line x1={padding.left} x2={width - padding.right} y1={y(tick)} y2={y(tick)}
                className="stroke-ink-700" strokeWidth="1" />
          <text x={padding.left - 8} y={y(tick) + 4} textAnchor="end" fontSize="10" className="fill-slate-500">
            {Math.round(tick * 100)}%
          </text>
        </g>
      ))}

      <path d={area} fill="url(#accuracyFill)" />
      <path d={line} fill="none" className="stroke-accent" strokeWidth="2.5" strokeLinejoin="round" />

      <defs>
        <linearGradient id="accuracyFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2563EB" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#2563EB" stopOpacity="0" />
        </linearGradient>
      </defs>

      {data.map((row, index) => (
        <g key={row.season}>
          <circle cx={x(index)} cy={y(row.accuracy)} r="4" className="fill-ink-900 stroke-accent" strokeWidth="2.5" />
          <text x={x(index)} y={y(row.accuracy) - 12} textAnchor="middle" fontSize="11" className="fill-mist" fontWeight="600">
            {(row.accuracy * 100).toFixed(1)}%
          </text>
          <text x={x(index)} y={height - 8} textAnchor="middle" fontSize="10" className="fill-slate-500">
            {row.season}
          </text>
        </g>
      ))}
    </svg>
  );
};

export default AccuracyChart;

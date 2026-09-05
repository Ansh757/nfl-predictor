import React from 'react';
import { Lock } from 'lucide-react';
import { confidenceBand, teamAbbreviation, teamLogo } from '../../utils/teams';

/**
 * One game.
 *
 * There are no pick controls. The reference layout this follows had PICK NE /
 * PICK SEA buttons and a "your pick" state; this application has no user picks
 * and inventing them would imply the model responds to them. The card ends in
 * the model's own pick, stated once.
 */
const TeamLogo = ({ team }) => (
  <img
    src={teamLogo(team)}
    alt={`${team} logo`}
    loading="lazy"
    className="h-8 w-8 flex-shrink-0 object-contain"
    onError={(event) => { event.currentTarget.style.visibility = 'hidden'; }}
  />
);

const Side = ({ team, probability, predicted, align = 'left' }) => (
  <div className={`flex min-w-0 flex-1 items-center gap-2.5 ${align === 'right' ? 'flex-row-reverse text-right' : ''}`}>
    <TeamLogo team={team} />
    <div className="min-w-0">
      <div className={`truncate text-base font-semibold ${predicted ? 'text-content' : 'text-content-secondary'}`}>
        {teamAbbreviation(team)}
      </div>
      {probability != null && (
        <div className="tnum text-xs text-content-muted">
          {Math.round(probability * 100)}%
        </div>
      )}
    </div>
  </div>
);

/** Small, bordered, lowercase-friendly. Not a pill on every label. */
const Badge = ({ children, tone = 'muted' }) => {
  const tones = {
    muted: 'border-edge text-content-muted',
    accent: 'border-accent/40 text-accent',
    warning: 'border-warning/40 text-warning',
  };
  return (
    <span className={`rounded border px-1.5 py-px text-[10px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
};

const MatchupCard = ({ game, summary, isPredicting, isSelected, onSelect, formatTime }) => {
  const winner = summary?.winner;
  const confidence = summary?.confidence;
  const band = winner ? confidenceBand(confidence) : null;
  const homeIsWinner = winner === game.home_team;
  const homeProbability = winner ? (homeIsWinner ? confidence : 1 - confidence) : null;

  const finished = game.home_score != null && game.away_score != null;
  const actualWinner = finished
    ? (game.home_score > game.away_score ? game.home_team
      : game.away_score > game.home_score ? game.away_team : null)
    : null;
  const modelWasRight = finished && winner ? winner === actualWinner : null;

  const international = summary?.internationalGame || game.international_game;
  const neutral = summary?.neutralSite || game.neutral_site;

  return (
    <button
      type="button"
      onClick={() => onSelect(game)}
      aria-current={isSelected ? 'true' : undefined}
      className={`w-full rounded-lg border bg-surface p-3.5 text-left transition ${
        isSelected
          ? 'border-accent bg-surface-selected'
          : 'border-edge hover:border-edge-strong hover:bg-surface-elevated'
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <span className="tnum text-xs text-content-muted">{formatTime(game.game_date)}</span>
        <span className="flex items-center gap-1.5">
          {neutral && <Badge>Neutral site</Badge>}
          {international && <Badge tone="accent">International</Badge>}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <Side team={game.away_team} probability={homeProbability == null ? null : 1 - homeProbability}
              predicted={winner === game.away_team} />
        <span className="text-xs text-content-muted">@</span>
        <Side team={game.home_team} probability={homeProbability}
              predicted={winner === game.home_team} align="right" />
      </div>

      {homeProbability != null && (
        <div className="mt-3 flex h-1 overflow-hidden rounded-full bg-edge" aria-hidden="true">
          <div className="bg-opposing" style={{ width: `${(1 - homeProbability) * 100}%` }} />
          <div className="bg-accent" style={{ width: `${homeProbability * 100}%` }} />
        </div>
      )}

      <div className="mt-3 border-t border-edge pt-2.5">
        {isPredicting ? (
          <span className="text-xs text-content-muted">Running agents…</span>
        ) : summary?.error ? (
          <span className="text-xs text-danger">Prediction unavailable</span>
        ) : winner ? (
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <div className="min-w-0">
              <div className="text-[10px] font-medium uppercase tracking-wide text-content-muted">
                Official pick
              </div>
              <div className="truncate text-sm font-semibold text-content">
                {winner} <span className="tnum font-normal text-content-secondary">
                  · {Math.round(confidence * 100)}%
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {summary?.consensus?.label && (
                <span className="tnum text-xs text-content-muted">{summary.consensus.label}</span>
              )}
              {band && (
                <span className={`text-xs ${band.tone === 'success' ? 'text-success' : band.tone === 'warning' ? 'text-warning' : 'text-content-muted'}`}>
                  {band.label}
                </span>
              )}
              {summary?.locked && (
                <span className="flex items-center gap-1 text-xs text-content-muted" title="Recorded before kickoff">
                  <Lock aria-hidden="true" className="h-3 w-3" />
                  <span className="sr-only">Locked prediction</span>
                </span>
              )}
            </div>
          </div>
        ) : (
          <span className="text-xs text-content-muted">No prediction yet</span>
        )}
      </div>

      {finished && (
        <div className="mt-2.5 flex items-center justify-between border-t border-edge pt-2.5">
          <span className="tnum text-sm text-content-secondary">
            Final {teamAbbreviation(game.away_team)} {game.away_score} — {teamAbbreviation(game.home_team)} {game.home_score}
          </span>
          {modelWasRight != null && (
            /* Status is a word first and a colour second, so it survives being
               read aloud or seen by someone who cannot separate red from green. */
            <span className={`text-xs font-medium ${modelWasRight ? 'text-success' : 'text-danger'}`}>
              {modelWasRight ? 'Model correct' : 'Model wrong'}
            </span>
          )}
        </div>
      )}
    </button>
  );
};

export default MatchupCard;

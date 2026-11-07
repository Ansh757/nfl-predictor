import React from 'react';
import { ArrowRight } from 'lucide-react';
import { confidenceBand, teamAbbreviation, teamNickname } from '../../utils/teams';
import { ProbabilityBar, TeamLogo } from '../shell/PageIntro';
import { OutcomeBadge } from '../overview/LiveRecord';

/**
 * One game: kickoff, both teams, and the model's pick underneath.
 *
 * Two things it deliberately does NOT do:
 *
 *   - There are no pick controls, and no "run the model" button. The model's
 *     pick is shown as soon as it is computed; a control implying the reader
 *     changes or triggers it would be a lie about what this application is.
 *   - The surface does not lean toward the predicted winner. A card brightening
 *     toward one team is the loudest argument on the page for a pick the model
 *     makes at 55%. The pick is carried by the PICK tag, the accent on the bar
 *     and the line under it. One solid surface.
 */

const BAND_TONE = {
  success: 'text-success',
  warning: 'text-warning',
  muted: 'text-content-muted',
};

const TeamRow = ({ team, score, picked, lost, finished }) => (
  <div className="flex items-center gap-3">
    <TeamLogo team={team} size={40} dim={lost} />
    <div className="min-w-0 flex-1">
      <div className="flex items-baseline gap-2">
        <span className={`font-display text-xl font-bold leading-none tracking-wide ${
          lost ? 'text-content-muted' : 'text-content'
        }`}>
          {teamAbbreviation(team)}
        </span>
        {picked && (
          <span className="rounded-sm bg-accent/20 px-1.5 py-0.5 font-display text-[10px] font-semibold uppercase tracking-widest text-accent">
            Pick
          </span>
        )}
      </div>
      <p className="truncate text-sm text-content-muted">{teamNickname(team)}</p>
    </div>
    {finished && (
      <span className={`tnum font-display text-3xl font-bold ${lost ? 'text-content-muted' : 'text-content'}`}>
        {score}
      </span>
    )}
  </div>
);

const MatchupCard = ({ game, summary, isPredicting, isSelected, onSelect, formatTime }) => {
  const winner = summary?.winner;
  const confidence = summary?.confidence;
  const hasPick = Boolean(winner && confidence != null && !summary?.error);
  const band = hasPick ? confidenceBand(confidence) : null;
  const homeIsWinner = winner === game.home_team;
  const homeProbability = hasPick ? (homeIsWinner ? confidence : 1 - confidence) : null;

  const finished = game.home_score != null && game.away_score != null;
  const actualWinner = finished
    ? (game.home_score > game.away_score ? game.home_team
      : game.away_score > game.home_score ? game.away_team : null)
    : null;
  // A tie is neither correct nor wrong. Comparing the pick against a null
  // winner would score every drawn game as a miss.
  const modelWasRight = finished && hasPick && actualWinner ? winner === actualWinner : null;
  const outcome = !finished ? 'pending' : modelWasRight == null ? null : modelWasRight ? 'correct' : 'wrong';

  const international = summary?.internationalGame || game.international_game;
  const neutral = summary?.neutralSite || game.neutral_site;
  const consensus = summary?.consensus;

  /*
   * An explicit accessible name, because the card is one button wrapping a
   * dozen fragments; left to itself the browser reads every number twice and
   * no sentence. The band is spelled out ("lean confidence in that pick") -
   * it is what a sighted reader gets from the word beside the percentage.
   */
  const label = [
    `${game.away_team} at ${game.home_team}`,
    formatTime(game.game_date),
    hasPick
      ? `Model picks ${winner}, ${Math.round(confidence * 100)} percent confidence`
        + `${consensus?.label ? `, ${consensus.count} of ${consensus.total} agents agree` : ''}`
        + `${band ? `, ${band.label.toLowerCase()} confidence in that pick` : ''}`
      : isPredicting ? 'Prediction running' : 'No prediction yet',
    finished
      ? `Final ${game.away_score} to ${game.home_score}`
        + `${modelWasRight == null ? '' : modelWasRight ? ', model correct' : ', model wrong'}`
      : null,
    'View analysis',
  ].filter(Boolean).join('. ');

  return (
    <button
      type="button"
      onClick={() => onSelect(game)}
      aria-label={label}
      aria-current={isSelected ? 'true' : undefined}
      className={`group w-full cursor-pointer overflow-hidden rounded-lg border bg-surface text-left transition duration-150 hover:-translate-y-px hover:border-accent ${
        isSelected ? 'border-accent' : 'border-edge'
      }`}
    >
      <div aria-hidden="true">
        <div className="flex items-center justify-between gap-3 border-b border-edge px-5 py-3">
          <div className="min-w-0">
            <p className="eyebrow tnum truncate text-content-muted">{formatTime(game.game_date)}</p>
            {game.venue && <p className="truncate text-xs text-content-muted">{game.venue}</p>}
          </div>
          <div className="flex flex-shrink-0 items-center gap-1.5">
            {neutral && (
              <span className="rounded border border-edge px-1.5 py-px text-[10px] font-medium text-content-muted">Neutral site</span>
            )}
            {international && (
              <span className="rounded border border-edge px-1.5 py-px text-[10px] font-medium text-content-secondary">International</span>
            )}
            {outcome && hasPick && <OutcomeBadge outcome={outcome} />}
          </div>
        </div>

        <div className="space-y-3 px-5 py-4">
          <TeamRow
            team={game.away_team} score={game.away_score} finished={finished}
            picked={hasPick && !homeIsWinner}
            lost={actualWinner != null && actualWinner !== game.away_team}
          />
          <TeamRow
            team={game.home_team} score={game.home_score} finished={finished}
            picked={hasPick && homeIsWinner}
            lost={actualWinner != null && actualWinner !== game.home_team}
          />
        </div>

        <div className="border-t border-edge bg-background px-5 py-4">
          {isPredicting && !hasPick ? (
            <p className="text-sm text-content-muted">Running agents…</p>
          ) : summary?.error ? (
            <p className="text-sm text-danger">Prediction unavailable</p>
          ) : hasPick ? (
            <div className="space-y-3">
              <ProbabilityBar homeProbability={homeProbability} homePicked={homeIsWinner} />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm">
                  <span className="text-content-muted">Model takes </span>
                  <span className="font-display font-semibold uppercase tracking-wide text-content">
                    {teamNickname(winner)}
                  </span>
                  {band && (
                    <span className={`ml-2 font-display text-xs font-semibold uppercase tracking-widest ${BAND_TONE[band.tone]}`}>
                      {band.label}
                    </span>
                  )}
                </p>
                {consensus?.label && (
                  <span className="tnum text-xs font-medium text-content-muted">
                    {consensus.count}/{consensus.total} agents agree
                  </span>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-content-muted">No prediction yet</p>
          )}

          {/* An affordance, not a control - the whole card is the button, and a
              nested <button> here would be invalid and unreachable. */}
          <p className="mt-3 flex items-center gap-1 text-xs font-medium text-content-muted transition group-hover:text-accent">
            View analysis
            <ArrowRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
          </p>
        </div>
      </div>
    </button>
  );
};

export default MatchupCard;

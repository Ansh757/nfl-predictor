import React from 'react';
import { ArrowRight } from 'lucide-react';
import { confidenceBand, teamAbbreviation, teamLogo, teamNickname } from '../../utils/teams';
import { kickoffParts } from '../../utils/time';

/**
 * One game, with the model's pick as the thing you see first.
 *
 * The earlier card stated the pick correctly and quietly - a line of 14px text
 * at the bottom, the same size as the kickoff time above it. Everything on the
 * card had equal weight, so nothing read as the answer. This version gives the
 * pick the largest type on the card and tints the winning side, so the shape of
 * the prediction is legible before a single number is read.
 *
 * Two things it deliberately does NOT do:
 *
 *   - There are no pick controls. The reference layout had PICK NE / PICK SEA
 *     buttons; this application has no user picks and a control implying the
 *     model responds to one would be a lie about what it is.
 *   - The tint is dropped once a game is final. A card that shades its losing
 *     prediction green and captions it "Model wrong" is celebrating and
 *     retracting in the same frame; once there is a result, the result is the
 *     story.
 */
const TeamLogo = ({ team, dim }) => (
  <img
    src={teamLogo(team)}
    alt=""
    loading="lazy"
    className={`h-9 w-9 flex-shrink-0 object-contain transition ${dim ? 'opacity-45' : ''}`}
    onError={(event) => { event.currentTarget.style.visibility = 'hidden'; }}
  />
);

/**
 * One side of the matchup. The predicted side keeps full contrast; the other is
 * stepped down to secondary, which is the quietest way to say which way the
 * model leans without repeating it a fourth time.
 */
const Side = ({ team, predicted, hasPick, align = 'left' }) => (
  <div className={`flex min-w-0 flex-1 items-center gap-2.5 ${align === 'right' ? 'flex-row-reverse text-right' : ''}`}>
    <TeamLogo team={team} dim={hasPick && !predicted} />
    <div className="min-w-0">
      <div className={`truncate text-lg font-semibold leading-tight ${
        !hasPick || predicted ? 'text-content' : 'text-content-secondary'
      }`}>
        {teamAbbreviation(team)}
      </div>
      <div className="truncate text-xs text-content-muted">{teamNickname(team)}</div>
    </div>
  </div>
);

/**
 * Headcount as dots, with the count in text beside it.
 *
 * Aria-hidden: "3/5 agents" is already written next to this, so announcing five
 * list items would only make a screen reader read the same fact twice. Note
 * this is a headcount, not influence - the vote is weighted, and a minority of
 * agents can carry a decision.
 */
const AgentDots = ({ count, total }) => (
  <span aria-hidden="true" className="flex items-center gap-[3px]">
    {Array.from({ length: Math.min(total, 8) }, (_, index) => (
      <span
        key={index}
        className={`h-1.5 w-1.5 rounded-full ${index < count ? 'bg-accent' : 'bg-edge-strong'}`}
      />
    ))}
  </span>
);

/** Small, bordered. Not a pill on every label. */
const Badge = ({ children, tone = 'muted' }) => {
  const tones = {
    muted: 'border-edge text-content-muted',
    accent: 'border-accent/40 text-accent',
  };
  return (
    <span className={`rounded border px-1.5 py-px text-[10px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
};

const BAND_TONE = {
  success: 'text-success',
  warning: 'text-warning',
  muted: 'text-content-muted',
};

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
  const modelWasRight = finished && winner && actualWinner ? winner === actualWinner : null;

  const international = summary?.internationalGame || game.international_game;
  const neutral = summary?.neutralSite || game.neutral_site;

  const parts = kickoffParts(game.game_date);
  const consensus = summary?.consensus;

  /*
   * Only while the outcome is still open - see the note at the top of the file -
   * and never on a selected card. Selection already carries an accent border and
   * its own lighter surface; stacking the tint on top of that is a second copy
   * of the same signal, and it composites a background on which text-muted
   * measures 3.98:1, under AA. theme.test.js pins the tint's contrast on the
   * surfaces it is actually allowed to land on.
   */
  const tinted = hasPick && !finished && !isSelected;

  /*
   * An explicit accessible name, because the card is one button wrapping a
   * dozen fragments. Left to itself the browser concatenates all of them and
   * announces "SUN SEP 13 1:00 PM EDT NE Patriots SEA Seahawks 45 percent 55
   * percent predicted winner Seahawks 55 percent 3/5 agents low edge view
   * analysis" - every number twice and no sentence.
   *
   * The label carries the caveat as well as the pick. "Low edge" is the part a
   * sighted reader gets from a muted label beside the confidence, and dropping
   * it here would leave a screen reader user with a bare, more certain-sounding
   * claim than the card actually makes.
   */
  const label = [
    `${game.away_team} at ${game.home_team}`,
    formatTime(game.game_date),
    hasPick
      ? `Model picks ${winner}, ${Math.round(confidence * 100)} percent confidence`
        + `${consensus?.label ? `, ${consensus.count} of ${consensus.total} agents agree` : ''}`
        + `${band ? `, ${band.label.toLowerCase()} edge` : ''}`
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
      /*
       * No background lift on hover. The card only ever sits on `surface`, and
       * that is load-bearing: the winner tint composites over whatever is
       * underneath it, and over `surface-elevated` it drags text-muted to
       * 4.27:1 - under AA - at any alpha strong enough to see. Hover is carried
       * by the border and by "View analysis" turning accent, which is enough.
       */
      className={`group relative w-full overflow-hidden rounded-lg border bg-surface p-4 text-left transition ${
        isSelected
          ? 'border-accent bg-surface-selected'
          : 'border-edge hover:border-edge-strong'
      }`}
    >
      {/* The winner's half of the card, tinted. Low alpha on purpose: it has to
          read as a lean, not as a highlighted row, and it sits under text whose
          contrast is asserted against the untinted surface. */}
      {tinted && (
        <span
          aria-hidden="true"
          className={`pointer-events-none absolute inset-y-0 w-3/5 ${
            homeIsWinner
              ? 'right-0 bg-gradient-to-l from-accent/[0.14] to-transparent'
              : 'left-0 bg-gradient-to-r from-accent/[0.14] to-transparent'
          }`}
        />
      )}

      <div className="relative" aria-hidden="true">
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <span className="tnum text-[11px] font-medium uppercase tracking-wide text-content-muted">
            {parts ? `${parts.weekday} · ${parts.date} · ${parts.time}` : formatTime(game.game_date)}
          </span>
          <span className="flex items-center gap-1.5">
            {neutral && <Badge>Neutral site</Badge>}
            {international && <Badge tone="accent">International</Badge>}
          </span>
        </div>

        <div className="mt-3.5 flex items-center gap-3">
          <Side team={game.away_team} predicted={winner === game.away_team} hasPick={hasPick} />
          <span className="text-[11px] font-medium text-content-muted">@</span>
          <Side team={game.home_team} predicted={winner === game.home_team} hasPick={hasPick}
                align="right" />
        </div>

        {homeProbability != null && (
          /*
           * The accent marks the side the model picked, never simply the home
           * team. Colouring by home/away looked right on any game the home side
           * was favoured in and was backwards on every other one - Baltimore at
           * Indianapolis, picked Ravens 60%, lit up the Colts' 40% instead. It
           * also pointed the opposite way to the card tint, which follows the
           * pick, so the same card argued with itself.
           */
          <div className="mt-3 flex items-center gap-2.5">
            <span className={`tnum w-9 text-xs font-medium ${
              homeIsWinner ? 'text-content-muted' : 'text-content'
            }`}>
              {Math.round((1 - homeProbability) * 100)}%
            </span>
            <span className="relative flex h-1.5 flex-1 overflow-hidden rounded-full bg-edge">
              <span
                className={homeIsWinner ? 'bg-opposing' : 'bg-accent'}
                style={{ width: `${(1 - homeProbability) * 100}%` }}
              />
              <span
                className={homeIsWinner ? 'bg-accent' : 'bg-opposing'}
                style={{ width: `${homeProbability * 100}%` }}
              />
              {/* The coin-flip mark. A 55% pick looks decisive until you can see
                  how close to the middle it actually sits. */}
              <span className="absolute left-1/2 top-0 h-full w-0.5 -translate-x-1/2 bg-background" />
            </span>
            <span className={`tnum w-9 text-right text-xs font-medium ${
              homeIsWinner ? 'text-content' : 'text-content-muted'
            }`}>
              {Math.round(homeProbability * 100)}%
            </span>
          </div>
        )}

        <div className="mt-3.5 border-t border-edge pt-3">
          {isPredicting ? (
            <p className="text-center text-xs text-content-muted">Running agents…</p>
          ) : summary?.error ? (
            <p className="text-center text-xs text-danger">Prediction unavailable</p>
          ) : hasPick ? (
            <div className="text-center">
              <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-content-muted">
                Predicted winner
              </p>
              <p className="mt-1 truncate text-2xl font-semibold uppercase leading-none tracking-tight text-content">
                {teamNickname(winner)}
              </p>
              <p className="tnum mt-1.5 text-sm font-semibold text-accent">
                {Math.round(confidence * 100)}%
              </p>

              <div className="mt-3 flex items-center justify-center gap-4">
                {consensus?.label && (
                  <span className="flex items-center gap-1.5">
                    <AgentDots count={consensus.count} total={consensus.total} />
                    <span className="tnum text-[11px] font-medium uppercase tracking-wide text-content-muted">
                      {consensus.label}
                    </span>
                  </span>
                )}
                {band && (
                  <span className={`text-[11px] font-medium uppercase tracking-wide ${BAND_TONE[band.tone]}`}>
                    {band.label} edge
                  </span>
                )}
              </div>
            </div>
          ) : (
            <p className="text-center text-xs text-content-muted">No prediction yet</p>
          )}
        </div>

        {finished && (
          <div className="mt-3 flex items-center justify-between border-t border-edge pt-3">
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

        {/* An affordance, not a control - the whole card is the button, and a
            nested <button> here would be invalid and unreachable. */}
        <p className="mt-3 flex items-center justify-center gap-1 text-[11px] font-medium text-content-muted transition group-hover:text-accent">
          View analysis
          <ArrowRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
        </p>
      </div>
    </button>
  );
};

export default MatchupCard;

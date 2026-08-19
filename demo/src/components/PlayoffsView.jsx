import React from 'react';
import { AlertTriangle, Trophy } from 'lucide-react';
import { teamAbbreviation, teamLogo } from '../utils/teams';

const ROUND_ORDER = ['Wild Card', 'Divisional', 'Conference', 'Super Bowl'];

const isPlaceholder = (team) => !team || team === 'TBD';

const Side = ({ team, score, seed, won, decided }) => (
  <div className={`flex items-center justify-between gap-3 rounded-xl px-3 py-2 ${
    won ? 'bg-accent/10 ring-1 ring-accent/40' : 'bg-ink-800'
  }`}>
    <span className="flex min-w-0 items-center gap-2">
      {!isPlaceholder(team) && (
        <img
          src={teamLogo(team)} alt="" aria-hidden="true" loading="lazy"
          className="h-6 w-6 flex-shrink-0 object-contain"
          onError={(event) => { event.currentTarget.style.visibility = 'hidden'; }}
        />
      )}
      <span className={`truncate text-sm font-semibold ${won ? 'text-mist' : 'text-slate-300'}`}>
        {isPlaceholder(team) ? 'TBD' : teamAbbreviation(team)}
      </span>
      {seed != null && <span className="text-[11px] text-slate-500">#{seed}</span>}
    </span>
    {decided && (
      <span className={`text-sm font-bold tabular-nums ${won ? 'text-mist' : 'text-slate-500'}`}>
        {score}
      </span>
    )}
  </div>
);

const Matchup = ({ game }) => {
  const decided = game.home_score != null && game.away_score != null;
  const homeWon = decided && game.home_score > game.away_score;
  const awayWon = decided && game.away_score > game.home_score;

  return (
    <div className="space-y-1.5 rounded-2xl border border-ink-700 bg-ink-900 p-2">
      <Side team={game.away_team} score={game.away_score} seed={game.away_seed} won={awayWon} decided={decided} />
      <Side team={game.home_team} score={game.home_score} seed={game.home_seed} won={homeWon} decided={decided} />
    </div>
  );
};

/**
 * Completed brackets only.
 *
 * There is deliberately no simulator here. Every playoff row in the database
 * has a null seed, so the seed-gap model it used could only ever return 0.5 -
 * a coin flip dressed up as a projection. And it never advanced winners, so it
 * scored each stored matchup independently. For a finished season the results
 * are already known, and for a future one the teams are still TBD, which leaves
 * it no regime where it says anything.
 */
const PlayoffsView = ({ season, seasonOptions, onSeasonChange, gamesByRound, loading, error }) => {
  const rounds = ROUND_ORDER.filter((round) => (gamesByRound?.[round] ?? []).length);
  const everyTeamUnknown = rounds.length > 0 && rounds.every((round) =>
    gamesByRound[round].every((game) => isPlaceholder(game.home_team) && isPlaceholder(game.away_team))
  );

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-ink-700 bg-ink-900 p-4">
        <div className="flex items-center gap-2">
          <Trophy aria-hidden="true" className="h-5 w-5 text-caution" />
          <h2 className="text-sm font-bold uppercase tracking-wide text-mist">Playoff bracket</h2>
        </div>
        <div>
          <label htmlFor="playoff-season" className="sr-only">Playoff season</label>
          <select
            id="playoff-season"
            value={season}
            onChange={onSeasonChange}
            className="rounded-xl border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-mist outline-none transition focus:border-accent"
          >
            {seasonOptions.map((option) => (
              <option key={option} value={option}>{option} postseason</option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div role="status" className="rounded-2xl border border-ink-700 bg-ink-900 py-16 text-center text-sm text-slate-400">
          Loading bracket…
        </div>
      ) : error ? (
        <div role="alert" className="rounded-2xl border border-red-500/40 bg-red-500/5 py-12 text-center">
          <div className="text-sm font-semibold text-red-400">Could not load the bracket</div>
          <div className="mt-1 text-xs text-slate-400">{error}</div>
        </div>
      ) : !rounds.length ? (
        <div className="rounded-2xl border border-ink-700 bg-ink-900 py-16 text-center">
          <Trophy aria-hidden="true" className="mx-auto h-10 w-10 text-slate-600" />
          <p className="mt-3 text-sm text-slate-400">No postseason games recorded for {season}</p>
        </div>
      ) : everyTeamUnknown ? (
        <div className="rounded-2xl border border-ink-700 bg-ink-900 py-16 text-center">
          <AlertTriangle aria-hidden="true" className="mx-auto h-10 w-10 text-caution" />
          <p className="mt-3 text-sm font-semibold text-mist">Bracket not set yet</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">
            The {season} postseason field is decided after Week 18, so every matchup is still
            listed as TBD. Pick an earlier season to see a completed bracket.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-4">
          {rounds.map((round) => (
            <div key={round} className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">{round}</h3>
              {gamesByRound[round].map((game, index) => (
                <Matchup key={game.game_id ?? `${round}-${index}`} game={game} />
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  );
};

export default PlayoffsView;

import React from 'react';
import ConferenceStandings from './playoffs/ConferenceStandings';
import MatchupCard from './predictions/MatchupCard';
import SelectedGameAnalysis from './predictions/SelectedGameAnalysis';
import { teamAbbreviation, teamLogo } from '../utils/teams';

const ROUND_ORDER = ['Wild Card', 'Divisional', 'Conference', 'Super Bowl'];
const isPlaceholder = (team) => !team || team === 'TBD';

/**
 * A completed bracket, drawn from stored results.
 *
 * No advance probabilities and no simulation count. The seed-gap simulator this
 * page used to carry could only ever return 0.5 - every playoff row has a null
 * seed - and it never advanced winners between rounds, so it was a coin flip
 * presented as a projection.
 */
const BracketColumn = ({ round, games }) => (
  <div className="min-w-[160px] flex-1">
    <h3 className="pb-2 text-[11px] font-semibold uppercase tracking-wide text-content-muted">
      {round}
    </h3>
    <div className="space-y-2">
      {games.map((game, index) => {
        const decided = game.home_score != null && game.away_score != null;
        const homeWon = decided && game.home_score > game.away_score;
        const awayWon = decided && game.away_score > game.home_score;
        return (
          <div key={game.game_id ?? `${round}-${index}`} className="rounded border border-edge bg-surface p-1.5">
            {[
              { team: game.away_team, score: game.away_score, won: awayWon },
              { team: game.home_team, score: game.home_score, won: homeWon },
            ].map((side, sideIndex) => (
              <div
                key={sideIndex}
                className={`flex items-center justify-between gap-2 rounded px-2 py-1.5 ${
                  side.won ? 'bg-surface-selected' : ''
                }`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  {!isPlaceholder(side.team) && (
                    <img
                      src={teamLogo(side.team)} alt={`${side.team} logo`} loading="lazy"
                      className="h-4 w-4 flex-shrink-0 object-contain"
                      onError={(event) => { event.currentTarget.style.visibility = 'hidden'; }}
                    />
                  )}
                  <span className={`truncate text-xs ${side.won ? 'font-semibold text-content' : 'text-content-secondary'}`}>
                    {isPlaceholder(side.team) ? 'TBD' : teamAbbreviation(side.team)}
                  </span>
                </span>
                {decided && (
                  <span className={`tnum text-xs ${side.won ? 'font-semibold text-content' : 'text-content-muted'}`}>
                    {side.score}
                  </span>
                )}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  </div>
);

const PlayoffsPage = ({
  season, seasonOptions, onSeasonChange,
  afc, nfc, standingsReady, standingsError,
  gamesByRound, loading, error,
  postseasonGames, predictionSummaries, predictionLoading,
  selectedGame, onSelectGame, formatTime, agentDefinitions,
}) => {
  const rounds = ROUND_ORDER.filter((round) => (gamesByRound?.[round] ?? []).length);
  const everyTeamUnknown = rounds.length > 0 && rounds.every((round) =>
    gamesByRound[round].every((game) => isPlaceholder(game.home_team) && isPlaceholder(game.away_team))
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-edge bg-surface px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-content">Current playoff picture</h2>
          {/* Not "projected". Nothing here forecasts a future standing - these
              are the games that have actually been played. */}
          <p className="text-xs text-content-muted">
            Records from completed {season} games. Rank is by win percentage, not an official NFL seed.
          </p>
        </div>
        <div>
          <label htmlFor="playoff-season" className="sr-only">Playoff season</label>
          <select
            id="playoff-season"
            value={season}
            onChange={onSeasonChange}
            className="tnum h-9 rounded border border-edge bg-surface-elevated px-2.5 text-sm text-content outline-none transition hover:border-edge-strong"
          >
            {seasonOptions.map((option) => (
              <option key={option} value={option}>{option} season</option>
            ))}
          </select>
        </div>
      </div>

      {standingsError ? (
        <div role="alert" className="rounded-lg border border-danger/40 bg-surface p-6 text-center">
          <p className="text-sm font-medium text-danger">Could not load standings</p>
          <p className="mt-1 text-xs text-content-muted">{standingsError}</p>
        </div>
      ) : !standingsReady ? (
        <div role="status" className="rounded-lg border border-edge bg-surface p-8 text-center text-sm text-content-muted">
          Loading standings…
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          <ConferenceStandings conference="AFC" rows={afc} season={season} />
          <ConferenceStandings conference="NFC" rows={nfc} season={season} />
        </div>
      )}

      <section aria-label="Postseason" className="rounded-lg border border-edge bg-surface p-4">
        <h2 className="pb-3 text-sm font-semibold text-content">Postseason</h2>
        {loading ? (
          <p role="status" className="py-8 text-center text-sm text-content-muted">Loading bracket…</p>
        ) : error ? (
          <p role="alert" className="py-8 text-center text-sm text-danger">{error}</p>
        ) : !rounds.length ? (
          <p className="py-8 text-center text-sm text-content-muted">
            No postseason games recorded for {season}.
          </p>
        ) : everyTeamUnknown ? (
          <div className="py-8 text-center">
            <p className="text-sm font-medium text-content">Bracket not set yet</p>
            <p className="mx-auto mt-1.5 max-w-md text-xs text-content-muted">
              The {season} field is decided after Week 18, so every matchup is still listed as TBD.
              Pick an earlier season to see a completed bracket.
            </p>
          </div>
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-1">
            {rounds.map((round) => (
              <BracketColumn key={round} round={round} games={gamesByRound[round]} />
            ))}
          </div>
        )}
      </section>

      {postseasonGames?.length > 0 && (
        <>
          <section aria-label="Postseason matchups">
            <h2 className="pb-2 text-sm font-semibold text-content">Postseason matchups</h2>
            <div className="grid gap-3 xl:grid-cols-2">
              {postseasonGames.map((game) => (
                <MatchupCard
                  key={game.game_id}
                  game={game}
                  summary={predictionSummaries?.[game.game_id]}
                  isPredicting={predictionLoading?.[game.game_id]}
                  isSelected={selectedGame?.game_id === game.game_id}
                  onSelect={onSelectGame}
                  formatTime={formatTime}
                />
              ))}
            </div>
          </section>

          <SelectedGameAnalysis
            game={selectedGame}
            summary={selectedGame ? predictionSummaries?.[selectedGame.game_id] : null}
            isPredicting={selectedGame ? predictionLoading?.[selectedGame.game_id] : false}
            agentDefinitions={agentDefinitions}
            formatTime={formatTime}
          />
        </>
      )}
    </div>
  );
};

export default PlayoffsPage;

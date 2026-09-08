import React from 'react';
import Bracket from './playoffs/Bracket';
import ConferenceStandings from './playoffs/ConferenceStandings';
import MatchupCard from './predictions/MatchupCard';
import SelectedGameAnalysis from './predictions/SelectedGameAnalysis';

const ROUND_ORDER = ['Wild Card', 'Divisional', 'Conference', 'Super Bowl'];
const isPlaceholder = (team) => !team || team === 'TBD';

const PlayoffsPage = ({
  season, seasonOptions, onSeasonChange,
  afc, nfc, standingsReady, standingsError, projecting,
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
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-content">
            {projecting ? 'Projected playoff picture' : 'Current playoff picture'}
          </h2>
          {projecting ? (
            <>
              <p className="text-xs text-content-muted">
                Record so far plus this week&rsquo;s predicted results. Rank is by projected win
                percentage, not an official NFL seed.
              </p>
              {/*
                * Said plainly, because a projected table is the easiest thing on
                * this site to mistake for a forecast of the season. It is one
                * game deep - the games the model has actually published a pick
                * for - and it is not a playoff probability. That would need the
                * remaining schedule simulated, which nothing here can do.
                */}
              <p className="mt-1 text-[11px] font-medium uppercase tracking-wide text-warning">
                Model projection — not current standings
              </p>
            </>
          ) : (
            <p className="text-xs text-content-muted">
              Records from completed {season} games. Rank is by win percentage, not an official
              NFL seed.
            </p>
          )}
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
        <div role="alert" className="rounded-lg border border-danger bg-surface p-6 text-center">
          <p className="text-sm font-medium text-danger">Could not load standings</p>
          <p className="mt-1 text-xs text-content-muted">{standingsError}</p>
        </div>
      ) : !standingsReady ? (
        <div role="status" className="rounded-lg border border-edge bg-surface p-8 text-center text-sm text-content-muted">
          Loading standings…
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          <ConferenceStandings conference="AFC" rows={afc} season={season} projecting={projecting} />
          <ConferenceStandings conference="NFC" rows={nfc} season={season} projecting={projecting} />
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
          <Bracket gamesByRound={gamesByRound} />
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

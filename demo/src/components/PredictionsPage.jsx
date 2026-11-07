import React from 'react';
import PredictionFilters from './predictions/PredictionFilters';
import WeekNavigator from './predictions/WeekNavigator';
import MatchupCard from './predictions/MatchupCard';
import SelectedGameAnalysis from './predictions/SelectedGameAnalysis';
import RotobotPanel from './predictions/RotobotPanel';
import { PageIntro, StatTile } from './shell/PageIntro';

/**
 * The prediction workspace: the week, its numbers, every game, then the
 * selected game's analysis and its Rotobot simulation.
 *
 * Every game of the week is on the page at once. A week is at most sixteen
 * games, three to a row; the pagination that used to split it into pages of
 * eight hid half the slate behind a control for no gain.
 */

const pct = (value) => (value == null ? '—' : `${Math.round(value * 100)}%`);

/** Seasons as a segmented control - six short numbers fit in one row. */
const SeasonPicker = ({ seasons, season, onChange }) => (
  <div role="group" aria-label="Season" className="flex w-fit flex-wrap gap-1 rounded-lg border border-edge bg-surface p-1">
    {seasons.map((option) => (
      <button
        key={option}
        type="button"
        onClick={() => onChange(option)}
        aria-pressed={option === season}
        className={`tnum rounded-md px-3 py-1.5 font-display text-sm font-semibold transition ${
          option === season ? 'bg-accent text-accent-on' : 'text-content-muted hover:text-content'
        }`}
      >
        {option}
      </button>
    ))}
  </div>
);

const PredictionsPage = ({
  filters,
  season, seasonOptions, onSeasonChange,
  weeks, currentWeek, weekRange, onWeekChange, weekResults,
  games, predictionSummaries, predictionLoading,
  selectedGame, onSelectGame, formatTime,
  loading, gamesError, serviceWaking,
  avgConfidence, strongPickCount,
  agentDefinitions, apiUrl,
}) => {
  const recorded = weekResults?.[currentWeek];
  return (
    <div>
      <PageIntro
        eyebrow={`${season} regular season${weekRange ? ` · ${weekRange}` : ''}`}
        title={`Week ${currentWeek}`}
        aside={<SeasonPicker seasons={seasonOptions} season={season} onChange={onSeasonChange} />}
      >
        Every matchup with the model's pick. Open a game to see how each agent voted and why.
      </PageIntro>

      <WeekNavigator
        weeks={weeks} currentWeek={currentWeek} onWeekChange={onWeekChange}
        weekResults={weekResults}
      />

      <dl className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Games" value={games.length} />
        <StatTile
          label="Record"
          value={recorded?.scored ? `${recorded.correct}–${recorded.scored - recorded.correct}` : '—'}
          sub={recorded?.scored ? pct(recorded.accuracy) : recorded ? 'Not played yet' : 'No picks recorded'}
        />
        <StatTile label="Avg confidence" value={pct(avgConfidence)} />
        <StatTile label="Strong picks" value={strongPickCount} sub="70% or better" />
      </dl>

      <div className="mt-6">
        <PredictionFilters {...filters} />
      </div>

      <section aria-label="Matchups" className="mt-6 min-w-0">
        <p className="tnum pb-3 text-xs text-content-muted">
          {games.length === 1 ? '1 game' : `${games.length} games`}
        </p>

        {loading && !games.length ? (
          <div role="status" className="rounded-lg border border-edge bg-surface p-8 text-center">
            <p className="text-sm text-content-muted">Loading games…</p>
            {serviceWaking && (
              <p className="mx-auto mt-1.5 max-w-xs text-xs text-content-muted">
                The service is waking up. A first load can take up to a minute.
              </p>
            )}
          </div>
        ) : gamesError ? (
          <div role="alert" className="rounded-lg border border-danger bg-surface p-8 text-center">
            <p className="font-display text-lg font-semibold uppercase tracking-wider text-danger">Could not load games</p>
            <p className="mt-1 text-sm text-content-muted">{gamesError}</p>
          </div>
        ) : !games.length ? (
          <div className="rounded-lg border border-edge bg-surface p-8 text-center">
            <p className="text-sm text-content-muted">No games match these filters for week {currentWeek}.</p>
          </div>
        ) : (
          <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
            {games.map((game) => (
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
        )}
      </section>

      <div className="mt-12 space-y-12">
        <SelectedGameAnalysis
          game={selectedGame}
          summary={selectedGame ? predictionSummaries?.[selectedGame.game_id] : null}
          isPredicting={selectedGame ? predictionLoading?.[selectedGame.game_id] : false}
          agentDefinitions={agentDefinitions}
          formatTime={formatTime}
        />

        <RotobotPanel game={selectedGame} apiUrl={apiUrl} />
      </div>
    </div>
  );
};

export default PredictionsPage;

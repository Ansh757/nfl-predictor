import React from 'react';

const TeamRow = ({ team, seed, isHighlighted, mutedTextClass, primaryTextClass, isDarkMode }) => (
  <div
    className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-semibold transition ${
      isHighlighted
        ? isDarkMode
          ? 'bg-blue-500/20 text-blue-100'
          : 'bg-blue-50 text-blue-800'
        : `${primaryTextClass}`
    }`}
  >
    <div className="flex items-center gap-2">
      <span
        className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
          isHighlighted
            ? isDarkMode
              ? 'bg-blue-500/30 text-blue-100'
              : 'bg-blue-100 text-blue-700'
            : isDarkMode
            ? 'bg-slate-800 text-slate-200'
            : 'bg-slate-100 text-slate-600'
        }`}
      >
        {seed}
      </span>
      <span>{team}</span>
    </div>
    {isHighlighted && (
      <span className={`text-[11px] uppercase ${mutedTextClass}`}>Projected</span>
    )}
  </div>
);

const PlayoffsBracket = ({
  rounds,
  gamesByRound,
  selectedRound,
  onSelectGame,
  isDarkMode,
  mutedTextClass,
  primaryTextClass,
  surfaceClass
}) => (
  <section className={`${surfaceClass} rounded-2xl p-6`}>
    <div className="flex flex-col gap-2">
      <p className={`text-sm font-semibold uppercase tracking-wide ${mutedTextClass}`}>
        Playoff Bracket
      </p>
      <h2 className={`text-xl font-semibold ${primaryTextClass}`}>Round-by-round matchups</h2>
      <p className={`text-sm ${mutedTextClass}`}>
        Click a matchup to run the same prediction analysis used in Regular Season.
      </p>
    </div>

    <div className="mt-6 overflow-x-auto">
      <div className="flex min-w-[720px] gap-6">
        {rounds.map((round) => {
          const isSelected = round === selectedRound;
          const games = gamesByRound?.[round] ?? [];
          return (
            <div key={round} className="flex min-w-[220px] flex-1 flex-col gap-4">
              <div
                className={`rounded-xl border px-4 py-2 text-sm font-semibold uppercase tracking-wide ${
                  isSelected
                    ? isDarkMode
                      ? 'border-blue-400/60 bg-blue-500/10 text-blue-100'
                      : 'border-blue-200 bg-blue-50 text-blue-700'
                    : isDarkMode
                    ? 'border-slate-800 bg-slate-950 text-slate-300'
                    : 'border-slate-200 bg-white text-slate-600'
                }`}
              >
                {round}
              </div>

              {isSelected ? (
                games.length > 0 ? (
                  games.map((game) => {
                    const predictedWinner = game.predicted_winner ?? 'TBD';
                    const advanceProbability =
                      typeof game.advance_probability === 'number'
                        ? Math.round(game.advance_probability * 100)
                        : null;
                    const homeHighlighted = predictedWinner === game.home_team;
                    const awayHighlighted = predictedWinner === game.away_team;
                    return (
                      <button
                        key={game.game_id}
                        type="button"
                        onClick={() => onSelectGame(game)}
                        className={`w-full rounded-2xl border p-4 text-left transition ${
                          isDarkMode
                            ? 'border-slate-800 bg-slate-950 hover:border-blue-500/60 hover:shadow-lg hover:shadow-blue-500/10'
                            : 'border-slate-200 bg-white hover:border-blue-500 hover:shadow-md'
                        }`}
                      >
                        <div className="space-y-2">
                          <TeamRow
                            team={game.away_team}
                            seed={game.away_seed}
                            isHighlighted={awayHighlighted}
                            mutedTextClass={mutedTextClass}
                            primaryTextClass={primaryTextClass}
                            isDarkMode={isDarkMode}
                          />
                          <TeamRow
                            team={game.home_team}
                            seed={game.home_seed}
                            isHighlighted={homeHighlighted}
                            mutedTextClass={mutedTextClass}
                            primaryTextClass={primaryTextClass}
                            isDarkMode={isDarkMode}
                          />
                        </div>
                        <div className="mt-4 flex items-center justify-between">
                          <div>
                            <div className={`text-[11px] uppercase ${mutedTextClass}`}>
                              Predicted winner
                            </div>
                            <div className={`text-sm font-semibold ${primaryTextClass}`}>
                              {predictedWinner}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className={`text-[11px] uppercase ${mutedTextClass}`}>
                              Advance probability
                            </div>
                            <div className={`text-sm font-semibold ${primaryTextClass}`}>
                              {advanceProbability !== null ? `${advanceProbability}%` : '—'}
                            </div>
                          </div>
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div
                    className={`rounded-2xl border border-dashed p-4 text-sm ${
                      isDarkMode
                        ? 'border-slate-800 text-slate-400'
                        : 'border-slate-200 text-slate-500'
                    }`}
                  >
                    No games listed for this round yet.
                  </div>
                )
              ) : (
                <div
                  className={`rounded-2xl border border-dashed p-4 text-sm ${
                    isDarkMode
                      ? 'border-slate-800 text-slate-500'
                      : 'border-slate-200 text-slate-400'
                  }`}
                >
                  Select {round} to view matchups.
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  </section>
);

export default PlayoffsBracket;

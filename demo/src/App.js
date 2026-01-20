import React, { useState, useEffect, useMemo } from 'react';
import { AlertCircle, TrendingUp, Users, Moon, Sun } from 'lucide-react';

function App() {
  const [games, setGames] = useState([]);
  const [selectedGame, setSelectedGame] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiUrl, setApiUrl] = useState('http://localhost:8001');
  const [currentWeek, setCurrentWeek] = useState(1);
  const [totalWeeks] = useState(18);
  const [currentPage, setCurrentPage] = useState(1);
  const [darkMode, setDarkMode] = useState(false);
  const pageSize = 6;

  // Fetch games by week
  const fetchGamesByWeek = async (week) => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/games/week/${week}`);
      if (response.ok) {
        const data = await response.json();
        setGames(data.games || []);
        setCurrentPage(1);
      }
    } catch (error) {
      console.error('Error fetching games:', error);
    }
    setLoading(false);
  };

  const fetchPrediction = async (game) => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          game_data: {
            game_id: game.game_id,
            home_team_name: game.home_team,
            away_team_name: game.away_team,
            game_time: game.game_date,
            is_dome: game.is_dome
          }
        })
      });

      if (response.ok) {
        const res = await response.json();
        const prediction = {
          winner: res.overall_winner,
          confidence: res.overall_confidence, // Map this correctly
          reasoning: res.consensus_reasoning
        };
        console.log('Prediction Response:', prediction);
        setSelectedGame({ ...game, prediction });
      }
    } catch (error) {
      console.error('Error fetching prediction:', error);
    }
    setLoading(false);
  };

  const handleWeekChange = (event) => {
    const nextWeek = Number(event.target.value);
    setCurrentWeek(nextWeek);
    fetchGamesByWeek(nextWeek);
  };

  useEffect(() => {
    fetchGamesByWeek(currentWeek);
  }, []);

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.70) return darkMode ? 'text-emerald-200 bg-emerald-500/20' : 'text-green-600 bg-green-50';
    if (confidence >= 0.60) return darkMode ? 'text-amber-200 bg-amber-500/20' : 'text-yellow-600 bg-yellow-50';
    return darkMode ? 'text-rose-200 bg-rose-500/20' : 'text-red-600 bg-red-50';
  };

  const formatTime = (timeString) => {
    const date = new Date(timeString);
    return date.toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  const totalPages = Math.max(1, Math.ceil(games.length / pageSize));
  const paginatedGames = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return games.slice(start, start + pageSize);
  }, [currentPage, games]);

  const goToPage = (page) => {
    setCurrentPage(page);
  };

  return (
    <div className={`min-h-screen ${darkMode ? 'bg-slate-950 text-slate-100' : 'bg-gray-50 text-gray-900'} p-6 transition-colors`}>
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setDarkMode((prev) => !prev)}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold shadow-sm transition ${
              darkMode
                ? 'bg-slate-800 text-slate-100 hover:bg-slate-700'
                : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {darkMode ? 'Light mode' : 'Dark mode'}
          </button>
          <span className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
            Connected to {apiUrl}
          </span>
        </div>
        {/* Header */}
        <div className={`rounded-2xl border p-6 shadow-sm ${darkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'}`}>
          <h1 className="text-3xl font-bold mb-2">
            NFL Predictions Dashboard
          </h1>
          <p className={darkMode ? 'text-slate-300' : 'text-gray-600'}>
            Multi-agent AI predictions for NFL games
          </p>
          
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className={`flex-1 rounded-xl border px-3 py-2 text-sm shadow-inner focus:outline-none focus:ring-2 ${
                darkMode
                  ? 'border-slate-700 bg-slate-950 text-slate-100 focus:ring-sky-500/40'
                  : 'border-gray-300 bg-white text-gray-900 focus:ring-blue-500/40'
              }`}
              placeholder="API URL"
            />
            <button
              onClick={() => fetchGamesByWeek(currentWeek)}
              className={`px-4 py-2 text-sm font-semibold rounded-xl transition ${
                darkMode
                  ? 'bg-sky-500/90 text-slate-900 hover:bg-sky-400'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              Refresh
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Games List */}
          <div className={`rounded-2xl border p-6 shadow-sm ${darkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'}`}>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
              <div>
                <h2 className="text-xl font-bold">Week {currentWeek} Games</h2>
                <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                  Pick a matchup for instant AI predictions.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <label htmlFor="week-select" className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                  Week
                </label>
                <select
                  id="week-select"
                  value={currentWeek}
                  onChange={handleWeekChange}
                  className={`rounded-xl border px-3 py-2 text-sm shadow-inner focus:outline-none focus:ring-2 ${
                    darkMode
                      ? 'border-slate-700 bg-slate-950 text-slate-100 focus:ring-sky-500/40'
                      : 'border-gray-300 bg-white text-gray-900 focus:ring-blue-500/40'
                  }`}
                >
                  {Array.from({ length: totalWeeks }, (_, index) => {
                    const week = index + 1;
                    return (
                      <option key={week} value={week}>
                        Week {week}
                      </option>
                    );
                  })}
                </select>
              </div>
            </div>
            
            {loading && games.length === 0 ? (
              <div className={`text-center py-8 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Loading games...</div>
            ) : games.length === 0 ? (
              <div className={`text-center py-8 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                No games found for week {currentWeek}
              </div>
            ) : (
              <div className="space-y-3">
                {paginatedGames.map((game) => (
                  <div
                    key={game.game_id}
                    onClick={() => fetchPrediction(game)}
                    className={`cursor-pointer rounded-2xl border p-4 transition hover:-translate-y-0.5 hover:shadow-lg ${
                      darkMode
                        ? 'border-slate-800 bg-slate-950/60 hover:border-sky-500/60'
                        : 'border-gray-200 bg-white hover:border-blue-500'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-semibold">
                        {game.away_team} @ {game.home_team}
                      </div>
                      {game.is_dome && (
                        <span className={`text-xs px-2 py-1 rounded-full ${
                          darkMode ? 'bg-slate-800 text-slate-300' : 'bg-gray-100 text-gray-600'
                        }`}>
                          DOME
                        </span>
                      )}
                    </div>
                    <div className={`text-sm ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>
                      {formatTime(game.game_date)}
                    </div>
                    <div className={`text-xs mt-1 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                      {game.venue}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {games.length > 0 && (
              <div className="mt-6 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => goToPage(Math.max(1, currentPage - 1))}
                  disabled={currentPage === 1}
                  className={`px-3 py-2 text-sm font-semibold rounded-lg border transition disabled:opacity-50 disabled:cursor-not-allowed ${
                    darkMode
                      ? 'border-slate-700 text-slate-200 hover:bg-slate-800'
                      : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  Previous
                </button>
                <span className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  type="button"
                  onClick={() => goToPage(Math.min(totalPages, currentPage + 1))}
                  disabled={currentPage === totalPages}
                  className={`px-3 py-2 text-sm font-semibold rounded-lg border transition disabled:opacity-50 disabled:cursor-not-allowed ${
                    darkMode
                      ? 'border-slate-700 text-slate-200 hover:bg-slate-800'
                      : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  Next
                </button>
              </div>
            )}
          </div>

          {/* Prediction Panel - Same as artifact */}
          <div className={`rounded-2xl border p-6 shadow-sm ${darkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'}`}>
            <h2 className="text-xl font-bold mb-4">Prediction Analysis</h2>
            
            {loading && selectedGame ? (
              <div className={`text-center py-8 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Analyzing game...</div>
            ) : selectedGame?.prediction ? (
              <div className="space-y-4">
                <div className={`border-b pb-4 ${darkMode ? 'border-slate-800' : 'border-gray-200'}`}>
                  <h3 className="text-lg font-bold">
                    {selectedGame.away_team} @ {selectedGame.home_team}
                  </h3>
                  <p className={`text-sm ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>
                    {formatTime(selectedGame.game_date)}
                  </p>
                </div>

                <div className={`rounded-2xl border p-4 ${
                  darkMode ? 'bg-sky-500/10 border-sky-500/30' : 'bg-blue-50 border-blue-200'
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className={`w-5 h-5 ${darkMode ? 'text-sky-300' : 'text-blue-600'}`} />
                    <span className={`font-semibold ${darkMode ? 'text-sky-100' : 'text-blue-900'}`}>Predicted Winner</span>
                  </div>
                  <div className={`text-2xl font-bold ${darkMode ? 'text-sky-100' : 'text-blue-900'}`}>
                    {selectedGame.prediction.winner}
                  </div>
                  <div className={`inline-block mt-2 px-3 py-1 rounded-full text-sm font-semibold ${
                    getConfidenceColor(selectedGame.prediction.confidence)
                  }`}>
                    {(selectedGame.prediction.confidence * 100).toFixed(0)}% Confidence
                  </div>
                </div>

                <div className={`rounded-2xl border p-4 ${darkMode ? 'border-slate-800' : 'border-gray-200'}`}>
                  <div className="flex items-center gap-2 mb-3">
                    <AlertCircle className={`w-5 h-5 ${darkMode ? 'text-slate-300' : 'text-gray-600'}`} />
                    <span className="font-semibold">Analysis</span>
                  </div>
                  <p className={`text-sm ${darkMode ? 'text-slate-200' : 'text-gray-700'}`}>
                    {selectedGame.prediction.reasoning}
                  </p>
                </div>
              </div>
            ) : (
              <div className={`text-center py-12 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                <Users className={`w-12 h-12 mx-auto mb-3 ${darkMode ? 'text-slate-500' : 'text-gray-400'}`} />
                <p>Select a game to view predictions</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

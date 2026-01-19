import React, { useState, useEffect } from 'react';
import { AlertCircle, TrendingUp, Cloud, Users, Target } from 'lucide-react';

function App() {
  const [games, setGames] = useState([]);
  const [selectedGame, setSelectedGame] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiUrl, setApiUrl] = useState('https://nfl-predictor-system-production.up.railway.app');
  const [currentWeek, setCurrentWeek] = useState(1);
  const [totalWeeks] = useState(18);

  // Fetch games by week
  const fetchGamesByWeek = async (week) => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/games/week/${week}`);
      if (response.ok) {
        const data = await response.json();
        setGames(data.games || []);
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

  const goToNextWeek = () => {
    if (currentWeek < totalWeeks) {
      const nextWeek = currentWeek + 1;
      setCurrentWeek(nextWeek);
      fetchGamesByWeek(nextWeek);
    }
  };

  const goToPreviousWeek = () => {
    if (currentWeek > 1) {
      const prevWeek = currentWeek - 1;
      setCurrentWeek(prevWeek);
      fetchGamesByWeek(prevWeek);
    }
  };

  useEffect(() => {
    fetchGamesByWeek(currentWeek);
  }, []);

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.70) return 'text-green-600 bg-green-50';
    if (confidence >= 0.60) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
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

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            NFL Predictions Dashboard
          </h1>
          <p className="text-gray-600">
            Multi-agent AI predictions for NFL games
          </p>
          
          <div className="mt-4 flex gap-2 items-center">
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
              placeholder="API URL"
            />
            <button
              onClick={() => fetchGamesByWeek(currentWeek)}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
            >
              Refresh
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Games List */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900">Week {currentWeek} Games</h2>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={goToPreviousWeek}
                  disabled={currentWeek === 1}
                  className="px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  ← Prev
                </button>
                <span className="text-sm text-gray-600">
                  {currentWeek} / {totalWeeks}
                </span>
                <button
                  onClick={goToNextWeek}
                  disabled={currentWeek === totalWeeks}
                  className="px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next →
                </button>
              </div>
            </div>
            
            {loading && games.length === 0 ? (
              <div className="text-center py-8 text-gray-500">Loading games...</div>
            ) : games.length === 0 ? (
              <div className="text-center py-8 text-gray-500">No games found for week {currentWeek}</div>
            ) : (
              <div className="space-y-3">
                {games.map((game) => (
                  <div
                    key={game.game_id}
                    onClick={() => fetchPrediction(game)}
                    className="border border-gray-200 rounded-lg p-4 hover:border-blue-500 hover:shadow-md cursor-pointer transition"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-semibold text-gray-900">
                        {game.away_team} @ {game.home_team}
                      </div>
                      {game.is_dome && (
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                          DOME
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-600">
                      {formatTime(game.game_date)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {game.venue}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Prediction Panel - Same as artifact */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Prediction Analysis</h2>
            
            {loading && selectedGame ? (
              <div className="text-center py-8 text-gray-500">Analyzing game...</div>
            ) : selectedGame?.prediction ? (
              <div className="space-y-4">
                <div className="border-b pb-4">
                  <h3 className="text-lg font-bold text-gray-900">
                    {selectedGame.away_team} @ {selectedGame.home_team}
                  </h3>
                  <p className="text-sm text-gray-600">{formatTime(selectedGame.game_date)}</p>
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-5 h-5 text-blue-600" />
                    <span className="font-semibold text-blue-900">Predicted Winner</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-900">
                    {selectedGame.prediction.winner}
                  </div>
                  <div className={`inline-block mt-2 px-3 py-1 rounded-full text-sm font-semibold ${
                    getConfidenceColor(selectedGame.prediction.confidence)
                  }`}>
                    {(selectedGame.prediction.confidence * 100).toFixed(0)}% Confidence
                  </div>
                </div>

                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertCircle className="w-5 h-5 text-gray-600" />
                    <span className="font-semibold text-gray-900">Analysis</span>
                  </div>
                  <p className="text-sm text-gray-700">
                    {selectedGame.prediction.reasoning}
                  </p>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <Users className="w-12 h-12 mx-auto mb-3 text-gray-400" />
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

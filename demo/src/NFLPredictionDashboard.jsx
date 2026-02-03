import React, { useState, useEffect } from 'react';
import { AlertCircle, TrendingUp, Cloud, Users, Target } from 'lucide-react';

const NFLPredictionsDashboard = () => {
  const [games, setGames] = useState([]);
  const [selectedGame, setSelectedGame] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiUrl, setApiUrl] = useState('http://localhost:8080');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTeam, setSelectedTeam] = useState('all');
  const [selectedWeek, setSelectedWeek] = useState('all');
  const [selectedSeason, setSelectedSeason] = useState('all');
  const [selectedTime, setSelectedTime] = useState('all');
  const [sortBy, setSortBy] = useState('week');
  const [predictionCache, setPredictionCache] = useState({});
  const [sortMode, setSortMode] = useState('week');

  // Fetch upcoming games
  const fetchGames = async () => {
    setLoading(true);
    try {
      // Mock data for demonstration
      const mockGames = [
        {
          game_id: 1,
          season: '2024-2025',
          week: 1,
          home_team: 'Bills',
          away_team: 'Dolphins',
          game_time: '2024-01-21T13:00:00',
          venue: 'Highmark Stadium',
          is_dome: false
        },
        {
          game_id: 2,
          season: '2024-2025',
          week: 1,
          home_team: 'Packers',
          away_team: 'Vikings',
          game_time: '2024-01-21T16:30:00',
          venue: 'Lambeau Field',
          is_dome: false
        },
        {
          game_id: 3,
          season: '2024-2025',
          week: 1,
          home_team: 'Cowboys',
          away_team: 'Eagles',
          game_time: '2024-01-21T20:15:00',
          venue: 'AT&T Stadium',
          is_dome: true
        },
        {
          game_id: 4,
          season: '2025-2026',
          week: 2,
          home_team: 'Chiefs',
          away_team: 'Ravens',
          game_time: '2025-09-14T13:00:00',
          venue: 'Arrowhead Stadium',
          is_dome: false
        },
        {
          game_id: 5,
          season: '2025-2026',
          week: 2,
          home_team: '49ers',
          away_team: 'Seahawks',
          game_time: '2025-09-14T16:25:00',
          venue: 'Levi\'s Stadium',
          is_dome: false
        },
        {
          game_id: 6,
          season: '2025-2026',
          week: 3,
          home_team: 'Jets',
          away_team: 'Patriots',
          game_time: '2025-09-21T20:20:00',
          venue: 'MetLife Stadium',
          is_dome: false
        }
      ];
      setGames(mockGames);
    } catch (error) {
      console.error('Error fetching games:', error);
    }
    setLoading(false);
  };

  // Fetch prediction for a specific game
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
            game_time: game.game_time,
            is_dome: game.is_dome
          }
        })
      });

      if (response.ok) {
        const prediction = await response.json();
        setSelectedGame({ ...game, prediction });
        setPredictionCache((prev) => ({
          ...prev,
          [game.game_id]: prediction
        }));
      } else {
        console.error('Prediction failed');
      }
    } catch (error) {
      console.error('Error fetching prediction:', error);
      // Show mock prediction for demo
      setSelectedGame({
        ...game,
        prediction: {
          winner: game.home_team,
          confidence: 0.67,
          reasoning: 'Mock prediction - API connection failed',
          weather: { temp: 35, wind: 12, conditions: 'Clear' },
          props: {
            anytime_tds: [
              { player: 'Josh Allen', position: 'QB', probability: 0.35 },
              { player: 'Stefon Diggs', position: 'WR', probability: 0.28 }
            ]
          }
        }
      });
      setPredictionCache((prev) => ({
        ...prev,
        [game.game_id]: {
          winner: game.home_team,
          confidence: 0.67
        }
      }));
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchGames();
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

  const getWeekNumber = (timeString) => {
    const date = new Date(timeString);
    const startOfYear = new Date(date.getFullYear(), 0, 1);
    const dayOfYear = Math.floor((date - startOfYear) / 86400000) + 1;
    return Math.ceil(dayOfYear / 7);
  };

  const getTimeBucket = (timeString) => {
    const hour = new Date(timeString).getHours();
    if (hour < 12) return 'morning';
    if (hour < 18) return 'afternoon';
    return 'evening';
  };

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const teams = Array.from(
    new Set(games.flatMap((game) => [game.home_team, game.away_team]))
  ).sort();
  const weeks = Array.from(new Set(games.map((game) => game.week))).sort(
    (a, b) => a - b
  );
  const seasons = Array.from(new Set(games.map((game) => game.season))).sort();

  const filteredGames = games
    .filter((game) => {
      if (selectedTeam !== 'all') {
        const matchesTeam =
          game.home_team === selectedTeam || game.away_team === selectedTeam;
        if (!matchesTeam) return false;
      }

      if (selectedWeek !== 'all' && game.week !== Number(selectedWeek)) {
        return false;
      }

      if (selectedSeason !== 'all' && game.season !== selectedSeason) {
        return false;
      }

      if (selectedTime !== 'all' && getTimeBucket(game.game_time) !== selectedTime) {
        return false;
      }

      if (normalizedQuery) {
        const matchup = `${game.away_team} @ ${game.home_team}`.toLowerCase();
        if (!matchup.includes(normalizedQuery)) return false;
      }

      return true;
    })
    .sort((a, b) => {
      if (sortBy === 'team') {
        const matchupA = `${a.away_team} @ ${a.home_team}`.toLowerCase();
        const matchupB = `${b.away_team} @ ${b.home_team}`.toLowerCase();
        return matchupA.localeCompare(matchupB);
      }

      if (sortBy === 'confidence') {
        const confidenceA = predictionCache[a.game_id]?.confidence ?? -1;
        const confidenceB = predictionCache[b.game_id]?.confidence ?? -1;
        return confidenceB - confidenceA;
      }

      if (a.week !== b.week) {
        return a.week - b.week;
      }

      return new Date(a.game_time) - new Date(b.game_time);
  const teamOptions = Array.from(
    new Set(games.flatMap((game) => [game.home_team, game.away_team]))
  ).sort((a, b) => a.localeCompare(b));

  const weekOptions = Array.from(
    new Set(games.map((game) => getWeekNumber(game.game_time)))
  ).sort((a, b) => a - b);

  const filteredGames = games
    .filter((game) => {
      const matchup = `${game.away_team} ${game.home_team}`.toLowerCase();
      return matchup.includes(searchQuery.trim().toLowerCase());
    })
    .filter((game) => {
      if (selectedTeam === 'all') return true;
      return game.home_team === selectedTeam || game.away_team === selectedTeam;
    })
    .filter((game) => {
      if (selectedWeek === 'all') return true;
      return getWeekNumber(game.game_time).toString() === selectedWeek;
    })
    .filter((game) => {
      if (selectedTime === 'all') return true;
      return getTimeBucket(game.game_time) === selectedTime;
    })
    .sort((a, b) => {
      if (sortMode === 'team') {
        const matchupA = `${a.away_team} @ ${a.home_team}`;
        const matchupB = `${b.away_team} @ ${b.home_team}`;
        return matchupA.localeCompare(matchupB);
      }
      if (sortMode === 'confidence') {
        const confidenceA = a.prediction?.confidence ?? 0;
        const confidenceB = b.prediction?.confidence ?? 0;
        return confidenceB - confidenceA;
      }
      const weekA = getWeekNumber(a.game_time);
      const weekB = getWeekNumber(b.game_time);
      return weekA - weekB;
    });

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
          
          {/* API URL Config */}
          <div className="mt-4 flex gap-2">
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
              placeholder="API URL"
            />
            <button
              onClick={fetchGames}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
            >
              Refresh Games
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Games List */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Upcoming Games</h2>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Search teams
            <div className="border border-gray-200 rounded-lg p-4 mb-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase mb-2">
                  Search
                </label>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search team or opponent"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 uppercase mb-2">
                    Team
                  </label>
                  <select
                    value={selectedTeam}
                    onChange={(event) => setSelectedTeam(event.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="all">All Teams</option>
                    {teamOptions.map((team) => (
                      <option key={team} value={team}>
                        {team}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Season
                  </label>
                  <select
                    value={selectedSeason}
                    onChange={(e) => setSelectedSeason(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="all">All seasons</option>
                    {seasons.map((season) => (
                      <option key={season} value={season}>
                        {season}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Week
                  </label>
                  <select
                    value={selectedWeek}
                    onChange={(event) => setSelectedWeek(event.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="all">All Weeks</option>
                    {weekOptions.map((week) => (
                      <option key={week} value={week}>
                        Week {week}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 uppercase mb-2">
                    Time
                  </label>
                  <select
                    value={selectedTime}
                    onChange={(e) => setSelectedTime(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="all">All times</option>
                    <option value="morning">Morning</option>
                    <option value="afternoon">Afternoon</option>
                    <option value="evening">Evening</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Sort by
                </label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                >
                  <option value="week">Week order</option>
                  <option value="team">Team (A-Z)</option>
                  <option value="confidence">Confidence</option>
                </select>
              </div>
            </div>
            
            {loading && games.length === 0 ? (
              <div className="text-center py-8 text-gray-500">Loading games...</div>
            ) : (
              <div className="space-y-3">
                {filteredGames.length === 0 ? (
                  <div className="text-center py-6 text-sm text-gray-500">
                    No games match your filters.
                  </div>
                ) : null}
                {filteredGames.map((game) => (
                  <div
                    key={game.game_id}
                    onClick={() => fetchPrediction(game)}
                    className="border border-gray-200 rounded-lg p-4 hover:border-blue-500 hover:shadow-md cursor-pointer transition"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-semibold text-gray-900">
                        {game.away_team} @ {game.home_team}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">
                          Week {game.week}
                        </span>
                        <span className="text-xs text-gray-400">•</span>
                        <span className="text-xs text-gray-500">{game.season}</span>
                        {game.is_dome && (
                          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                            DOME
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-sm text-gray-600">
                      {formatTime(game.game_time)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {game.venue}
                    </div>
                    {predictionCache[game.game_id]?.confidence ? (
                      <div className="mt-2 text-xs text-gray-500">
                        Confidence: {(predictionCache[game.game_id].confidence * 100).toFixed(0)}%
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Prediction Details */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Prediction Analysis</h2>
            
            {loading && selectedGame ? (
              <div className="text-center py-8 text-gray-500">Analyzing game...</div>
            ) : selectedGame ? (
              <div className="space-y-4">
                {/* Game Header */}
                <div className="border-b pb-4">
                  <h3 className="text-lg font-bold text-gray-900">
                    {selectedGame.away_team} @ {selectedGame.home_team}
                  </h3>
                  <p className="text-sm text-gray-600">{formatTime(selectedGame.game_time)}</p>
                </div>

                {/* Predicted Winner */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-5 h-5 text-blue-600" />
                    <span className="font-semibold text-blue-900">Predicted Winner</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-900">
                    {selectedGame.prediction?.winner || 'N/A'}
                  </div>
                  <div className={`inline-block mt-2 px-3 py-1 rounded-full text-sm font-semibold ${
                    getConfidenceColor(selectedGame.prediction?.confidence || 0)
                  }`}>
                    {((selectedGame.prediction?.confidence || 0) * 100).toFixed(0)}% Confidence
                  </div>
                </div>

                {/* Weather Conditions */}
                {selectedGame.prediction?.weather && (
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Cloud className="w-5 h-5 text-gray-600" />
                      <span className="font-semibold text-gray-900">Weather Impact</span>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <div className="text-gray-600">Temperature</div>
                        <div className="font-semibold">{selectedGame.prediction.weather.temp}°F</div>
                      </div>
                      <div>
                        <div className="text-gray-600">Wind</div>
                        <div className="font-semibold">{selectedGame.prediction.weather.wind} mph</div>
                      </div>
                      <div>
                        <div className="text-gray-600">Conditions</div>
                        <div className="font-semibold">{selectedGame.prediction.weather.conditions}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Reasoning */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertCircle className="w-5 h-5 text-gray-600" />
                    <span className="font-semibold text-gray-900">Analysis</span>
                  </div>
                  <p className="text-sm text-gray-700">
                    {selectedGame.prediction?.reasoning || 'No analysis available'}
                  </p>
                </div>

                {/* Props Predictions */}
                {selectedGame.prediction?.props?.anytime_tds && (
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Target className="w-5 h-5 text-gray-600" />
                      <span className="font-semibold text-gray-900">Anytime TD Scorers</span>
                    </div>
                    <div className="space-y-2">
                      {selectedGame.prediction.props.anytime_tds.map((player, idx) => (
                        <div key={idx} className="flex items-center justify-between text-sm">
                          <div>
                            <span className="font-medium">{player.player}</span>
                            <span className="text-gray-500 ml-2">({player.position})</span>
                          </div>
                          <div className={`px-2 py-1 rounded ${
                            player.probability >= 0.30 ? 'bg-green-100 text-green-700' :
                            player.probability >= 0.20 ? 'bg-yellow-100 text-yellow-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {(player.probability * 100).toFixed(0)}%
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <Users className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                <p>Select a game to view predictions</p>
              </div>
            )}
          </div>
        </div>

        {/* Agent Status Footer */}
        <div className="mt-6 bg-white rounded-lg shadow-sm p-4">
          <div className="flex items-center justify-between text-sm">
            <div className="flex gap-4">
              <span className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                Weather Agent
              </span>
              <span className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                Data Collector
              </span>
              <span className="flex items-center gap-2">
                <div className="w-2 h-2 bg-gray-300 rounded-full"></div>
                Market Intelligence
              </span>
            </div>
            <div className="text-gray-500">
              Last updated: {new Date().toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NFLPredictionsDashboard;

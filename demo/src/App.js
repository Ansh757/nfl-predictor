import React, { useState, useEffect, useMemo } from 'react';
import {
  GamesSection,
  HeaderSection,
  PaginationControls,
  PredictionSection
} from './components/DashboardSections';

function App() {
  const [games, setGames] = useState([]);
  const [selectedGame, setSelectedGame] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiUrl, setApiUrl] = useState('https://nfl-predictor-system-production.up.railway.app');
  const [currentWeek, setCurrentWeek] = useState(1);
  const [totalWeeks] = useState(18);
  const [currentPage, setCurrentPage] = useState(1);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const pageSize = 4;

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

  const handleWeekChange = (event) => {
    const nextWeek = Number(event.target.value);
    setCurrentWeek(nextWeek);
    setCurrentPage(1);
    fetchGamesByWeek(nextWeek);
  };

  useEffect(() => {
    fetchGamesByWeek(currentWeek);
  }, []);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(games.length / pageSize));
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [games, currentPage]);

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

  const totalPages = Math.max(1, Math.ceil(games.length / pageSize));
  const paginatedGames = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return games.slice(start, start + pageSize);
  }, [games, currentPage]);
  const visibleRangeStart = games.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const visibleRangeEnd = Math.min(currentPage * pageSize, games.length);
  const surfaceClass = isDarkMode
    ? 'bg-slate-900/80 border border-slate-800 shadow-lg shadow-black/30'
    : 'bg-white border border-slate-200 shadow-sm';
  const mutedTextClass = isDarkMode ? 'text-slate-400' : 'text-slate-600';
  const primaryTextClass = isDarkMode ? 'text-slate-100' : 'text-slate-900';
  const inputClass = isDarkMode
    ? 'border-slate-700 bg-slate-900 text-slate-100 placeholder:text-slate-500 focus:border-blue-500'
    : 'border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-blue-500';
  const chipClass = isDarkMode
    ? 'bg-slate-800 text-slate-200'
    : 'bg-slate-100 text-slate-600';

  return (
    <div className={`min-h-screen p-6 transition-colors ${isDarkMode ? 'bg-slate-950' : 'bg-slate-50'}`}>
      <div className="max-w-7xl mx-auto space-y-6">
        <HeaderSection
          apiUrl={apiUrl}
          inputClass={inputClass}
          isDarkMode={isDarkMode}
          mutedTextClass={mutedTextClass}
          primaryTextClass={primaryTextClass}
          surfaceClass={surfaceClass}
          onApiUrlChange={(event) => setApiUrl(event.target.value)}
          onRefresh={() => fetchGamesByWeek(currentWeek)}
          onToggleDarkMode={() => setIsDarkMode((prev) => !prev)}
        />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <GamesSection
              chipClass={chipClass}
              currentWeek={currentWeek}
              formatTime={formatTime}
              games={games}
              inputClass={inputClass}
              isDarkMode={isDarkMode}
              loading={loading}
              mutedTextClass={mutedTextClass}
              paginatedGames={paginatedGames}
              primaryTextClass={primaryTextClass}
              surfaceClass={surfaceClass}
              totalWeeks={totalWeeks}
              visibleRangeEnd={visibleRangeEnd}
              visibleRangeStart={visibleRangeStart}
              onSelectGame={fetchPrediction}
              onWeekChange={handleWeekChange}
            />
            <PaginationControls
              currentPage={currentPage}
              isDarkMode={isDarkMode}
              mutedTextClass={mutedTextClass}
              totalPages={totalPages}
              onNext={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
              onPrev={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
            />
          </div>

          <PredictionSection
            formatTime={formatTime}
            getConfidenceColor={getConfidenceColor}
            isDarkMode={isDarkMode}
            loading={loading}
            mutedTextClass={mutedTextClass}
            primaryTextClass={primaryTextClass}
            selectedGame={selectedGame}
            surfaceClass={surfaceClass}
          />
        </div>
      </div>
    </div>
  );
}

export default App;

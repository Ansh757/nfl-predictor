import React, { useState, useEffect, useMemo } from 'react';
import { Activity, BarChart3, CloudRain, Newspaper } from 'lucide-react';
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
  const [predictionSummaries, setPredictionSummaries] = useState({});
  const [predictionLoading, setPredictionLoading] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTeam, setSelectedTeam] = useState('all');
  const [selectedTime, setSelectedTime] = useState('all');
  const [sortBy, setSortBy] = useState('week-asc');
  const pageSize = 4;
  const agentDefinitions = useMemo(
    () => [
      {
        key: 'weather',
        label: 'Weather',
        description: 'Wind, precipitation, and temperature signals',
        icon: CloudRain
      },
      {
        key: 'injuries',
        label: 'Injuries',
        description: 'Lineup health and late-week availability',
        icon: Activity
      },
      {
        key: 'market',
        label: 'Market',
        description: 'Sharp money, line movement, and consensus splits',
        icon: BarChart3
      },
      {
        key: 'news',
        label: 'News',
        description: 'Beat reports, momentum, and roster updates',
        icon: Newspaper
      }
    ],
    []
  );

  const normalizeAgentKey = (agentName = '') => {
    const normalized = agentName.toLowerCase();
    if (normalized.includes('weather')) return 'weather';
    if (normalized.includes('market')) return 'market';
    if (normalized.includes('news')) return 'news';
    if (normalized.includes('data') || normalized.includes('injury')) return 'injuries';
    return 'injuries';
  };

  const buildPredictionSummary = (res) => {
    const agentPredictions = res?.agent_predictions ?? [];
    const totalAgents = agentPredictions.length || agentDefinitions.length;
    const winner = res?.overall_winner ?? 'Awaiting pick';
    const confidence = res?.overall_confidence ?? 0;
    const alignedAgents = agentPredictions.filter(
      (prediction) => prediction.predicted_winner === winner
    ).length;

    const agentInsights = agentDefinitions.reduce((acc, agent) => {
      acc[agent.key] = {
        label: agent.label,
        description: agent.description,
        status: 'Awaiting data'
      };
      return acc;
    }, {});

    agentPredictions.forEach((prediction) => {
      const key = normalizeAgentKey(prediction.agent_name);
      agentInsights[key] = {
        label: agentInsights[key]?.label ?? prediction.agent_name,
        description: agentInsights[key]?.description ?? '',
        predictedWinner: prediction.predicted_winner,
        confidence: prediction.confidence,
        reasoning: prediction.reasoning,
        isAligned: prediction.predicted_winner === winner
      };
    });

    return {
      winner,
      confidence,
      reasoning: res?.consensus_reasoning ?? 'Consensus details are pending.',
      consensus: {
        count: alignedAgents,
        total: totalAgents,
        label: `${alignedAgents}/${totalAgents} agents`
      },
      agentInsights
    };
  };

  const requestPrediction = async (game) => {
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

      if (!response.ok) {
        return null;
      }

      const res = await response.json();
      return buildPredictionSummary(res);
    } catch (error) {
      console.error('Error fetching prediction:', error);
      return null;
    }
  };

  const preloadPredictions = async (gamesList) => {
    if (!gamesList.length) return;

    setPredictionLoading((prev) => {
      const next = { ...prev };
      gamesList.forEach((game) => {
        next[game.game_id] = true;
      });
      return next;
    });

    const results = await Promise.all(
      gamesList.map(async (game) => ({
        gameId: game.game_id,
        summary: await requestPrediction(game)
      }))
    );

    setPredictionSummaries((prev) => {
      const next = { ...prev };
      results.forEach(({ gameId, summary }) => {
        if (summary) {
          next[gameId] = summary;
        }
      });
      return next;
    });

    setPredictionLoading((prev) => {
      const next = { ...prev };
      results.forEach(({ gameId }) => {
        next[gameId] = false;
      });
      return next;
    });
  };

  // Fetch games by week
  const fetchGamesByWeek = async (week) => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/games/week/${week}`);
      if (response.ok) {
        const data = await response.json();
        const nextGames = data.games || [];
        setGames(nextGames);
        setPredictionLoading({});
        await preloadPredictions(nextGames);
      }
    } catch (error) {
      console.error('Error fetching games:', error);
    }
    setLoading(false);
  };

  const fetchPrediction = async (game) => {
    setLoading(true);
    setPredictionLoading((prev) => ({ ...prev, [game.game_id]: true }));
    const prediction = await requestPrediction(game);
    if (prediction) {
      setPredictionSummaries((prev) => ({ ...prev, [game.game_id]: prediction }));
      setSelectedGame({ ...game, prediction });
    }
    setPredictionLoading((prev) => ({ ...prev, [game.game_id]: false }));
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
    const nextTotalPages = Math.max(1, Math.ceil(filteredGames.length / pageSize));
    if (currentPage > nextTotalPages) {
      setCurrentPage(nextTotalPages);
    }
  }, [filteredGames, currentPage]);

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.70) return 'text-green-600 bg-green-50';
    if (confidence >= 0.60) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getTimeBucket = (timeString) => {
    const hour = new Date(timeString).getHours();
    if (hour < 12) return 'morning';
    if (hour < 18) return 'afternoon';
    return 'evening';
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

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const teamOptions = useMemo(
    () =>
      Array.from(new Set(games.flatMap((game) => [game.home_team, game.away_team]))).sort(),
    [games]
  );

  const filteredGames = useMemo(
    () =>
      games
        .filter((game) => {
          if (selectedTeam !== 'all') {
            return game.home_team === selectedTeam || game.away_team === selectedTeam;
          }
          return true;
        })
        .filter((game) => {
          if (selectedTime === 'all') return true;
          return getTimeBucket(game.game_date) === selectedTime;
        })
        .filter((game) => {
          if (!normalizedQuery) return true;
          const matchup = `${game.away_team} @ ${game.home_team}`.toLowerCase();
          return matchup.includes(normalizedQuery);
        })
        .sort((a, b) => {
          if (sortBy === 'team') {
            const teamA = `${a.home_team} ${a.away_team}`;
            const teamB = `${b.home_team} ${b.away_team}`;
            return teamA.localeCompare(teamB);
          }

          if (sortBy === 'matchup') {
            const matchupA = `${a.away_team} @ ${a.home_team}`;
            const matchupB = `${b.away_team} @ ${b.home_team}`;
            return matchupA.localeCompare(matchupB);
          }

          if (sortBy === 'confidence') {
            const confidenceA = predictionSummaries[a.game_id]?.confidence ?? -1;
            const confidenceB = predictionSummaries[b.game_id]?.confidence ?? -1;
            return confidenceB - confidenceA;
          }

          const weekOrder = sortBy === 'week-desc' ? -1 : 1;
          const weekA = a.week ?? currentWeek;
          const weekB = b.week ?? currentWeek;
          if (weekA !== weekB) {
            return (weekA - weekB) * weekOrder;
          }

          return (new Date(a.game_date) - new Date(b.game_date)) * weekOrder;
        }),
    [games, selectedTeam, selectedTime, normalizedQuery, sortBy, predictionSummaries, currentWeek]
  );

  const totalPages = Math.max(1, Math.ceil(filteredGames.length / pageSize));
  const paginatedGames = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredGames.slice(start, start + pageSize);
  }, [filteredGames, currentPage]);
  const visibleRangeStart =
    filteredGames.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const visibleRangeEnd = Math.min(currentPage * pageSize, filteredGames.length);

  useEffect(() => {
    const nextTotalPages = Math.max(1, Math.ceil(filteredGames.length / pageSize));
    if (currentPage > nextTotalPages) {
      setCurrentPage(nextTotalPages);
    }
  }, [filteredGames, currentPage, pageSize]);
  
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
  const agentChipClass = isDarkMode
    ? 'border-slate-700 bg-slate-900 text-slate-200 hover:border-blue-400/60'
    : 'border-slate-200 bg-white text-slate-600 hover:border-blue-400';
  const agentChipActiveClass = isDarkMode
    ? 'border-blue-400/60 bg-blue-500/20 text-blue-100'
    : 'border-blue-200 bg-blue-50 text-blue-700';

  const handleScrollToAgent = (agentKey) => {
    const section = document.getElementById(`agent-${agentKey}`);
    if (section) {
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

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
              agentChipActiveClass={agentChipActiveClass}
              agentChipClass={agentChipClass}
              agentDefinitions={agentDefinitions}
              chipClass={chipClass}
              currentWeek={currentWeek}
              formatTime={formatTime}
              games={filteredGames}
              getConfidenceColor={getConfidenceColor}
              inputClass={inputClass}
              isDarkMode={isDarkMode}
              loading={loading}
              mutedTextClass={mutedTextClass}
              paginatedGames={paginatedGames}
              predictionLoading={predictionLoading}
              predictionSummaries={predictionSummaries}
              primaryTextClass={primaryTextClass}
              searchQuery={searchQuery}
              selectedTeam={selectedTeam}
              selectedTime={selectedTime}
              sortBy={sortBy}
              teamOptions={teamOptions}
              surfaceClass={surfaceClass}
              totalWeeks={totalWeeks}
              visibleRangeEnd={visibleRangeEnd}
              visibleRangeStart={visibleRangeStart}
              onAgentChipClick={handleScrollToAgent}
              onSearchChange={(event) => {
                setSearchQuery(event.target.value);
                setCurrentPage(1);
              }}
              onSortChange={(event) => setSortBy(event.target.value)}
              onSelectGame={fetchPrediction}
              onTeamChange={(event) => {
                setSelectedTeam(event.target.value);
                setCurrentPage(1);
              }}
              onTimeChange={(event) => {
                setSelectedTime(event.target.value);
                setCurrentPage(1);
              }}
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
            agentDefinitions={agentDefinitions}
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

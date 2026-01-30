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

  const getGameSeed = (game) =>
    `${game.game_id}-${game.home_team}-${game.away_team}`
      .split('')
      .reduce((acc, char) => acc + char.charCodeAt(0), 0);

  const buildFallbackPrediction = (game) => {
    const seed = getGameSeed(game);
    const winner = seed % 2 === 0 ? game.home_team : game.away_team;
    const confidence = 0.58 + ((seed % 18) / 100);
    const alignedCount = Math.max(2, (seed % 3) + 2);
    const total = agentDefinitions.length;

    const agentInsights = agentDefinitions.reduce((acc, agent, index) => {
      const isAligned = index < alignedCount;
      acc[agent.key] = {
        label: agent.label,
        description: agent.description,
        predictedWinner: isAligned ? winner : winner === game.home_team ? game.away_team : game.home_team,
        confidence: Math.min(0.78, confidence + (index % 2 === 0 ? 0.04 : -0.03)),
        reasoning: `${agent.label} signals lean toward ${isAligned ? winner : 'the other side'} based on demo inputs.`,
        isAligned
      };
      return acc;
    }, {});

    return {
      winner,
      confidence,
      reasoning: `Demo consensus: ${alignedCount}/${total} agents favor ${winner}.`,
      consensus: {
        count: alignedCount,
        total,
        label: `${alignedCount}/${total} agents`
      },
      agentInsights
    };
  };

  const hydratePredictionSummaries = (gamesList) => {
    setPredictionSummaries((prev) => {
      const next = { ...prev };
      gamesList.forEach((game) => {
        if (!next[game.game_id]) {
          next[game.game_id] = buildFallbackPrediction(game);
        }
      });
      return next;
    });
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

  // Fetch games by week
  const fetchGamesByWeek = async (week) => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/games/week/${week}`);
      if (response.ok) {
        const data = await response.json();
        const nextGames = data.games || [];
        setGames(nextGames);
        hydratePredictionSummaries(nextGames);
      } else {
        throw new Error('Unable to load games');
      }
    } catch (error) {
      console.error('Error fetching games:', error);
      const mockGames = [
        {
          game_id: 501,
          home_team: 'Bills',
          away_team: 'Dolphins',
          game_date: '2024-01-21T13:00:00',
          venue: 'Highmark Stadium',
          is_dome: false
        },
        {
          game_id: 502,
          home_team: 'Packers',
          away_team: 'Vikings',
          game_date: '2024-01-21T16:30:00',
          venue: 'Lambeau Field',
          is_dome: false
        },
        {
          game_id: 503,
          home_team: 'Cowboys',
          away_team: 'Eagles',
          game_date: '2024-01-21T20:15:00',
          venue: 'AT&T Stadium',
          is_dome: true
        },
        {
          game_id: 504,
          home_team: '49ers',
          away_team: 'Rams',
          game_date: '2024-01-22T20:15:00',
          venue: "Levi's Stadium",
          is_dome: false
        }
      ];
      setGames(mockGames);
      hydratePredictionSummaries(mockGames);
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
        const prediction = buildPredictionSummary(res);
        setPredictionSummaries((prev) => ({ ...prev, [game.game_id]: prediction }));
        setSelectedGame({ ...game, prediction });
      }
    } catch (error) {
      console.error('Error fetching prediction:', error);
      const fallbackPrediction = buildFallbackPrediction(game);
      setPredictionSummaries((prev) => ({ ...prev, [game.game_id]: fallbackPrediction }));
      setSelectedGame({ ...game, prediction: fallbackPrediction });
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
              games={games}
              getConfidenceColor={getConfidenceColor}
              inputClass={inputClass}
              isDarkMode={isDarkMode}
              loading={loading}
              mutedTextClass={mutedTextClass}
              paginatedGames={paginatedGames}
              predictionSummaries={predictionSummaries}
              primaryTextClass={primaryTextClass}
              surfaceClass={surfaceClass}
              totalWeeks={totalWeeks}
              visibleRangeEnd={visibleRangeEnd}
              visibleRangeStart={visibleRangeStart}
              onAgentChipClick={handleScrollToAgent}
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

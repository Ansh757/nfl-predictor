import React, { useCallback, useState, useEffect, useMemo } from 'react';
import { Activity, BarChart3, Bot, Gauge, Plane, TrendingUp } from 'lucide-react';
import {
  GamesSection,
  HeaderSection,
  PaginationControls,
  PlayoffControls,
  PredictionSection
} from './components/DashboardSections';
import PlayoffsBracket from './components/PlayoffsBracket';

const TabBar = ({ tabs, activeTab, onTabChange, isDarkMode }) => {
  const baseClasses = isDarkMode
    ? 'border-slate-800 bg-slate-900 text-slate-300'
    : 'border-slate-200 bg-white text-slate-600';
  const activeClasses = isDarkMode
    ? 'bg-blue-500/20 text-blue-100 border-blue-500/50'
    : 'bg-blue-50 text-blue-700 border-blue-200';

  return (
    <div
      role="tablist"
      aria-label="Dashboard views"
      className={`flex flex-wrap gap-2 rounded-2xl border p-2 ${baseClasses}`}
    >
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.key}
          className={`rounded-xl border px-4 py-2 text-sm font-semibold transition ${
            activeTab === tab.key ? activeClasses : 'border-transparent'
          }`}
          onClick={() => onTabChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
};


function App() {
  const [games, setGames] = useState([]);
  const [selectedGame, setSelectedGame] = useState(null);
  const [loading, setLoading] = useState(false);
  // Set REACT_APP_API_URL at build time to point at a different backend -
  // the Java gateway, or a local service. Falls back to production.
  const [apiUrl, setApiUrl] = useState(
    process.env.REACT_APP_API_URL || 'https://nfl-predictor-system-production.up.railway.app'
  );
  const seasonStart = 2021;
  const calendarSeason = new Date().getFullYear();
  // NFL seasons run into the new year, so until March the season in play is
  // still the previous calendar year's. Derived rather than hardcoded so this
  // does not need editing every August.
  const seasonEnd = new Date().getMonth() < 2 ? calendarSeason - 1 : calendarSeason;
  const boundedSeason = Math.min(Math.max(calendarSeason, seasonStart), seasonEnd);
  const [currentSeason, setCurrentSeason] = useState(boundedSeason);
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
  const [activeTab, setActiveTab] = useState('regular');
  const [selectedSeason, setSelectedSeason] = useState(boundedSeason);
  const [selectedRound, setSelectedRound] = useState('Wild Card');
  const [playoffViewMode, setPlayoffViewMode] = useState('single');
  const [playoffGames, setPlayoffGames] = useState([]);
  const [playoffGamesLoading, setPlayoffGamesLoading] = useState(false);
  const [playoffGamesError, setPlayoffGamesError] = useState(null);
  // Fetch failures used to be console.error only, so an API outage looked
  // identical to a week with no games.
  const [gamesError, setGamesError] = useState(null);
  const [playoffSimulation, setPlayoffSimulation] = useState({
    loading: false,
    error: null,
    data: null
  });
  const simulationCount = 1000;
  const pageSize = 4;
  const tabs = useMemo(
    () => [
      { key: 'regular', label: 'Regular Season' },
      { key: 'playoffs', label: 'Playoffs' }
      // 'trends' and 'compare' were listed here with no matching render branch,
      // so selecting either showed an empty page. Removed rather than shipped
      // broken; /api/gateway/accuracy and /agents/compare are the natural
      // backends if they are built for real.
    ],
    []
  );
  // The five agents that carry weight, strongest first. Weather and News were
  // retired from the ensemble - both measured at coin-flip level - so they no
  // longer appear as voters. Conditions are still shown as game context.
  // Keys must stay in sync with
  // normalizeAgentKey() below, which maps the backend's agent_name strings onto
  // them. Any agent the backend returns that does not match a key here is still
  // rendered - see displayAgents - so adding one server-side degrades to a
  // generic card rather than disappearing.
  const agentDefinitions = useMemo(
    () => [
      {
        key: 'market',
        label: 'Market',
        description: 'Closing lines across sportsbooks, with the vig removed',
        icon: BarChart3
      },
      {
        key: 'stats',
        label: 'Team Stats',
        description: 'Records, point differential, recent form, home/away splits',
        icon: TrendingUp
      },
      {
        key: 'elo',
        label: 'Elo',
        description: 'Opponent-adjusted power ratings with margin of victory',
        icon: Gauge
      },
      {
        key: 'rest',
        label: 'Rest & Travel',
        description: 'Rest days, byes, short weeks, travel and time zones',
        icon: Plane
      },
      {
        key: 'injuries',
        label: 'Injuries',
        description: 'Lineup health and late-week availability',
        icon: Activity
      }
    ],
    []
  );
  const roundOptions = useMemo(
    () => ['Wild Card', 'Divisional', 'Conference', 'Championship'],
    []
  );
  const playoffRounds = useMemo(() => roundOptions, [roundOptions]);
  const playoffGamesByRound = useMemo(
    () =>
      playoffGames.reduce((acc, game, index) => {
        const roundName = game.round ?? 'Unknown';
        if (!acc[roundName]) {
          acc[roundName] = [];
        }
        acc[roundName].push({
          game_id: game.game_id ?? `${roundName}-${index}`,
          away_team: game.away_team,
          home_team: game.home_team,
          away_seed: game.away_seed,
          home_seed: game.home_seed,
          predicted_winner: game.predicted_winner,
          advance_probability: game.advance_probability,
          game_date: game.game_date,
          is_dome: game.is_dome,
          venue: game.venue
        });
        return acc;
      }, {}),
    [playoffGames]
  );

  const mapSimulationToBracket = (simulation) => {
    const rounds = simulation?.rounds ?? {};
    const mappedRounds = Object.entries(rounds).reduce((acc, [roundName, games]) => {
      acc[roundName] = games.map((game) => ({
        game_id: game.game_id,
        away_team: game.away_team,
        home_team: game.home_team,
        away_seed: game.away_seed,
        home_seed: game.home_seed,
        predicted_winner: game.predicted_winner,
        advance_probability: game.advance_probability,
        game_date: game.game_date,
        is_dome: game.is_dome,
        venue: game.venue
      }));
      return acc;
    }, {});

    return {
      ...simulation,
      gamesByRound: mappedRounds
    };
  };

  const bracketGamesByRound = playoffSimulation.data?.gamesByRound ?? playoffGamesByRound;

  // What actually gets rendered: the known cards, plus any agent the service
  // returned that has no card defined. Keeps the dashboard honest if the
  // backend's agent roster changes without a frontend update.
  const displayAgents = useMemo(() => {
    const known = new Set(agentDefinitions.map((agent) => agent.key));
    const extras = new Map();

    Object.values(predictionSummaries).forEach((summary) => {
      Object.entries(summary?.agentInsights ?? {}).forEach(([key, insight]) => {
        if (!known.has(key) && !extras.has(key)) {
          extras.set(key, {
            key,
            label: insight?.label ?? key,
            description: insight?.description || 'Reported by the prediction service',
            icon: Bot
          });
        }
      });
    });

    return [...agentDefinitions, ...extras.values()];
  }, [agentDefinitions, predictionSummaries]);

  // Substring -> card key. Matched in order, so put anything ambiguous first.
  // The previous version fell through to 'injuries' for everything unmatched,
  // which meant new backend agents silently overwrote the injuries card instead
  // of showing up.
  const normalizeAgentKey = (agentName = '') => {
    const normalized = agentName.toLowerCase();
    const patterns = [
      ['elo', 'elo'],
      ['market', 'market'],
      ['odds', 'market'],
      ['injur', 'injuries'],
      ['rest', 'rest'],
      ['travel', 'rest'],
      ['basic', 'stats'],
      ['predictor', 'stats']
    ];
    const match = patterns.find(([needle]) => normalized.includes(needle));
    if (match) return match[1];
    // Unknown agent: give it its own slug so it renders rather than vanishing
    return `agent-${normalized.replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`;
  };

  const buildPredictionSummary = (res) => {
    const agentPredictions = res?.agent_predictions ?? [];
    const totalAgents = agentPredictions.length || agentDefinitions.length;
    const winner = res?.overall_winner ?? 'Awaiting pick';
    const confidence = res?.overall_confidence ?? 0;
    const alignedAgents = agentPredictions.filter(
      (prediction) => prediction.predicted_winner === winner
    ).length;

    // The vote is weighted, so agreeing with the outcome is not the same as
    // affecting it. An agent's contribution is weight x (confidence - 0.5), and
    // an agent with no measured edge contributes exactly zero however sure it is.
    const totalContribution = agentPredictions.reduce(
      (sum, prediction) => sum + (prediction.contribution ?? 0),
      0
    );
    const weightedScores = res?.weighted_scores ?? {};
    const winnerScore = weightedScores[winner] ?? 0;
    const scoreTotal = Object.values(weightedScores).reduce((sum, value) => sum + value, 0);

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
      const contribution = prediction.contribution ?? 0;
      agentInsights[key] = {
        label: agentInsights[key]?.label ?? prediction.agent_name,
        description: agentInsights[key]?.description ?? '',
        predictedWinner: prediction.predicted_winner,
        confidence: prediction.confidence,
        reasoning: prediction.reasoning,
        isAligned: prediction.predicted_winner === winner,
        weight: prediction.weight ?? 0,
        contribution,
        // has_data is false when the agent reported exactly 0.50 - its signal
        // for "no data", which is different from a genuine 50/50 read
        hasData: prediction.has_data !== false,
        influenceShare: totalContribution > 0 ? contribution / totalContribution : 0
      };
    });

    return {
      winner,
      confidence,
      reasoning: res?.consensus_reasoning ?? 'Consensus details are pending.',
      consensus: {
        count: alignedAgents,
        total: totalAgents,
        label: `${alignedAgents}/${totalAgents} agents`,
        method: res?.consensus_method ?? 'weighted',
        weightedScores,
        // Share of the weighted total behind the winning side. Distinct from
        // the headcount: a minority of agents can carry a decision.
        winnerInfluence: scoreTotal > 0 ? winnerScore / scoreTotal : null
      },
      agentInsights,
      // Display-only context: reported, never voted on
      conditions: res?.conditions ?? null
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
        return { error: `Prediction service returned ${response.status}.` };
      }

      const res = await response.json();
      return buildPredictionSummary(res);
    } catch (error) {
      console.error('Error fetching prediction:', error);
      return { error: 'Could not reach the prediction service.' };
    }
  };

  const fetchPlayoffGames = useCallback(async (season, round) => {
    const roundSegment = round ? `/round/${encodeURIComponent(round)}` : '';
    const response = await fetch(`${apiUrl}/playoffs/${season}${roundSegment}`);
    if (!response.ok) {
      throw new Error('Unable to load playoff games.');
    }
    const data = await response.json();
    return data.games || [];
  }, [apiUrl]);


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
  const fetchGamesByWeek = async (week, season = currentSeason) => {
    setLoading(true);
    setGamesError(null);
    try {
      const response = await fetch(`${apiUrl}/games/week/${week}?season=${season}`);
      if (!response.ok) {
        // Previously this branch did nothing at all: the old games stayed on
        // screen and the user was told nothing.
        setGamesError(`The schedule service returned ${response.status}.`);
        setGames([]);
      } else {
        const data = await response.json();
        const nextGames = data.games || [];
        setGames(nextGames);
        setPredictionLoading({});
        await preloadPredictions(nextGames);
      }
    } catch (error) {
      console.error('Error fetching games:', error);
      setGamesError('Could not reach the prediction service.');
      setGames([]);
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

  const runPlayoffSimulation = async () => {
    setPlayoffSimulation((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const response = await fetch(`${apiUrl}/playoffs/${selectedSeason}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simulations: simulationCount })
      });

      if (!response.ok) {
        throw new Error('Simulation request failed.');
      }

      const data = await response.json();
      setPlayoffSimulation({ loading: false, error: null, data: mapSimulationToBracket(data) });
    } catch (error) {
      console.error('Error running playoff simulation:', error);
      setPlayoffSimulation((prev) => ({
        ...prev,
        loading: false,
        error: 'Unable to run simulation right now.'
      }));
    }
  };

  const handleWeekChange = (event) => {
    const nextWeek = Number(event.target.value);
    setCurrentWeek(nextWeek);
    setCurrentPage(1);
    fetchGamesByWeek(nextWeek);
  };

  useEffect(() => {
    // Initial load, and again whenever the API URL is repointed - which
    // previously did nothing until you changed week or hit refresh.
    //
    // currentWeek and currentSeason are deliberately absent: their own change
    // handlers fetch directly, so listing them here would fire a second
    // request on every change.
    fetchGamesByWeek(currentWeek, currentSeason);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl]);

  useEffect(() => {
    setPlayoffSimulation((prev) => ({ ...prev, data: null, error: null }));
  }, [selectedSeason]);

  useEffect(() => {
    let isActive = true;
    const loadPlayoffGames = async () => {
      setPlayoffGamesLoading(true);
      setPlayoffGamesError(null);
      try {
        const games = await fetchPlayoffGames(selectedSeason);
        if (isActive) {
          setPlayoffGames(games);
        }
      } catch (error) {
        console.error('Error fetching playoff games:', error);
        if (isActive) {
          setPlayoffGames([]);
          setPlayoffGamesError('Unable to load playoff games right now.');
        }
      } finally {
        if (isActive) {
          setPlayoffGamesLoading(false);
        }
      }
    };

    loadPlayoffGames();
    return () => {
      isActive = false;
    };
  }, [selectedSeason, apiUrl, fetchPlayoffGames]);

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
  const seasonOptions = useMemo(() => {
    const startSeason = seasonStart;
    const endSeason = seasonEnd;
    return Array.from({ length: endSeason - startSeason + 1 }, (_, index) => startSeason + index);
  }, [seasonEnd, seasonStart]);

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

  useEffect(() => {
    const nextTotalPages = Math.max(1, Math.ceil(filteredGames.length / pageSize));
    if (currentPage > nextTotalPages) {
      setCurrentPage(nextTotalPages);
    }
  }, [filteredGames, currentPage]);

  const totalPages = Math.max(1, Math.ceil(filteredGames.length / pageSize));
  const paginatedGames = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredGames.slice(start, start + pageSize);
  }, [filteredGames, currentPage]);
  const selectedRoundGames = playoffGamesByRound?.[selectedRound] ?? [];
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
          onRefresh={() => fetchGamesByWeek(currentWeek, currentSeason)}
          onToggleDarkMode={() => setIsDarkMode((prev) => !prev)}
        />

        <TabBar
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          isDarkMode={isDarkMode}
        />

        <div className="space-y-6">
          {activeTab === 'regular' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <GamesSection
                  gamesError={gamesError}
                  agentChipActiveClass={agentChipActiveClass}
                  agentChipClass={agentChipClass}
                  agentDefinitions={displayAgents}
                  chipClass={chipClass}
              currentWeek={currentWeek}
              currentSeason={currentSeason}
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
              seasonOptions={seasonOptions}
              sortBy={sortBy}
                  teamOptions={teamOptions}
                  surfaceClass={surfaceClass}
              totalWeeks={totalWeeks}
              onSeasonChange={(event) => {
                const nextSeason = Number(event.target.value);
                setCurrentSeason(nextSeason);
                setCurrentPage(1);
                fetchGamesByWeek(currentWeek, nextSeason);
              }}
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
                agentDefinitions={displayAgents}
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
          )}

          {activeTab === 'playoffs' && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="space-y-6">
                <PlayoffControls
                  inputClass={inputClass}
                  isDarkMode={isDarkMode}
                  mutedTextClass={mutedTextClass}
                  primaryTextClass={primaryTextClass}
                  roundOptions={roundOptions}
                  seasonOptions={seasonOptions}
                  selectedRound={selectedRound}
                  selectedSeason={selectedSeason}
                  playoffViewMode={playoffViewMode}
                  simulationCount={simulationCount}
                  simulationError={playoffSimulation.error}
                  simulationLoading={playoffSimulation.loading}
                  surfaceClass={surfaceClass}
                  onRoundChange={(event) => setSelectedRound(event.target.value)}
                  onSeasonChange={(event) => setSelectedSeason(Number(event.target.value))}
                  onViewModeChange={setPlayoffViewMode}
                  onRunSimulation={runPlayoffSimulation}
                />
                {playoffViewMode === 'bracket' ? (
                  <PlayoffsBracket
                    rounds={playoffRounds}
                    gamesByRound={bracketGamesByRound}
                    selectedRound={selectedRound}
                    onSelectGame={fetchPrediction}
                    isDarkMode={isDarkMode}
                    mutedTextClass={mutedTextClass}
                    primaryTextClass={primaryTextClass}
                    surfaceClass={surfaceClass}
                  />
                ) : (
                  <div className={`rounded-2xl p-6 ${surfaceClass}`}>
                    <p className={`text-sm font-semibold uppercase tracking-wide ${mutedTextClass}`}>
                      Playoff Matchups
                    </p>
                    <h2 className={`mt-2 text-xl font-semibold ${primaryTextClass}`}>
                      Single-game view
                    </h2>
                    <p className={`mt-2 text-sm ${mutedTextClass}`}>
                      {selectedSeason} Season · {selectedRound}
                    </p>
                    {playoffGamesLoading ? (
                      <p className={`mt-3 text-sm ${mutedTextClass}`}>Loading playoff games...</p>
                    ) : playoffGamesError ? (
                      <p className={`mt-3 text-sm text-red-500`}>{playoffGamesError}</p>
                    ) : selectedRoundGames.length > 0 ? (
                      <div className="mt-4 space-y-3">
                        {selectedRoundGames.map((game) => (
                          <button
                            key={game.game_id}
                            type="button"
                            onClick={() => fetchPrediction(game)}
                            className={`w-full rounded-xl border p-4 text-left transition ${
                              isDarkMode
                                ? 'border-slate-800 bg-slate-950 hover:border-blue-500/60 hover:shadow-lg hover:shadow-blue-500/10'
                                : 'border-slate-200 bg-white hover:border-blue-500 hover:shadow-md'
                            }`}
                          >
                            <div className="flex items-center justify-between text-sm font-semibold">
                              <span className={primaryTextClass}>
                                {game.away_team} @ {game.home_team}
                              </span>
                              <span className={mutedTextClass}>
                                {game.game_date ? formatTime(game.game_date) : 'TBD'}
                              </span>
                            </div>
                            <div className={`mt-2 text-xs uppercase ${mutedTextClass}`}>
                              {game.venue || 'Venue TBD'}
                            </div>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className={`mt-3 text-sm ${mutedTextClass}`}>
                        No games listed for this round yet.
                      </p>
                    )}
                  </div>
                )}
              </div>
              <PredictionSection
                agentDefinitions={displayAgents}
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
          )}

          {activeTab !== 'regular' && activeTab !== 'playoffs' && (
            <div className={`rounded-2xl p-6 ${surfaceClass}`}>
              <p className={`text-sm font-semibold uppercase tracking-wide ${mutedTextClass}`}>
                {tabs.find((tab) => tab.key === activeTab)?.label ?? 'Tab'}
              </p>
              <h2 className={`mt-2 text-xl font-semibold ${primaryTextClass}`}>
                This view is on the roadmap
              </h2>
              <p className={`mt-3 text-sm ${mutedTextClass}`}>
                Add new content for this tab by expanding the tab configuration and layout here.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;

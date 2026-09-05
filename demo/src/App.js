import React, { useCallback, useState, useEffect, useMemo } from 'react';
import { Activity, BarChart3, Bot, Gauge, Plane, TrendingUp } from 'lucide-react';
import TopBar from './components/TopBar';
import StatStrip from './components/StatStrip';
import Sidebar from './components/Sidebar';
import GameList from './components/GameList';
import GameDetail from './components/GameDetail';
import PlayoffsView from './components/PlayoffsView';
import LandingPage from './components/LandingPage';
import Disclaimer from './components/Disclaimer';
import WakeBanner from './components/WakeBanner';
import { formatKickoff } from './utils/time';

// Cold-start handling. The hosted service is stopped when idle, so the first
// request after a quiet spell waits on a container boot rather than failing
// fast. A single probe reported that as an outage; these govern the retry.
const COLD_START_HINT_MS = 2500;   // announce the wait only once it is a wait
const HEALTH_PROBE_ATTEMPTS = 8;   // ~2 minutes of backoff before giving up
const HEALTH_PROBE_BACKOFF_MS = [1000, 2000, 4000, 8000, 15000, 25000, 40000];
const GAMES_RETRY_BACKOFF_MS = [3000, 8000];
// A week's worth of predictions is requested at once, so a 429 is a queueing
// problem rather than an error. Two retries clear it.
const PREDICTION_RETRY_ATTEMPTS = 2;

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const THEME_STORAGE_KEY = 'nfl-predictor-theme';

/**
 * The theme the page should open in: an explicit past choice first, then the
 * operating system's preference, then dark.
 *
 * Both lookups are guarded. localStorage throws outright in a Safari private
 * window, and jsdom has no matchMedia - neither is a reason to fail to render.
 */
export const preferredTheme = () => {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    /* storage unavailable - fall through to the OS preference */
  }
  try {
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
  } catch {
    /* no matchMedia - fall through to the default */
  }
  // Light is the default now: the warm paper palette is the design, and dark
  // is the alternate. An explicit OS preference still wins over both.
  return 'light';
};

const FALLBACK_API_URL = 'https://nfl-predictor-system-production.up.railway.app';

/**
 * Where to send API calls.
 *
 * 1. REACT_APP_API_URL wins - point the dashboard at the Java gateway or a
 *    local service at build time.
 * 2. Otherwise, same origin. The service serves this bundle itself, so
 *    whatever host the page was loaded from is the host that answers. That is
 *    what makes a custom domain a DNS change rather than a rebuild, and it is
 *    why a preview deploy talks to its own backend instead of production.
 * 3. Only when the page is served from a dev server (which has no API behind
 *    it) does it fall back to the hosted service.
 */
export const resolveApiUrl = () => {
  if (process.env.REACT_APP_API_URL) return process.env.REACT_APP_API_URL;
  if (typeof window === 'undefined' || !window.location) return FALLBACK_API_URL;
  const { origin, hostname } = window.location;
  const isDevServer = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
  return isDevServer || !origin || origin === 'null' ? FALLBACK_API_URL : origin;
};

function App() {
  const [games, setGames] = useState([]);
  const [selectedGame, setSelectedGame] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiUrl] = useState(resolveApiUrl);
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
  // Was `isDarkMode`, initialised to false while every surface was hardcoded
  // dark - so the toggle swapped its own icon and nothing else. The value now
  // drives a data-theme attribute that the whole palette hangs off; see
  // index.css.
  const [theme, setTheme] = useState(preferredTheme);
  const [predictionSummaries, setPredictionSummaries] = useState({});
  const [predictionLoading, setPredictionLoading] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTeam, setSelectedTeam] = useState('all');
  const [selectedTime, setSelectedTime] = useState('all');
  const [sortBy, setSortBy] = useState('week-asc');
  const [selectedSeason, setSelectedSeason] = useState(boundedSeason);
  const [playoffGames, setPlayoffGames] = useState([]);
  const [playoffGamesLoading, setPlayoffGamesLoading] = useState(false);
  const [playoffGamesError, setPlayoffGamesError] = useState(null);
  // Fetch failures used to be console.error only, so an API outage looked
  // identical to a week with no games.
  const [gamesError, setGamesError] = useState(null);
  const [activeView, setActiveView] = useState('overview');
  const [apiConnected, setApiConnected] = useState(null);
  // Only populated when apiUrl points at the Java gateway; the Python service
  // has no such endpoint, so this stays null and the tile shows a dash rather
  // than inventing a number before any game has been played.
  const [liveAccuracy, setLiveAccuracy] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  // True while the service has been asked for something and has not answered
  // yet - see WakeBanner. Distinct from `loading`, which is also true for a
  // fast request against a warm service.
  const [serviceWaking, setServiceWaking] = useState(false);
  const pageSize = 4;
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
          away_score: game.away_score,
          home_score: game.home_score,
          game_date: game.game_date,
          venue: game.venue
        });
        return acc;
      }, {}),
    [playoffGames]
  );



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

  const requestPrediction = async (game, attempt = 0) => {
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

      if (response.status === 429) {
        // Rate limited. A week loads every game at once, so a burst is normal
        // traffic rather than abuse - back off and try again instead of
        // reporting a permanent failure for something that resolves itself.
        const retryAfter = Number(response.headers.get('Retry-After')) || 2;
        if (attempt < PREDICTION_RETRY_ATTEMPTS) {
          await wait(Math.min(retryAfter, 5) * 1000 * (attempt + 1));
          return requestPrediction(game, attempt + 1);
        }
        return { error: 'Too many requests just now. Refresh in a moment.' };
      }

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

  // Fetch games by week.
  //
  // Retries a failed load a couple of times before reporting it. A sleeping
  // deployment can refuse or drop the first request while the container boots,
  // and that used to surface as a permanent "could not load games" that only a
  // manual refresh cleared.
  const fetchGamesByWeek = async (week, season = currentSeason) => {
    setLoading(true);
    setGamesError(null);

    let failure = null;
    for (let attempt = 0; attempt <= GAMES_RETRY_BACKOFF_MS.length; attempt += 1) {
      try {
        const response = await fetch(`${apiUrl}/games/week/${week}?season=${season}`);
        if (response.ok) {
          const data = await response.json();
          const nextGames = data.games || [];
          setGames(nextGames);
          setGamesError(null);
          setPredictionLoading({});
          setLoading(false);
          // Predictions run the agents, so they are slow by nature; the list is
          // already on screen and fills in card by card.
          await preloadPredictions(nextGames);
          return;
        }
        // A 4xx is an answer, not a cold start - do not sit through the backoff.
        failure = `The schedule service returned ${response.status}.`;
        if (response.status < 500) break;
      } catch (error) {
        console.error('Error fetching games:', error);
        failure = 'Could not reach the prediction service.';
      }
      if (attempt < GAMES_RETRY_BACKOFF_MS.length) {
        await wait(GAMES_RETRY_BACKOFF_MS[attempt]);
      }
    }

    // Previously this branch did nothing at all: the old games stayed on
    // screen and the user was told nothing.
    setGamesError(failure);
    setGames([]);
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


  const getTimeBucket = (timeString) => {
    const hour = new Date(timeString).getHours();
    if (hour < 12) return 'morning';
    if (hour < 18) return 'afternoon';
    return 'evening';
  };

  useEffect(() => {
    let active = true;
    let hintTimer = null;

    const probeAccuracy = async () => {
      try {
        // 404s against the Python service, which is the expected case
        const response = await fetch(`${apiUrl}/api/gateway/accuracy`);
        if (response.ok) {
          const data = await response.json();
          if (active) setLiveAccuracy(data.accuracy ?? null);
        }
      } catch {
        /* no gateway reachable - the tile stays dashed */
      }
    };

    // Keep retrying while the service boots. The badge stays on "Checking API"
    // throughout rather than flashing red at the first refused connection, and
    // only reports a real outage once the attempts are exhausted.
    const probe = async () => {
      hintTimer = setTimeout(() => { if (active) setServiceWaking(true); }, COLD_START_HINT_MS);

      for (let attempt = 0; attempt < HEALTH_PROBE_ATTEMPTS; attempt += 1) {
        try {
          const response = await fetch(`${apiUrl}/health`);
          if (!active) return;
          if (response.ok) {
            clearTimeout(hintTimer);
            setApiConnected(true);
            setServiceWaking(false);
            await probeAccuracy();
            return;
          }
        } catch {
          /* still asleep or unreachable - retried below */
        }
        if (!active) return;
        // No point backing off after the final attempt - nothing follows it.
        if (attempt < HEALTH_PROBE_ATTEMPTS - 1) {
          await wait(HEALTH_PROBE_BACKOFF_MS[Math.min(attempt, HEALTH_PROBE_BACKOFF_MS.length - 1)]);
        }
      }

      if (!active) return;
      clearTimeout(hintTimer);
      setServiceWaking(false);
      setApiConnected(false);
    };

    probe();
    return () => {
      active = false;
      clearTimeout(hintTimer);
    };
  }, [apiUrl]);

  // Kickoffs are stored as UTC instants and rendered in the viewer's own zone,
  // always with the zone attached - see utils/time.js. Printing a bare "5:20 PM"
  // made the site look wrong to anyone outside the zone it happened to resolve to.
  const formatTime = formatKickoff;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      /* storage unavailable - the choice just will not survive a reload */
    }
  }, [theme]);

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
  const visibleRangeStart =
    filteredGames.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const visibleRangeEnd = Math.min(currentPage * pageSize, filteredGames.length);

  useEffect(() => {
    const nextTotalPages = Math.max(1, Math.ceil(filteredGames.length / pageSize));
    if (currentPage > nextTotalPages) {
      setCurrentPage(nextTotalPages);
    }
  }, [filteredGames, currentPage, pageSize]);
  

  // Headline numbers, derived from the predictions currently loaded
  const weekSummaries = useMemo(
    () => filteredGames
      .map((game) => predictionSummaries?.[game.game_id])
      .filter((summary) => summary && !summary.error && summary.confidence != null),
    [filteredGames, predictionSummaries]
  );
  const avgConfidence = weekSummaries.length
    ? weekSummaries.reduce((sum, s) => sum + s.confidence, 0) / weekSummaries.length
    : null;
  const highConfidenceCount = weekSummaries.filter((s) => s.confidence >= 0.7).length;
  const weekRange = useMemo(() => {
    if (!filteredGames.length) return null;
    const dates = filteredGames
      .map((game) => new Date(game.game_date))
      .filter((date) => !Number.isNaN(date.valueOf()))
      .sort((a, b) => a - b);
    if (!dates.length) return null;
    const fmt = (date) => date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return dates.length > 1 && fmt(dates[0]) !== fmt(dates[dates.length - 1])
      ? `${fmt(dates[0])} - ${fmt(dates[dates.length - 1])}`
      : fmt(dates[0]);
  }, [filteredGames]);

  // "View full analysis" on the featured matchup used to do nothing but switch
  // to the games view, leaving the reader to find the game it had just been
  // showing them. Select it too, reusing the loaded prediction rather than
  // running every agent again for a summary already on screen.
  const openGameDetail = (game) => {
    if (!game) return;
    setActiveView('regular');
    const cached = predictionSummaries[game.game_id];
    if (cached && !cached.error) {
      setSelectedGame({ ...game, prediction: cached });
    } else {
      fetchPrediction(game);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchGamesByWeek(currentWeek, currentSeason);
    setRefreshing(false);
  };


  return (
    <div className="app-shell min-h-screen text-mist">
      <TopBar
        seasonOptions={seasonOptions}
        currentSeason={currentSeason}
        onSeasonChange={(event) => {
          const nextSeason = Number(event.target.value);
          setCurrentSeason(nextSeason);
          setCurrentPage(1);
          fetchGamesByWeek(currentWeek, nextSeason);
        }}
        apiConnected={apiConnected}
        serviceWaking={serviceWaking}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        theme={theme}
        onToggleTheme={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
      />

      {serviceWaking && <WakeBanner />}

      <StatStrip
        week={currentWeek}
        weekRange={weekRange}
        gameCount={filteredGames.length}
        liveAccuracy={liveAccuracy}
        avgConfidence={avgConfidence}
        highConfidenceCount={highConfidenceCount}
      />

      <div className="flex flex-col lg:flex-row">
        <Sidebar activeView={activeView} onViewChange={setActiveView} />

        <main className="min-w-0 flex-1 space-y-4 px-4 py-4 lg:px-6">
          {activeView === 'overview' && (
            <LandingPage
              featuredGame={filteredGames[0] ?? null}
              featuredSummary={filteredGames[0] ? predictionSummaries?.[filteredGames[0].game_id] : null}
              week={currentWeek}
              onExplore={() => setActiveView('regular')}
              onOpenGame={openGameDetail}
            />
          )}

          {activeView === 'regular' && (
            <>
              <section className="panel p-5">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="xl:col-span-2">
                    <label htmlFor="game-search" className="block whitespace-nowrap text-xs font-semibold uppercase text-slate-400">
                      Search
                    </label>
                    <input
                      id="game-search"
                      type="text"
                      value={searchQuery}
                      onChange={(event) => { setSearchQuery(event.target.value); setCurrentPage(1); }}
                      placeholder="Search teams or opponents..."
                      className="mt-1 w-full rounded-xl border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-mist outline-none transition placeholder:text-slate-500 focus:border-accent"
                    />
                  </div>
                  <div>
                    <label htmlFor="filter-week" className="block whitespace-nowrap text-xs font-semibold uppercase text-slate-400">
                      Week
                    </label>
                    <select
                      id="filter-week"
                      value={currentWeek}
                      onChange={(event) => {
                        const nextWeek = Number(event.target.value);
                        setCurrentWeek(nextWeek);
                        setCurrentPage(1);
                        fetchGamesByWeek(nextWeek, currentSeason);
                      }}
                      className="mt-1 w-full rounded-xl border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-mist outline-none transition focus:border-accent"
                    >
                      {Array.from({ length: totalWeeks }, (_, index) => index + 1).map((week) => (
                        <option key={week} value={week}>Week {week}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="filter-team" className="block whitespace-nowrap text-xs font-semibold uppercase text-slate-400">
                      Team
                    </label>
                    <select
                      id="filter-team"
                      value={selectedTeam}
                      onChange={(event) => { setSelectedTeam(event.target.value); setCurrentPage(1); }}
                      className="mt-1 w-full rounded-xl border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-mist outline-none transition focus:border-accent"
                    >
                      <option value="all">All teams</option>
                      {teamOptions.map((team) => (
                        <option key={team} value={team}>{team}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="filter-time" className="block whitespace-nowrap text-xs font-semibold uppercase text-slate-400">
                      Kickoff
                    </label>
                    <select
                      id="filter-time"
                      value={selectedTime}
                      onChange={(event) => { setSelectedTime(event.target.value); setCurrentPage(1); }}
                      className="mt-1 w-full rounded-xl border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-mist outline-none transition focus:border-accent"
                    >
                      <option value="all">All times</option>
                      <option value="morning">Morning</option>
                      <option value="afternoon">Afternoon</option>
                      <option value="evening">Evening</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="filter-sort" className="block whitespace-nowrap text-xs font-semibold uppercase text-slate-400">
                      Sort
                    </label>
                    <select
                      id="filter-sort"
                      value={sortBy}
                      onChange={(event) => setSortBy(event.target.value)}
                      className="mt-1 w-full rounded-xl border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-mist outline-none transition focus:border-accent"
                    >
                      <option value="week-asc">Week (asc)</option>
                      <option value="week-desc">Week (desc)</option>
                      <option value="team">Team games (A-Z)</option>
                      <option value="matchup">Matchup (A-Z)</option>
                      <option value="confidence">Confidence (high to low)</option>
                    </select>
                  </div>
                </div>
              </section>

              <div className="grid gap-4 xl:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
                <GameList
                  games={filteredGames}
                  paginatedGames={paginatedGames}
                  predictionSummaries={predictionSummaries}
                  predictionLoading={predictionLoading}
                  selectedGameId={selectedGame?.game_id}
                  onSelect={fetchPrediction}
                  formatTime={formatTime}
                  loading={loading}
                  gamesError={gamesError}
                  serviceWaking={serviceWaking}
                  currentPage={currentPage}
                  totalPages={totalPages}
                  rangeStart={visibleRangeStart}
                  rangeEnd={visibleRangeEnd}
                  currentWeek={currentWeek}
                  onPrev={() => setCurrentPage((page) => Math.max(1, page - 1))}
                  onNext={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                />

                <GameDetail
                  game={selectedGame}
                  summary={selectedGame ? predictionSummaries?.[selectedGame.game_id] : null}
                  isPredicting={selectedGame ? predictionLoading?.[selectedGame.game_id] : false}
                  agentDefinitions={displayAgents}
                  formatTime={formatTime}
                />
              </div>
            </>
          )}

          {activeView === 'playoffs' && (
            <PlayoffsView
              season={selectedSeason}
              seasonOptions={seasonOptions}
              onSeasonChange={(event) => setSelectedSeason(Number(event.target.value))}
              gamesByRound={playoffGamesByRound}
              loading={playoffGamesLoading}
              error={playoffGamesError}
            />
          )}

        </main>
      </div>

      <Disclaimer />
    </div>
  );
}

export default App;

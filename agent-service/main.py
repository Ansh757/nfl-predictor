import sqlite3
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from collections import defaultdict
import random
import os
import asyncio
import time
from datetime import datetime
import logging

from dotenv import load_dotenv

# Load the project-root .env before any agent constructs its API clients.
# find_dotenv() walks up from this file, so it resolves the root .env whether
# the service is started from agent-service/ or from the repo root. This used
# to happen only as a side effect of importing weather_agent, which made key
# loading depend on import order.
load_dotenv()

# Import our agents
from agents.basic_predictor import BasicPredictorAgent
from agents.odds_agent import MarketOddsAgent
from agents.injury_agent import InjuryImpactAgent
from agents.consensus import build_consensus, AGENT_WEIGHTS, DEFAULT_WEIGHT
from agents.elo_agent import EloRatingAgent
from agents.rest_travel_agent import RestTravelAgent
from utils.schedule_loader import NFLScheduleLoader
from utils.weather import WeatherProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NFL Agentic Prediction Service", version="1.0.0")

current_dir = os.path.dirname(__file__)
candidate_build_paths = [
    os.path.join(current_dir, "demo", "build"),
    os.path.join(current_dir, "..", "demo", "build"),
]
demo_build = next((path for path in candidate_build_paths if os.path.exists(path)), candidate_build_paths[0])
demo_build = os.path.abspath(demo_build)
logger.info(f"Looking for frontend at: {demo_build}")
logger.info(f"Frontend exists: {os.path.exists(demo_build)}")

if os.path.exists(demo_build):
    # Mount static files
    static_path = os.path.join(demo_build, "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")
        logger.info(f"=== Mounted static files from: {static_path}")
    
    # Serve manifest and favicon
    @app.get("/manifest.json")
    async def manifest():
        return FileResponse(os.path.join(demo_build, "manifest.json"))
    
    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse(os.path.join(demo_build, "favicon.ico"))
    
    # Root path serves React app
    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(demo_build, "index.html"))
else:
    logger.warning(f"=== Frontend build folder not found at: {demo_build}")
    
    # Fallback root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "NFL Agentic Prediction Service",
            "status": "active",
            "version": "1.0.0",
            "agents": ["Market Odds", "Basic Predictor", "Elo Ratings",
                       "Rest & Travel", "Injury Impact"],
            "note": "Frontend not built. Run 'npm run build' in demo folder."
        }

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:3000", "https://nfl-predictor-system-production.up.railway.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Team logos are the only third-party asset the dashboard loads.
_ESPN_IMAGES = "https://a.espncdn.com"

_SECURITY_HEADERS = {
    # The page has no reason to be framed, and framing it is how a clickjack
    # would dress the dashboard up as something else.
    "X-Frame-Options": "DENY",
    # Stop the browser sniffing a response into a type it was not served as.
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Nothing here needs a camera, a microphone or a location.
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # Railway terminates TLS in front of this, so HSTS is safe to assert.
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # 'unsafe-inline' for styles is required: the build inlines a small runtime
    # style block, and Tailwind's generated sheet is served from this origin.
    # Scripts are restricted to self, so an injected <script src> cannot load.
    "Content-Security-Policy": (
        "default-src 'self'; "
        f"img-src 'self' data: {_ESPN_IMAGES}; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self' https:; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    ),
}


def _server_error(context: str, error: Exception) -> HTTPException:
    """
    Log the real cause, return a generic one.

    str(e) was going straight to the client, which for a sqlite or httpx failure
    means echoing file paths, SQL fragments and internal hostnames to anyone who
    can provoke an exception. The detail is still available - in the logs, where
    it is useful and not a disclosure.
    """
    logger.exception("%s failed: %s", context, error)
    return HTTPException(status_code=500, detail=f"{context} failed. See server logs.")


# Rate limiting for the endpoints that cost real resources.
#
# /predict runs five agents; /games/refresh re-pulls eighteen weeks from ESPN.
# Neither needs authentication to be useful, but a loop over either will happily
# exhaust a free-tier container or hammer an upstream we do not own. This is a
# deliberately small in-process limiter: one container, no shared state to keep,
# and nothing to add to the dependency list.
# Sized by unit of work, not by request count - which is what the first version
# got wrong. Nothing here asks for one prediction: the dashboard preloads every
# game in a week (16 concurrent /predict calls per page view) and the gateway
# fans out the same way over /agents/predict-all when it records a week. A
# 30-per-minute ceiling therefore allowed exactly one page view and rejected the
# next, which is not a rate limit, it is an outage with a timer.
#
# These allow roughly ten week-loads a minute per client. Still a bound on abuse
# - a scripted flood is orders of magnitude above this - without any legitimate
# use coming near it.
WEEK_FAN_OUT = 16
_RATE_LIMITS = {
    "/predict": (WEEK_FAN_OUT * 12, 60),
    "/agents/predict-all": (WEEK_FAN_OUT * 12, 60),
    "/agents/compare": (WEEK_FAN_OUT * 4, 60),
    # Genuinely expensive upstream - eighteen weeks pulled from ESPN with a
    # courtesy delay between them - and nothing legitimate calls it in a loop.
    "/games/refresh": (2, 3600),
}
_rate_state: Dict[str, List[float]] = defaultdict(list)
_rate_lock = asyncio.Lock()


def _rate_limit_for(path: str):
    for prefix, limit in _RATE_LIMITS.items():
        if path.startswith(prefix):
            return prefix, limit
    return None, None


def _client_key(request) -> str:
    # Railway sits behind a proxy, so request.client.host is the proxy. The
    # left-most X-Forwarded-For entry is the original client. It is spoofable,
    # which is fine here: this limits accidental hammering and casual abuse, and
    # is not claiming to stop a determined attacker with a botnet.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit(request, call_next):
    prefix, limit = _rate_limit_for(request.url.path)
    if limit is None:
        return await call_next(request)

    max_calls, window = limit
    key = f"{prefix}:{_client_key(request)}"
    now = time.monotonic()

    async with _rate_lock:
        recent = [stamp for stamp in _rate_state[key] if now - stamp < window]
        if len(recent) >= max_calls:
            retry_after = int(window - (now - recent[0])) + 1
            _rate_state[key] = recent
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(retry_after)},
            )
        recent.append(now)
        _rate_state[key] = recent

        # Bound the dictionary: without this every unique client key it has ever
        # seen stays resident for the life of the process.
        if len(_rate_state) > 2048:
            for stale in [k for k, v in _rate_state.items() if not v or now - v[-1] > 3600]:
                del _rate_state[stale]

    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """
    Baseline response hardening. None of these change how the app behaves; they
    close off the browser-side attacks that cost nothing to prevent.
    """
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response

# Pydantic models
class GameData(BaseModel):
    game_id: int
    home_team_name: str
    away_team_name: str
    game_time: datetime
    venue: Optional[str] = None
    is_dome: Optional[bool] = False
    # Both optional and both independent. Supplied by a caller that already
    # knows them (the gateway reading the schedule); otherwise resolved from
    # utils/venues.py. neutral_site governs home-field advantage,
    # venue_country governs the international travel adjustment - a Super Bowl
    # is the first without being the second.
    neutral_site: Optional[bool] = None
    venue_country: Optional[str] = None

class PlayoffGame(BaseModel):
    game_id: int
    season: int
    round: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    home_seed: Optional[int] = None
    away_seed: Optional[int] = None
    bracket: Optional[str] = None
    bracket_position: Optional[str] = None
    game_date: datetime
    venue: Optional[str] = None
    is_dome: Optional[bool] = False
    advance_probability: Optional[float] = None

class PredictionRequest(BaseModel):
    game_data: GameData
    include_reasoning: bool = True
    confidence_threshold: float = 0.0

class AgentPrediction(BaseModel):
    agent_name: str
    predicted_winner: str
    confidence: float
    reasoning: str
    prediction_time: datetime
    # How much this agent actually counted. weight is its measured edge over a
    # coin flip; contribution is weight x (confidence - 0.5), which is what the
    # consensus sums. An agent can be confident and still contribute nothing.
    weight: float = 0.0
    contribution: float = 0.0
    # False when the agent reported confidence exactly 0.50, its signal for
    # "no data" - distinct from a genuine 50/50 read.
    has_data: bool = True

class PredictionResponse(BaseModel):
    game_id: int
    overall_winner: str
    overall_confidence: float
    agent_predictions: List[AgentPrediction]
    consensus_reasoning: str
    prediction_time: datetime
    # The vote is weighted, not a headcount, so the raw counts alone can be
    # misleading - a minority of agents can win. Expose both.
    consensus_method: str = "weighted"
    home_votes: int = 0
    away_votes: int = 0
    weighted_scores: Dict[str, float] = {}
    # Game-day conditions for display. Not a vote - see utils/weather.py.
    conditions: Optional[Dict[str, Any]] = None

class AgentStatus(BaseModel):
    agent_name: str
    status: str
    last_activity: datetime
    message: str

# Simulation models
class SimulationRequest(BaseModel):
    simulations: int = 1000

class SimulationRoundGame(BaseModel):
    game_id: int
    round: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    home_seed: Optional[int] = None
    away_seed: Optional[int] = None
    game_date: Optional[datetime] = None
    venue: Optional[str] = None
    is_dome: Optional[bool] = False
    predicted_winner: Optional[str] = None
    advance_probability: Optional[float] = None

class SimulationResponse(BaseModel):
    season: int
    simulations: int
    title_odds: Dict[str, float]
    conference_championship_odds: Dict[str, float]
    advance_odds_by_round: Dict[str, Dict[str, float]]
    rounds: Dict[str, List[SimulationRoundGame]]

# Initialize agents
basic_agent = BasicPredictorAgent("Basic Predictor")
market_agent = MarketOddsAgent("Market Odds")
elo_agent = EloRatingAgent("Elo Ratings")
rest_agent = RestTravelAgent("Rest & Travel")
injury_agent = InjuryImpactAgent("Injury Impact")
# Display only - reports conditions, casts no vote. Retired from the
# ensemble at 51.1%, which is coin-flip level.
weather = WeatherProvider("Weather")
schedule_loader = NFLScheduleLoader(db_path="nfl_schedule.db")

def _seeded_win_probability(home_seed: Optional[int], away_seed: Optional[int]) -> float:
    if home_seed is None or away_seed is None:
        return 0.5
    try:
        seed_gap = int(away_seed) - int(home_seed)
    except (TypeError, ValueError):
        return 0.5
    advantage = seed_gap * 0.03
    return max(0.2, min(0.8, 0.5 + advantage))

def _group_playoff_games(games: List[Dict]) -> Dict[str, List[Dict]]:
    games_by_round: Dict[str, List[Dict]] = defaultdict(list)
    for game in games:
        round_name = game.get("round") or "Unknown"
        games_by_round[round_name].append(game)
    return games_by_round

# @app.get("/")
# async def root():
#     return {
#         "message": "NFL Agentic Prediction Service",
#         "status": "active",
#         "version": "1.0.0",
#         "agents": ["Basic Predictor", "Data Collector", "Weather Impact", "News Sentiment", "Market Intelligence"]
#     }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "agents_active": 5
    }

@app.get("/games/upcoming")
async def get_upcoming_games():
    """Get upcoming games from database"""
    games = schedule_loader.get_upcoming_games(limit=20)
    return {"games": games}

@app.get("/games/week/{week}")
async def get_games_by_week(
    week: int,
    season: int = Query(default=datetime.now().year),
    season_type: str = Query(default="regular")
):
    """
    Get all games for a specific week.

    Filters on season_type because playoff rounds reuse week numbers 1-4:
    without it, week 1 returns the regular season opener *and* the Wild Card
    round. Pass season_type=playoffs for postseason, or 'all' for both.
    """
    conn = sqlite3.connect(schedule_loader.db_path)
    cursor = conn.cursor()

    query = '''
        SELECT game_id, season, week, game_date, home_team, away_team, venue, is_dome, game_status
        FROM games
        WHERE week = ?
        AND season = ?
    '''
    params = [week, season]
    if season_type != "all":
        query += " AND season_type = ?"
        params.append(season_type)
    query += " ORDER BY game_date"

    cursor.execute(query, params)

    columns = [desc[0] for desc in cursor.description]
    games = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    conn.close()
    return {"games": games, "week": week, "season": season}

@app.get("/playoffs/{season}")
async def get_playoffs_by_season(season: int):
    """Get playoff games for a season"""
    games = schedule_loader.get_playoff_games_by_season(season)
    return {"season": season, "games": games}

@app.get("/playoffs/{season}/round/{round_name}")
async def get_playoffs_by_round(season: int, round_name: str):
    """Get playoff games for a season and round"""
    games = schedule_loader.get_playoff_games_by_round(season, round_name)
    return {"season": season, "round": round_name, "games": games}

@app.post("/playoffs/{season}/simulate")
async def simulate_playoffs(season: int, request: SimulationRequest) -> SimulationResponse:
    """Run playoff simulations and return title odds plus per-round advance probabilities."""
    if request.simulations <= 0:
        raise HTTPException(status_code=400, detail="Simulation count must be positive.")

    games = schedule_loader.get_playoff_games_by_season(season)
    if not games:
        raise HTTPException(status_code=404, detail=f"No playoff games found for season {season}.")

    games_by_round = _group_playoff_games(games)
    round_order = ["Wild Card", "Divisional", "Conference", "Championship"]
    round_names = [round_name for round_name in round_order if round_name in games_by_round]
    if not round_names:
        round_names = sorted(games_by_round.keys())

    title_counts: Dict[str, int] = defaultdict(int)
    conference_counts: Dict[str, int] = defaultdict(int)
    advance_counts_by_round: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    game_win_counts: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    game_total_counts: Dict[int, int] = defaultdict(int)

    conference_entry_round = (
        "Divisional"
        if "Divisional" in games_by_round
        else "Wild Card"
        if "Wild Card" in games_by_round
        else None
    )

    for _ in range(request.simulations):
        for round_name in round_names:
            for game in games_by_round.get(round_name, []):
                home_team = game.get("home_team")
                away_team = game.get("away_team")
                if not home_team or not away_team:
                    continue
                home_win_prob = _seeded_win_probability(game.get("home_seed"), game.get("away_seed"))
                winner = home_team if random.random() < home_win_prob else away_team
                game_id = game.get("game_id")
                if game_id is not None:
                    game_total_counts[game_id] += 1
                    game_win_counts[game_id][winner] += 1

                advance_counts_by_round[round_name][winner] += 1

                if conference_entry_round and round_name == conference_entry_round:
                    conference_counts[winner] += 1
                if round_name == "Championship":
                    title_counts[winner] += 1

    simulations = request.simulations
    title_odds = {
        team: round(count / simulations, 4)
        for team, count in title_counts.items()
    }
    conference_championship_odds = {
        team: round(count / simulations, 4)
        for team, count in conference_counts.items()
    }

    advance_odds_by_round: Dict[str, Dict[str, float]] = {}
    for round_name, counts in advance_counts_by_round.items():
        advance_odds_by_round[round_name] = {
            team: round(count / simulations, 4) for team, count in counts.items()
        }

    rounds_response: Dict[str, List[SimulationRoundGame]] = {}
    for round_name in round_names:
        round_games: List[SimulationRoundGame] = []
        for game in games_by_round.get(round_name, []):
            game_id = game.get("game_id")
            total = game_total_counts.get(game_id, 0)
            home_team = game.get("home_team")
            away_team = game.get("away_team")
            home_wins = game_win_counts.get(game_id, {}).get(home_team, 0)
            away_wins = game_win_counts.get(game_id, {}).get(away_team, 0)
            home_rate = home_wins / total if total else 0
            away_rate = away_wins / total if total else 0
            if home_rate >= away_rate:
                predicted_winner = home_team
                advance_probability = home_rate
            else:
                predicted_winner = away_team
                advance_probability = away_rate

            round_games.append(
                SimulationRoundGame(
                    game_id=game_id,
                    round=round_name,
                    home_team=home_team,
                    away_team=away_team,
                    home_seed=game.get("home_seed"),
                    away_seed=game.get("away_seed"),
                    game_date=game.get("game_date"),
                    venue=game.get("venue"),
                    is_dome=game.get("is_dome"),
                    predicted_winner=predicted_winner,
                    advance_probability=round(advance_probability, 4) if total else None
                )
            )
        rounds_response[round_name] = round_games

    return SimulationResponse(
        season=season,
        simulations=simulations,
        title_odds=title_odds,
        conference_championship_odds=conference_championship_odds,
        advance_odds_by_round=advance_odds_by_round,
        rounds=rounds_response
    )

@app.get("/agents/status")
async def get_agent_status() -> List[AgentStatus]:
    """Get status of all agents"""
    try:
        statuses = []
        
        # Check basic agent status
        basic_status = await basic_agent.get_status()
        statuses.append(AgentStatus(
            agent_name=basic_agent.name,
            status=basic_status["status"],
            last_activity=basic_status["last_activity"],
            message=basic_status["message"]
        ))
        
        
        # Check market agent status
        market_status = await market_agent.get_status()
        statuses.append(AgentStatus(
            agent_name=market_agent.name,
            status=market_status["status"],
            last_activity=market_status["last_activity"],
            message=market_status["message"]
        ))

        # Check Elo agent status
        elo_status = await elo_agent.get_status()
        statuses.append(AgentStatus(
            agent_name=elo_agent.name,
            status=elo_status["status"],
            last_activity=elo_status["last_activity"],
            message=elo_status["message"]
        ))

        # Check rest/travel agent status
        rest_status = await rest_agent.get_status()
        statuses.append(AgentStatus(
            agent_name=rest_agent.name,
            status=rest_status["status"],
            last_activity=rest_status["last_activity"],
            message=rest_status["message"]
        ))

        # Check injury agent status
        injury_status = await injury_agent.get_status()
        statuses.append(AgentStatus(
            agent_name=injury_agent.name,
            status=injury_status["status"],
            last_activity=injury_status["last_activity"],
            message=injury_status["message"]
        ))

        return statuses
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise _server_error("Prediction", e)

def agent_weight(agent_name: str) -> float:
    """An agent's calibrated influence, or the default for uncalibrated ones."""
    return max(0.0, AGENT_WEIGHTS.get(agent_name, DEFAULT_WEIGHT))


async def _run_all_agents(game_data):
    """
    Run every prediction agent against one game.

    Returns (predictions, agent_names) in matching order. Shared by /predict,
    which applies the consensus here, and /agents/predict-all, which returns
    the raw output so the Spring Boot gateway can apply its own weighted vote.
    """
    ordered_agents = [
        market_agent, basic_agent, elo_agent, rest_agent, injury_agent
    ]
    # game_context is vestigial. Every agent now fetches what it needs itself -
    # the game log, the odds feed, the injury report - so nothing reads it. It
    # stays in the signature because it is part of the agent contract.
    predictions = [
        await agent.predict_game(game_data, {})
        for agent in ordered_agents
    ]
    return predictions, [agent.name for agent in ordered_agents]


@app.post("/agents/predict-all")
async def predict_all_agents(request: PredictionRequest):
    """
    Raw per-agent predictions with no consensus applied.

    The Spring Boot gateway consumes this and runs the weighted vote itself,
    using weights persisted in Postgres.
    """
    try:
        predictions, agent_names = await _run_all_agents(request.game_data)
        return {
            "game_id": request.game_data.game_id,
            "home_team": request.game_data.home_team_name,
            "away_team": request.game_data.away_team_name,
            "agent_predictions": [
                {
                    "agent_name": agent_names[i],
                    "predicted_winner": pred["winner"],
                    "confidence": pred["confidence"],
                    "reasoning": pred["reasoning"],
                    "source": pred.get("source", "unknown")
                }
                for i, pred in enumerate(predictions)
            ],
            "prediction_time": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error running agents: {e}")
        raise _server_error("Agent refresh", e)


@app.post("/predict")
async def predict_game(request: PredictionRequest) -> PredictionResponse:
    """Generate prediction for a specific game using multiple agents"""
    try:
        logger.info(f"Generating prediction for game {request.game_data.game_id}")

        all_predictions, all_agent_names = await _run_all_agents(request.game_data)

        # Build the per-agent view, including how much each one counted
        agent_predictions = [
            AgentPrediction(
                agent_name=name,
                predicted_winner=pred["winner"],
                confidence=pred["confidence"],
                reasoning=pred["reasoning"],
                prediction_time=datetime.now(),
                weight=round(agent_weight(name), 4),
                contribution=round(agent_weight(name) * max(0.0, pred["confidence"] - 0.5), 5),
                has_data=pred["confidence"] != 0.5
            )
            for name, pred in zip(all_agent_names, all_predictions)
        ]

        # Count votes for each team
        home_team = request.game_data.home_team_name
        away_team = request.game_data.away_team_name

        consensus = build_consensus(all_predictions, all_agent_names, home_team, away_team)
        overall_winner = consensus["winner"]
        overall_confidence = consensus["confidence"]
        consensus_reasoning = consensus["reasoning"]
        home_votes = consensus["home_votes"]
        away_votes = consensus["away_votes"]

        for entry in agent_predictions:
            logger.info(
                f"{entry.agent_name} picks {entry.predicted_winner} "
                f"({entry.confidence:.2%}, contributes {entry.contribution:.4f})"
            )
        logger.info(
            f"Votes {home_votes}-{away_votes}; weighted {consensus.get('weighted_scores')}"
        )
        
        return PredictionResponse(
            game_id=request.game_data.game_id,
            overall_winner=overall_winner,
            overall_confidence=round(overall_confidence, 4),
            agent_predictions=agent_predictions,
            consensus_reasoning=consensus_reasoning,
            prediction_time=datetime.now(),
            consensus_method=consensus.get("method", "weighted"),
            home_votes=home_votes,
            away_votes=away_votes,
            weighted_scores=consensus.get("weighted_scores", {}),
            conditions=await weather.get_conditions(home_team)
        )
        
    except Exception as e:
        logger.error(f"Error generating prediction: {e}")
        raise _server_error("Game refresh", e)

@app.get("/games/results")
async def get_game_results(
    season: int = Query(default=datetime.now().year),
    week: Optional[int] = Query(default=None),
    season_type: str = Query(default="regular")
):
    """
    Completed games with final scores and the winner.

    Consumed by the gateway's weekly settle job, which scores stored
    predictions against these results.
    """
    conn = sqlite3.connect(schedule_loader.db_path)
    cursor = conn.cursor()

    query = '''
        SELECT game_id, season, week, game_date, home_team, away_team,
               home_score, away_score, game_status
        FROM games
        WHERE season = ?
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND home_team IS NOT NULL
          AND away_team IS NOT NULL
    '''
    params: List = [season]
    if season_type != "all":
        query += " AND season_type = ?"
        params.append(season_type)
    if week is not None:
        query += " AND week = ?"
        params.append(week)
    query += " ORDER BY game_date"

    cursor.execute(query, params)
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()

    for game in rows:
        if game["home_score"] > game["away_score"]:
            game["winner"] = game["home_team"]
        elif game["away_score"] > game["home_score"]:
            game["winner"] = game["away_team"]
        else:
            game["winner"] = None  # Tie - nothing to settle against

    return {"season": season, "week": week, "count": len(rows), "results": rows}


@app.post("/games/refresh")
async def refresh_schedule_from_espn(
    season: int = Query(default=datetime.now().year),
    include_playoffs: bool = Query(default=True)
):
    """
    Re-pull the schedule from ESPN so final scores land in the database.

    Rate-limited by the loader (one second between weeks), so this takes on the
    order of 20 seconds. Intended for the weekly job, not per-request use.
    """
    try:
        await schedule_loader.load_season(season, include_playoffs=include_playoffs)

        conn = sqlite3.connect(schedule_loader.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*), SUM(CASE WHEN home_score IS NOT NULL THEN 1 ELSE 0 END) "
            "FROM games WHERE season = ?",
            (season,)
        )
        total, completed = cursor.fetchone()
        conn.close()

        logger.info(f"Refreshed season {season}: {completed}/{total} games complete")
        return {
            "season": season,
            "games": total,
            "completed": completed or 0,
            "refreshed_at": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error refreshing schedule: {e}")
        raise _server_error("Playoff simulation", e)


@app.post("/reload")
async def reload_schedule():
    """Reload schedule data from database"""
    global schedule_loader
    schedule_loader = NFLScheduleLoader(db_path="nfl_schedule.db")
    return {"status": "reloaded"}

@app.post("/agents/refresh")
async def refresh_agents():
    """Refresh all agents with latest data"""
    try:
        await basic_agent.refresh()
        await market_agent.refresh()
        await elo_agent.refresh()
        await rest_agent.refresh()
        await injury_agent.refresh()
        await weather.refresh()
        return {"message": "All agents refreshed successfully"}
    except Exception as e:
        logger.error(f"Error refreshing agents: {e}")
        raise _server_error("Agent status", e)

# Individual agent testing endpoints
@app.post("/agents/basic/predict")
async def test_basic_prediction(request: PredictionRequest):
    """Test the basic prediction agent directly"""
    try:
        prediction = await basic_agent.predict_game(request.game_data, {})
        return prediction
    except Exception as e:
        raise _server_error("Agent prediction", e)

@app.post("/agents/market/predict")
async def test_market_prediction(request: PredictionRequest):
    """Test the market odds agent directly"""
    try:
        prediction = await market_agent.predict_game(request.game_data, {})
        return prediction
    except Exception as e:
        raise _server_error("Weight lookup", e)

# Agent comparison endpoint
@app.post("/agents/compare")
async def compare_agents(request: PredictionRequest):
    """
    Every agent's pick side by side, with how much each one counted.

    Built from _run_all_agents so it tracks the roster automatically - the
    previous version hardcoded four agents and silently went stale when the
    ensemble grew.
    """
    try:
        predictions, agent_names = await _run_all_agents(request.game_data)
        home = request.game_data.home_team_name
        away = request.game_data.away_team_name

        comparison = {
            name: {
                "winner": pred["winner"],
                "confidence": pred["confidence"],
                "reasoning": pred["reasoning"],
                "weight": round(agent_weight(name), 4),
                "contribution": round(agent_weight(name) * max(0.0, pred["confidence"] - 0.5), 5),
                "has_data": pred["confidence"] != 0.5,
            }
            for name, pred in zip(agent_names, predictions)
        }

        home_votes = sum(1 for pred in predictions if pred["winner"] == home)
        away_votes = sum(1 for pred in predictions if pred["winner"] == away)

        return {
            "game": f"{away} @ {home}",
            "agent_comparison": comparison,
            "agent_agreement": {
                "unanimous": len({pred["winner"] for pred in predictions}) == 1,
                "vote_count": {home: home_votes, away: away_votes},
            },
            "conditions": await weather.get_conditions(home),
        }
    except Exception as e:
        raise _server_error("Agent comparison", e)


def _resolve_within_build(full_path: str) -> Optional[str]:
    """
    Resolve a request path against the frontend build directory, returning it
    only if it stays inside that directory.

    Two ways the naive version escaped:
      * '../' sequences - percent-encoded, so the URL router hands them through
        as literal path segments ('/%2e%2e/%2e%2e/.env').
      * an absolute path - os.path.join() discards the base entirely when its
        second argument starts with '/', so '/etc/passwd' resolved to itself.

    realpath() also collapses symlinks, so a link inside the build directory
    cannot point outward either. Returns None if the path escapes.

    Restored after being deleted by an unrelated refactor (bb8f006, which
    retired the News Sentiment agent) while its call site below stayed. The
    result was a NameError on every unknown path - the catch-all returned 500
    rather than the SPA, and the guard this function provides was simply gone.
    tests/test_static_paths.py exists so a future deletion fails the build
    instead of shipping.
    """
    build_root = os.path.realpath(demo_build)
    candidate = os.path.realpath(os.path.join(build_root, full_path))

    try:
        if os.path.commonpath([candidate, build_root]) != build_root:
            return None
    except ValueError:
        # Different drives on Windows - not comparable, so treat as an escape
        return None

    return candidate


if os.path.exists(demo_build):
    @app.get("/{full_path:path}")
    async def serve_frontend_assets(full_path: str):
        safe_path = _resolve_within_build(full_path)

        if safe_path is not None and os.path.isfile(safe_path):
            return FileResponse(safe_path)

        # Anything else - missing file or attempted escape - falls back to the
        # SPA entry point, so client-side routes still work and a probe learns
        # nothing about what exists on disk.
        return FileResponse(os.path.join(os.path.realpath(demo_build), "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)

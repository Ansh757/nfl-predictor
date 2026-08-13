import sqlite3
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
from collections import defaultdict
import random
import os
import asyncio
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
from agents.data_collector import DataCollectorAgent
from agents.weather_agent import WeatherImpactAgent
from agents.news_sentiment_agent import NewsSentimentAgent
from agents.odds_agent import MarketOddsAgent
from agents.injury_agent import InjuryImpactAgent
from agents.consensus import build_consensus
from agents.elo_agent import EloRatingAgent
from agents.rest_travel_agent import RestTravelAgent
from utils.schedule_loader import NFLScheduleLoader

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
            "agents": ["Basic Predictor", "Data Collector", "Weather Impact", "News Sentiment",
                       "Market Odds", "Elo Ratings", "Rest & Travel", "Injury Impact"],
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

# Pydantic models
class GameData(BaseModel):
    game_id: int
    home_team_name: str
    away_team_name: str
    game_time: datetime
    venue: Optional[str] = None
    is_dome: Optional[bool] = False

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

class PredictionResponse(BaseModel):
    game_id: int
    overall_winner: str
    overall_confidence: float
    agent_predictions: List[AgentPrediction]
    consensus_reasoning: str
    prediction_time: datetime

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
data_agent = DataCollectorAgent("Data Collector")
weather_agent = WeatherImpactAgent("Weather Impact")
news_agent = NewsSentimentAgent("News Sentiment")
market_agent = MarketOddsAgent("Market Odds")
elo_agent = EloRatingAgent("Elo Ratings")
rest_agent = RestTravelAgent("Rest & Travel")
injury_agent = InjuryImpactAgent("Injury Impact")
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
        "agents_active": 8
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
        
        # Check data agent status
        data_status = await data_agent.get_status()
        statuses.append(AgentStatus(
            agent_name=data_agent.name,
            status=data_status["status"],
            last_activity=data_status["last_activity"],
            message=data_status["message"]
        ))
        
        # Check weather agent status
        weather_status = await weather_agent.get_status()
        statuses.append(AgentStatus(
            agent_name=weather_agent.name,
            status=weather_status["status"],
            last_activity=weather_status["last_activity"],
            message=weather_status["message"]
        ))
        
        # Check news agent status
        news_status = await news_agent.get_status()
        statuses.append(AgentStatus(
            agent_name=news_agent.name,
            status=news_status["status"],
            last_activity=news_status["last_activity"],
            message=news_status["message"]
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
        raise HTTPException(status_code=500, detail=str(e))

async def _run_all_agents(game_data):
    """
    Run every prediction agent against one game.

    Returns (predictions, agent_names) in matching order. Shared by /predict,
    which applies the consensus here, and /agents/predict-all, which returns
    the raw output so the Spring Boot gateway can apply its own weighted vote.
    """
    game_context = await data_agent.collect_game_data(game_data)

    ordered_agents = [
        basic_agent, weather_agent, news_agent,
        market_agent, elo_agent, rest_agent, injury_agent
    ]
    predictions = [
        await agent.predict_game(game_data, game_context)
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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict")
async def predict_game(request: PredictionRequest) -> PredictionResponse:
    """Generate prediction for a specific game using multiple agents"""
    try:
        logger.info(f"Generating prediction for game {request.game_data.game_id}")

        all_predictions, _ = await _run_all_agents(request.game_data)
        (basic_prediction, weather_prediction, news_prediction, market_prediction,
         elo_prediction, rest_prediction, injury_prediction) = all_predictions

        # Create agent prediction objects
        agent_predictions = [
            AgentPrediction(
                agent_name=basic_agent.name,
                predicted_winner=basic_prediction["winner"],
                confidence=basic_prediction["confidence"],
                reasoning=basic_prediction["reasoning"],
                prediction_time=datetime.now()
            ),
            AgentPrediction(
                agent_name=weather_agent.name,
                predicted_winner=weather_prediction["winner"],
                confidence=weather_prediction["confidence"],
                reasoning=weather_prediction["reasoning"],
                prediction_time=datetime.now()
            ),
            AgentPrediction(
                agent_name=news_agent.name,
                predicted_winner=news_prediction["winner"],
                confidence=news_prediction["confidence"],
                reasoning=news_prediction["reasoning"],
                prediction_time=datetime.now()
            ),
            AgentPrediction(
                agent_name=market_agent.name,
                predicted_winner=market_prediction["winner"],
                confidence=market_prediction["confidence"],
                reasoning=market_prediction["reasoning"],
                prediction_time=datetime.now()
            ),
            AgentPrediction(
                agent_name=elo_agent.name,
                predicted_winner=elo_prediction["winner"],
                confidence=elo_prediction["confidence"],
                reasoning=elo_prediction["reasoning"],
                prediction_time=datetime.now()
            ),
            AgentPrediction(
                agent_name=rest_agent.name,
                predicted_winner=rest_prediction["winner"],
                confidence=rest_prediction["confidence"],
                reasoning=rest_prediction["reasoning"],
                prediction_time=datetime.now()
            ),
            AgentPrediction(
                agent_name=injury_agent.name,
                predicted_winner=injury_prediction["winner"],
                confidence=injury_prediction["confidence"],
                reasoning=injury_prediction["reasoning"],
                prediction_time=datetime.now()
            )
        ]
        
        # Advanced 4-agent consensus
        predictions = [basic_prediction, weather_prediction, news_prediction,
                       market_prediction, elo_prediction, rest_prediction,
                       injury_prediction]
        agent_names = [basic_agent.name, weather_agent.name, news_agent.name,
                       market_agent.name, elo_agent.name, rest_agent.name,
                       injury_agent.name]
        
        # Count votes for each team
        home_team = request.game_data.home_team_name
        away_team = request.game_data.away_team_name

        consensus = build_consensus(predictions, agent_names, home_team, away_team)
        overall_winner = consensus["winner"]
        overall_confidence = consensus["confidence"]
        consensus_reasoning = consensus["reasoning"]
        home_votes = consensus["home_votes"]
        away_votes = consensus["away_votes"]

        logger.info(f"Basic Agent picks: {basic_prediction['winner']} ({basic_prediction['confidence']:.2%})")
        logger.info(f"Weather Agent picks: {weather_prediction['winner']} ({weather_prediction['confidence']:.2%})")
        logger.info(f"News Agent picks: {news_prediction['winner']} ({news_prediction['confidence']:.2%})")
        logger.info(f"Market Agent picks: {market_prediction['winner']} ({market_prediction['confidence']:.2%})")
        logger.info(f"Home votes: {home_votes}, Away votes: {away_votes}")
        
        return PredictionResponse(
            game_id=request.game_data.game_id,
            overall_winner=overall_winner,
            overall_confidence=round(overall_confidence, 4),
            agent_predictions=agent_predictions,
            consensus_reasoning=consensus_reasoning,
            prediction_time=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error generating prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        await data_agent.refresh()
        await weather_agent.refresh()
        await news_agent.refresh()
        await market_agent.refresh()
        await elo_agent.refresh()
        await rest_agent.refresh()
        await injury_agent.refresh()
        return {"message": "All agents refreshed successfully"}
    except Exception as e:
        logger.error(f"Error refreshing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Individual agent testing endpoints
@app.post("/agents/basic/predict")
async def test_basic_prediction(request: PredictionRequest):
    """Test the basic prediction agent directly"""
    try:
        game_context = await data_agent.collect_game_data(request.game_data)
        prediction = await basic_agent.predict_game(request.game_data, game_context)
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/weather/predict")
async def test_weather_prediction(request: PredictionRequest):
    """Test the weather prediction agent directly"""
    try:
        game_context = await data_agent.collect_game_data(request.game_data)
        prediction = await weather_agent.predict_game(request.game_data, game_context)
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/news/predict")
async def test_news_prediction(request: PredictionRequest):
    """Test the news sentiment agent directly"""
    try:
        game_context = await data_agent.collect_game_data(request.game_data)
        prediction = await news_agent.predict_game(request.game_data, game_context)
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/market/predict")
async def test_market_prediction(request: PredictionRequest):
    """Test the market odds agent directly"""
    try:
        game_context = await data_agent.collect_game_data(request.game_data)
        prediction = await market_agent.predict_game(request.game_data, game_context)
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Agent comparison endpoint
@app.post("/agents/compare")
async def compare_agents(request: PredictionRequest):
    """Compare all agent predictions side by side"""
    try:
        game_context = await data_agent.collect_game_data(request.game_data)
        
        # Get all predictions
        basic_pred = await basic_agent.predict_game(request.game_data, game_context)
        weather_pred = await weather_agent.predict_game(request.game_data, game_context)
        news_pred = await news_agent.predict_game(request.game_data, game_context)
        market_pred = await market_agent.predict_game(request.game_data, game_context)
        
        return {
            "game": f"{request.game_data.away_team_name} @ {request.game_data.home_team_name}",
            "agent_comparison": {
                "Basic Predictor": {
                    "winner": basic_pred["winner"],
                    "confidence": basic_pred["confidence"],
                    "reasoning": basic_pred["reasoning"]
                },
                "Weather Impact": {
                    "winner": weather_pred["winner"],
                    "confidence": weather_pred["confidence"],
                    "reasoning": weather_pred["reasoning"]
                },
                "News Sentiment": {
                    "winner": news_pred["winner"],
                    "confidence": news_pred["confidence"],
                    "reasoning": news_pred["reasoning"]
                },
                "Market Intelligence": {
                    "winner": market_pred["winner"],
                    "confidence": market_pred["confidence"],
                    "reasoning": market_pred["reasoning"]
                }
            },
            "agent_agreement": {
                "unanimous": len(set([basic_pred["winner"], weather_pred["winner"], news_pred["winner"], market_pred["winner"]])) == 1,
                "majority_winner": request.game_data.home_team_name if sum(1 for pred in [basic_pred, weather_pred, news_pred, market_pred] if pred["winner"] == request.game_data.home_team_name) >= 3 else request.game_data.away_team_name,
                "vote_count": {
                    request.game_data.home_team_name: sum(1 for pred in [basic_pred, weather_pred, news_pred, market_pred] if pred["winner"] == request.game_data.home_team_name),
                    request.game_data.away_team_name: sum(1 for pred in [basic_pred, weather_pred, news_pred, market_pred] if pred["winner"] == request.game_data.away_team_name)
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if os.path.exists(demo_build):
    @app.get("/{full_path:path}")
    async def serve_frontend_assets(full_path: str):
        file_path = os.path.join(demo_build, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(demo_build, "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)

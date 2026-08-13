# 🏈 NFL Prediction System

Ensemble prediction system combining statistical models and real-time data to predict NFL games.
Measured at **62.3% accuracy** across the full 2025 regular season (272 games).

## 🎯 Results

Full-season backtest, 2025 regular season, weeks 1–18. Three of the four agents are
stochastic, so every number below is the mean of **20 independent runs** over the same
272 games. "Correct" is out of the games played that week.

| Week | Games | Correct (mean) | Accuracy | Best run | Worst run |
|------|-------|----------------|----------|----------|-----------|
| 1  | 16 | 10.8 | 67.8% | 14 | 8  |
| 2  | 16 | 11.8 | 73.4% | 13 | 10 |
| 3  | 16 | 9.9  | 62.2% | 12 | 8  |
| 4  | 16 | 10.6 | 66.2% | 13 | 8  |
| 5  | 14 | 7.3  | 52.5% | 9  | 5  |
| 6  | 15 | 8.9  | 59.3% | 11 | 3  |
| 7  | 15 | 7.9  | 52.7% | 10 | 6  |
| 8  | 13 | 6.8  | 52.7% | 11 | 5  |
| 9  | 14 | 6.7  | 47.9% | 8  | 5  |
| 10 | 14 | 9.5  | 67.9% | 12 | 7  |
| 11 | 15 | 10.1 | 67.0% | 12 | 8  |
| 12 | 14 | 9.8  | 70.4% | 12 | 8  |
| 13 | 16 | 9.8  | 61.6% | 12 | 8  |
| 14 | 14 | 8.9  | 63.6% | 10 | 8  |
| 15 | 16 | 10.3 | 64.4% | 12 | 7  |
| 16 | 16 | 10.3 | 64.4% | 13 | 8  |
| 17 | 16 | 9.6  | 60.0% | 12 | 8  |
| 18 | 16 | 10.2 | 63.4% | 12 | 6  |

| Metric | Value |
|--------|-------|
| **Season accuracy** | **62.3%** (± 2.3%) |
| Run-to-run range | 58.1% – 66.9% |
| Home picks | 60.8% |
| Always-pick-home baseline | 53.7% |

**Comparison:** most public models land in the 55–65% range on straight-up winners, so the
ensemble is a modest but real improvement over the always-pick-home baseline.

### Across five seasons

| Season | Games | Ensemble | Best agent alone | Always-home baseline |
|--------|-------|----------|------------------|----------------------|
| 2021 | 272 | 57.2% | 59.2% | 51.5% |
| 2022 | 271 | 59.6% | 61.3% | 55.7% |
| 2023 | 272 | 60.0% | 62.9% | 55.5% |
| 2024 | 272 | 61.7% | 65.1% | 53.3% |
| 2025 | 272 | 62.3% | 66.9% | 53.7% |

### Per-agent accuracy (2025)

| Agent | Accuracy | Signal quality |
|-------|----------|----------------|
| Basic Predictor | **66.9%** | Real point-in-time records, point differential, form |
| Weather Impact | 52.6% (± 2.1%) | Weak — only 10 of 32 teams have a weather profile |
| News Sentiment | 48.9% (± 3.3%) | Coin flip — keyword counting over headlines |
| Market Intelligence | 49.6% (± 3.1%) | Coin flip — betting data is synthetic, not scraped |

> **Known issue:** the ensemble scores *below* its own strongest component in every season
> tested. Three of the four voters are close to random, and an equal-weight majority vote
> dilutes the one agent carrying real signal. Confidence-weighting the vote, or dropping the
> synthetic agents, is the clearest path to improving these numbers.

## 🧪 Reproducing the backtest

```bash
cd agent-service
pip install -r requirements.txt
python backtest.py --season 2025 --runs 20
```

The harness ([`agent-service/backtest.py`](agent-service/backtest.py)) replays the same four
agents and the exact same voting function used by `POST /predict`
([`agents/consensus.py`](agent-service/agents/consensus.py)), then scores each pick against
the final score stored in `nfl_schedule.db`.

**Methodology.** Team statistics are rebuilt from the game log using only games that kicked
off *before* the game being predicted — a rolling window of each team's most recent 17 games,
which reaches back into the previous season during the early weeks. The live ESPN endpoint is
deliberately not called, because it returns *current* standings and would leak the final
results of the season under test.

**What the backtest cannot replay faithfully:**

- **Weather** — the free endpoints serve current conditions only; there is no way to fetch the
  weather at a 2025 kickoff today. The agent falls back to its own seasonal simulation, keyed
  to the real month of the game.
- **News** — RSS feeds carry today's headlines, not the ones published in the game week, so the
  agent runs in simulated-scenario mode.
- **Market Intelligence** — generates synthetic betting data in production too, so it is
  replayed unchanged.

In live use the weather and news agents read real data, but neither shows enough signal in
backtest to expect a materially different result.

## 🧠 How It Works

Ensemble system combining 4 specialized predictors:

1. **Basic Predictor**: Analyzes team performance metrics
   - Win/loss records and point differential (ESPN API, with Pro Football Reference fallback)
   - Recent form (last 4 games) and home/away splits
   - Weighted strength score plus a 2.5-point home field advantage

2. **Weather Impact**: Real-time weather
   - Live data from Open-Meteo → WeatherAPI → NOAA, keyed to hardcoded stadium coordinates
   - Dome detection short-circuits the weather analysis entirely
   - Per-team cold/heat/wind profiles (currently defined for 10 of 32 teams)

3. **News Sentiment**: Media coverage analysis
   - Scrapes five NFL RSS feeds (ESPN, NFL.com, CBS, PFT, Bleacher Report)
   - Positive/negative keyword scoring, bucketed into chemistry, coaching, injuries,
     momentum, and motivation

4. **Market Intelligence**: Betting market patterns
   - Line movement, public vs sharp money splits, steam moves, reverse line movement
   - ⚠️ All of it is **simulated** — no sportsbook is contacted

Each agent returns a winner, a confidence, and reasoning. The consensus takes a majority vote,
averages the confidence of the winning side, adds +0.05 when unanimous, and breaks a 2–2 split
with the single most confident agent (discounted 10%).

## 🚀 Tech Stack

- **Deployed service**: Python FastAPI agent service — serves the API *and* the built React app
- **Also in repo**: Java Spring Boot API (`backend/`) that proxies the agent service; not
  currently wired into the Docker Compose stack or the Railway deploy
- **Data Sources**: ESPN API, Open-Meteo, NOAA, RSS feeds
- **Frontend**: React 19 dashboard, React Native (Next)
- **Database**: SQLite for schedule/results, PostgreSQL for team metadata

## 📊 Key Features

- Real team statistics from ESPN
- Live weather data (no API key required)
- Bias control — 60.8% home picks against a 53.7% home win rate
- Confidence scoring for each prediction
- Playoff bracket viewer with Monte Carlo simulation
- Dockerized for easy deployment

## 🔧 Setup

### Live Demo

https://nfl-predictor-system-production.up.railway.app/

Proof of concept. The React Native app is still in progress — the goal was to confirm the
agents work accurately before building out a full mobile application.

### For Developers

```bash
git clone https://github.com/Ansh757/nfl-predictor.git
cd nfl-predictor

# Optional: add a .env with your own WEATHER_API_KEY
# (Open-Meteo and NOAA need no key, so the weather agent works without one)
cp .env.example .env

docker-compose up -d
```

### Service Ports (Docker)
- **Python agent service**: http://localhost:8001
- **PostgreSQL**: localhost:5433
- **Redis**: localhost:6379

### Loading schedule data

```bash
cd agent-service
python utils/schedule_loader.py --seasons 2021-2025   # regular season + playoffs
```

# 🏈 NFL Prediction System

Ensemble prediction system combining statistical models and real-time data to predict NFL games.
Measured at **66.5% accuracy** across the full 2025 regular season (272 games), against a
53.7% always-pick-home baseline.

## 🎯 Results

Full-season backtest, 2025 regular season, weeks 1–18, mean of 10 independent runs. Agent
weights were fitted on 2021–2024 only, so 2025 is out-of-sample.

| Week | Games | Correct | Accuracy |
|------|-------|---------|----------|
| 1  | 16 | 11 | 68.8% |
| 2  | 16 | 13 | 81.2% |
| 3  | 16 | 10 | 62.5% |
| 4  | 16 | 12 | 75.0% |
| 5  | 14 | 8  | 57.1% |
| 6  | 15 | 10 | 66.7% |
| 7  | 15 | 9  | 60.0% |
| 8  | 13 | 8  | 61.5% |
| 9  | 14 | 7  | 50.0% |
| 10 | 14 | 9  | 64.3% |
| 11 | 15 | 11 | 73.3% |
| 12 | 14 | 11 | 78.6% |
| 13 | 16 | 10 | 62.5% |
| 14 | 14 | 10 | 71.4% |
| 15 | 16 | 9  | 56.2% |
| 16 | 16 | 12 | 75.0% |
| 17 | 16 | 10 | 62.5% |
| 18 | 16 | 10 | 62.5% |

| Metric | Value |
|--------|-------|
| **Season accuracy** | **66.5%** |
| Home picks | 63.6% |
| Always-pick-home baseline | 53.7% |

**Comparison:** most public models land in the 55–65% range on straight-up winners.

### Across five seasons

| Season | Ensemble | Best single agent | Always-home |
|--------|----------|-------------------|-------------|
| 2021 | 59.6% | 59.2% | 51.5% |
| 2022 | 62.4% | 63.1% | 55.7% |
| 2023 | 63.1% | 62.9% | 55.5% |
| 2024 | 67.4% | 69.1% | 53.3% |
| 2025 | 66.5% | 66.9% | 53.7% |
| **Mean** | **63.8%** | 63.1% | 53.9% |

Predictions are deterministic — run-to-run variance is 0.0%, because agents that showed no
measurable edge carry zero weight and cannot perturb the result.

### Per-agent accuracy

Weights come from measured accuracy on 2021–2024: an agent's weight is its edge over a coin
flip, floored at zero. An agent that cannot beat 50% contributes nothing.

| Agent | Accuracy | Weight | Data source |
|-------|----------|--------|-------------|
| Basic Predictor | 62.1% | 0.121 | ESPN records, point differential, form |
| Elo Ratings | 61.5% | 0.115 | Local game log — opponent-adjusted power ratings |
| Rest & Travel | 52.2% | 0.022 | Schedule — rest days, byes, travel, timezones |
| Weather Impact | 51.1% | 0.011 | Open-Meteo / NOAA |
| News Sentiment | 49.7% | 0.0 | RSS keyword sentiment — no measurable edge |
| Market Odds | not backtestable | 0.02 | The Odds API — real consensus lines |
| Injury Impact | not backtestable | 0.02 | ESPN injury reports |

Elo's 61.5% understates it: 2021 is a cold start, since the game log begins there and every
team opens at league average. From 2022 on it averages 63.8%, and in 2024 it was the single
best agent at 69.1%.

**Market Odds and Injury Impact cannot be backtested.** The free odds tier serves current
lines only, and ESPN publishes no historical injury archive — so unlike every other agent,
their edge has never been measured on this data. They ship at a deliberately small default
weight. Market Odds is almost certainly worth more than 0.02 (closing lines typically predict
straight-up winners in the high 60s), but an unmeasured weight has no business outvoting a
measured one. The gateway records every live prediction so both can eventually be calibrated
properly.

## 🧪 Reproducing the backtest

```bash
cd agent-service
pip install -r requirements.txt
python backtest.py --season 2025 --runs 10                 # weighted voting (default)
python backtest.py --season 2025 --runs 10 --method majority   # one agent, one vote
```

The harness ([`agent-service/backtest.py`](agent-service/backtest.py)) replays the same agents
and the same voting function used by `POST /predict`
([`agents/consensus.py`](agent-service/agents/consensus.py)), then scores each pick against the
final score in `nfl_schedule.db`.

**Methodology.** Team statistics are rebuilt from the game log using only games that kicked off
*before* the game being predicted — a rolling 17-game window that reaches into the previous
season during the early weeks. Elo walks the log forward and records each team's rating as it
stood at kickoff. The live ESPN endpoint is deliberately not called, because it returns
*current* standings and would leak the results of the season under test.

**What the backtest cannot replay:**

| Agent | Why |
|---|---|
| Weather | Free endpoints serve current conditions only; falls back to seasonal simulation keyed to the game's real month |
| News | RSS carries today's headlines, not the game week's; runs in simulated-scenario mode |
| Market Odds | No historical odds on the free tier; runs inert (contributes nothing) |
| Injury Impact | No historical injury archive; runs inert |

Inert agents return confidence exactly 0.50. Since weighted consensus scores on
`confidence − 0.5`, they contribute nothing rather than injecting noise.

## 🧠 How It Works

Seven agents each return a winner, a confidence, and reasoning:

1. **Basic Predictor** — win/loss records and point differential (ESPN, with Pro Football
   Reference fallback), recent form, home/away splits, plus a 2.5-point home field advantage.
2. **Elo Ratings** — opponent-adjusted power ratings with a margin-of-victory multiplier and
   offseason regression to the mean. Where the Basic Predictor sees a raw 3–1 record, Elo knows
   whether it came against strong or weak opponents.
3. **Rest & Travel** — rest differential, bye weeks, short weeks, haversine travel distance and
   eastward body-clock penalties. Small by nature, but consistently positive.
4. **Weather Impact** — live conditions from Open-Meteo → WeatherAPI → NOAA. Dome detection
   short-circuits the analysis. Currently only 10 of 32 teams have a weather profile, which is
   why its measured edge is thin.
5. **News Sentiment** — five NFL RSS feeds scored by keyword sentiment.
6. **Market Odds** — real consensus moneyline across US sportsbooks, with the bookmaker's vig
   removed. Requires `ODDS_API_KEY`; inert without one.
7. **Injury Impact** — real ESPN injury reports weighted by position (a quarterback matters far
   more than a backup safety) and report status.

**The weighted vote.** Each agent contributes `weight × (confidence − 0.5)` to its pick; the
higher total wins. This replaced an equal-weight majority vote that was worth 3.6 percentage
points less and, in every season tested, scored *below* its own best component — three
near-random voters were diluting the one carrying signal.

> Note for anyone extending this: the original vote counter only handled N-0 and (N-1)-1
> splits and silently fell through to "most confident agent wins" for everything else. That was
> invisible with exactly four agents, where 4-0, 3-1 and 2-2 are the only possibilities, but it
> discarded the majority on a 3-2 split the moment a fifth agent was added. Fixed in
> `agents/consensus.py`.

## 🏗️ Architecture

```
React dashboard ──┬──> Python agent service (FastAPI, :8001)  ── runs the 7 agents
                  │         └── SQLite: schedule, scores, Elo history
                  │
                  └──> Java gateway (Spring Boot, :8080)
                            ├── owns the weighted vote (weights in Postgres)
                            ├── fans out across a week's games concurrently
                            ├── caches predictions in Redis
                            └── persists every prediction for live scoring
```

The Python service runs the agents; the Java gateway decides what their output means. Keeping
the vote in Java means agent weights live in Postgres and can be recalibrated without a
redeploy, and every prediction is recorded so accuracy can be measured continuously rather than
only offline.

### Gateway endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/gateway/predictions/week/{week}?season=` | Predict a full week, fanned out concurrently |
| `GET /api/gateway/predictions/game/{id}?homeTeam=&awayTeam=` | Predict one matchup |
| `POST /api/gateway/predictions/{gameId}/settle?actualWinner=` | Record a result |
| `GET /api/gateway/accuracy` | Live accuracy across settled predictions |
| `GET /api/gateway/weights` | Current agent weights |
| `POST /api/gateway/weights/refresh` | Drop the weight cache after recalibration |

## 🚀 Tech Stack

- **Java Spring Boot** gateway — orchestration, weighted voting, persistence, caching
- **Python FastAPI** agent service — the seven agents; also serves the built React app
- **React 19** dashboard with Tailwind
- **PostgreSQL** for agent weights, prediction history and team metadata
- **Redis** for prediction and weight caching
- **SQLite** for schedule, results and Elo history
- **Data sources**: ESPN, Open-Meteo, NOAA, The Odds API, RSS feeds

## 🔧 Setup

### Live Demo

https://nfl-predictor-system-production.up.railway.app/

Proof of concept. The React Native app is still in progress — the goal was to confirm the
agents work accurately before building out a full mobile application.

### For Developers

```bash
git clone https://github.com/Ansh757/nfl-predictor.git
cd nfl-predictor

cp .env.example .env      # then fill in any keys you want
docker-compose up -d
```

All API keys are optional — the system runs without any of them:

| Key | Effect if missing |
|-----|-------------------|
| `ODDS_API_KEY` | Market Odds agent stays inert. Free tier at [the-odds-api.com](https://the-odds-api.com) |
| `WEATHER_API_KEY` | Weather still works — Open-Meteo and NOAA need no key |
| `NFL_API_KEY` | Stats still work — ESPN and PFR are tried first |

### Service Ports

- **Java gateway**: http://localhost:8080
- **Python agent service**: http://localhost:8001
- **PostgreSQL**: localhost:5433
- **Redis**: localhost:6379

### Loading schedule data

```bash
cd agent-service
python utils/schedule_loader.py --seasons 2021-2025   # regular season + playoffs
```

## 📊 Key Features

- Seven agents, each weighted by measured accuracy rather than treated as equals
- Real team statistics, weather, injury reports and betting lines
- Bias control — 63.6% home picks against a 53.7% home win rate
- Walk-forward backtest harness with strict point-in-time discipline
- Playoff bracket viewer with Monte Carlo simulation
- Fully Dockerized

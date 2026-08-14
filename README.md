# 🏈 NFL Prediction System

Ensemble prediction system combining statistical models and real-time data to predict NFL games.
Measured at **68.0% accuracy** across the full 2025 regular season (272 games), against a
53.7% always-pick-home baseline.

## 🎯 Results

Full-season backtest, 2025 regular season, weeks 1–18. Agent weights were fitted on 2021–2024
only, so **2025 is out-of-sample**. Predictions are deterministic — every agent carrying weight
is deterministic, so these numbers reproduce exactly.

| Week | Games | Correct | Accuracy |
|------|-------|---------|----------|
| 1  | 16 | 12 | 75.0% |
| 2  | 16 | 14 | 87.5% |
| 3  | 16 | 10 | 62.5% |
| 4  | 16 | 12 | 75.0% |
| 5  | 14 | 8 | 57.1% |
| 6  | 15 | 11 | 73.3% |
| 7  | 15 | 10 | 66.7% |
| 8  | 13 | 9 | 69.2% |
| 9  | 14 | 8 | 57.1% |
| 10 | 14 | 9 | 64.3% |
| 11 | 15 | 10 | 66.7% |
| 12 | 14 | 11 | 78.6% |
| 13 | 16 | 9 | 56.2% |
| 14 | 14 | 10 | 71.4% |
| 15 | 16 | 10 | 62.5% |
| 16 | 16 | 12 | 75.0% |
| 17 | 16 | 10 | 62.5% |
| 18 | 16 | 10 | 62.5% |

| Metric | Value |
|--------|-------|
| **Season accuracy** | **68.0%** |
| Home picks | 63.6% |
| Always-pick-home baseline | 53.7% |

**Comparison:** most public models land in the 55–65% range on straight-up winners.

### Across five seasons

| Season | Ensemble | Best single agent | Always-home |
|--------|----------|-------------------|-------------|
| 2021 | 61.4% | 60.7% | 51.5% |
| 2022 | 62.7% | 65.7% | 55.7% |
| 2023 | 64.7% | 67.6% | 55.5% |
| 2024 | 69.5% | 71.7% | 53.3% |
| 2025 | **68.0%** | 66.9% | 53.7% |
| **Mean** | **65.3%** | 66.5% | 53.9% |

Predictions are deterministic — run-to-run variance is 0.0%, because agents that showed no
measurable edge carry zero weight and cannot perturb the result.

### Per-agent accuracy

Weights come from measured accuracy on 2021–2024: an agent's weight is its edge over a coin
flip, floored at zero. An agent that cannot beat 50% contributes nothing.

| Agent | Accuracy | Weight | Data source |
|-------|----------|--------|-------------|
| Market Odds | **66.4%** | 0.164 | The Odds API live / nflverse historical closing lines |
| Basic Predictor | 62.1% | 0.121 | ESPN records, point differential, form |
| Elo Ratings | 61.5% | 0.115 | Local game log — opponent-adjusted power ratings |
| Rest & Travel | 52.2% | 0.022 | Schedule — rest days, byes, travel, timezones |
| Injury Impact | not backtestable | 0.02 | ESPN injury reports |

**Two agents were retired.** Weather Impact (51.1%) and News Sentiment (49.7%) both measured
at coin-flip level, and removing them made the ensemble marginally *better* (+0.07 points
over five seasons) while cutting ~4 seconds of latency per cold prediction. The reason is
structural rather than fixable: sportsbooks move lines on wind forecasts and injury news, so
by kickoff the market has already priced whatever they are worth. An agent re-deriving that
adds nothing alongside Market Odds. Conditions are still fetched and displayed as game
context — they just no longer vote.

Elo's 61.5% understates it: 2021 is a cold start, since the game log begins there and every
team opens at league average. From 2022 on it averages 63.8%, and in 2024 it was the single
best agent at 69.1%.

**Read the five-season table carefully.** Weights were fitted on 2021–2024, so those four
seasons are in-sample and Market Odds alone beats the ensemble on three of them. **2025 is the
only unbiased estimate**, and there the ensemble (68.0%) beats every individual agent — Basic
Predictor 66.9%, Market Odds 65.4%, Elo 64.3%. That is the number to trust.

**Injury Impact still cannot be backtested.** ESPN publishes no historical injury archive, so
its edge has never been measured; it ships at a deliberately small default weight. The gateway
records every live prediction so it can eventually be calibrated properly.

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
| Injury Impact | No historical injury archive; runs inert (contributes nothing) |

Inert agents return confidence exactly 0.50. Since weighted consensus scores on
`confidence − 0.5`, they contribute nothing rather than injecting noise.

**Market Odds is backtested against real closing lines.** The Odds API's historical endpoint is
paid-only, so the backtest sources closing moneylines from
[nflverse](https://github.com/nflverse/nfldata) instead — free, and covering all 272 games in
every season. The backtest drives the *real* `MarketOddsAgent` through an adapter, so it
exercises the agent's actual de-vigging and confidence logic rather than a reimplementation.
Closing lines are fixed before kickoff, so this is not lookahead.

## 🧠 How It Works

Five agents each return a winner, a confidence, and reasoning:

1. **Basic Predictor** — win/loss records and point differential (ESPN, with Pro Football
   Reference fallback), recent form, home/away splits, plus a 2.5-point home field advantage.
2. **Elo Ratings** — opponent-adjusted power ratings with a margin-of-victory multiplier and
   offseason regression to the mean. Where the Basic Predictor sees a raw 3–1 record, Elo knows
   whether it came against strong or weak opponents.
3. **Rest & Travel** — rest differential, bye weeks, short weeks, haversine travel distance and
   eastward body-clock penalties. Small by nature, but consistently positive.
1. **Market Odds** — real consensus moneyline across US sportsbooks with the bookmaker's vig
   removed, and the single strongest agent at 66.4%. Requires `ODDS_API_KEY` for live
   predictions; inert without one. Backtests against free nflverse closing lines.
5. **Injury Impact** — real ESPN injury reports weighted by position (a quarterback matters far
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
React dashboard ──┬──> Python agent service (FastAPI, :8001)  ── runs the 5 agents
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
| `POST /api/gateway/predictions/{gameId}/settle?actualWinner=` | Record a single result |
| `POST /api/gateway/settle/run?season=&refresh=` | Run the weekly settlement now |
| `GET /api/gateway/accuracy` | Live accuracy across settled predictions |
| `GET /api/gateway/weights` | Current agent weights |
| `POST /api/gateway/weights/refresh` | Drop the weight cache after recalibration |

### Weekly settlement

A prediction is only worth storing if something eventually scores it. Every Tuesday at 09:00 —
late enough that Monday night is final — the gateway re-pulls results from ESPN and marks each
stored prediction correct or incorrect.

This is what makes Injury Impact calibratable. It has no historical archive to backtest
against, so its weight can only ever come from settled live predictions. Cron and enablement
are configurable under `prediction.settlement` in `application.yml`.

### Odds quota

The free Odds API tier allows 500 requests/month. One request returns every upcoming game, so
the whole payload is cached rather than queried per game — and the cache TTL is kickoff-aware:

| Situation | TTL | Why |
|---|---|---|
| No game within 30 min | 12 hours | Lines barely move days out |
| Game within 30 min | 10 minutes | Capture line movement into kickoff |

That costs roughly 125 requests/month against the 500 available. It also *improves* accuracy:
the 66.4% figure was measured on closing lines, so pricing captured near kickoff is what the
agent's weight was calibrated against. Tune with `ODDS_IDLE_TTL_HOURS`,
`ODDS_KICKOFF_TTL_MINUTES` and `ODDS_KICKOFF_WINDOW_MINUTES`.

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
python utils/schedule_loader.py --seasons 2021-2026   # regular season + playoffs
```

Results refresh automatically via the gateway's weekly job, or on demand:

```bash
curl -X POST "http://localhost:8001/games/refresh?season=2026"
```

### Deploying the gateway to Railway

The Python service and the gateway deploy as two Railway services from the same repo.

1. **New service** → same repo, set **Root Directory** to `backend/`. It picks up
   `backend/railway.json` and `backend/Dockerfile`.
2. **Add the Postgres and Redis plugins** to the project. The `railway` Spring profile reads
   `PGHOST`/`PGPORT`/`PGDATABASE`/`PGUSER`/`PGPASSWORD` and `REDISHOST`/`REDISPORT`/
   `REDISPASSWORD` directly, so no manual database wiring is needed.
3. **Set `AGENT_SERVICE_URL`** on the gateway service to the Python service's internal address,
   e.g. `http://nfl-predictor-system.railway.internal:8001`.
4. **Point the frontend at it** by setting `REACT_APP_API_URL` to the gateway's public URL on
   the *Python* service (the frontend is built into that image). Leave it unset to keep calling
   the Python service directly.

`ODDS_API_KEY` belongs on the **Python** service — that is where the agents run.

## 📊 Key Features

- Five agents, each weighted by measured accuracy rather than treated as equals
- Real team statistics, weather, injury reports and betting lines
- Bias control — 63.6% home picks against a 53.7% home win rate
- Walk-forward backtest harness with strict point-in-time discipline
- Playoff bracket viewer with Monte Carlo simulation
- Fully Dockerized

# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What actually ships

Despite three top-level services, **only the Python agent service is deployed**.

| Path | Role |
|------|------|
| `agent-service/` | FastAPI app. Serves the prediction API **and** the built React frontend. This is the deployed artifact. |
| `demo/` | React 19 + Tailwind dashboard. Built into the Python image at Docker stage 1 and served from `/`. |
| `backend/` | Java Spring Boot proxy in front of the agent service. Compiles, but is **not** in `docker-compose.yml` and **not** in the Railway deploy. Nothing routes through it today. |
| `mobile-app/` | Empty placeholder for the planned React Native app. |
| `database/init.sql` | PostgreSQL seed — 32 teams with fixed IDs. Only the Spring Boot service reads it. |

The root `Dockerfile` builds React, copies it to `/app/demo/build`, and runs `python main.py`.
`railway.json` points at that Dockerfile. `demo/src/App.js` hardcodes the production Railway URL
as its default `apiUrl`, so the frontend calls FastAPI directly and skips Spring Boot entirely.

## Commands

```bash
# Run the agent service locally (serves API + frontend if demo/build exists)
cd agent-service && python main.py            # → http://localhost:8001

# Full stack (postgres + redis + agent service; no Spring Boot)
docker-compose up -d

# Tests
cd agent-service && python -m pytest tests/ -q

# Backtest the ensemble against historical results
cd agent-service && python backtest.py --season 2025 --runs 20

# Load / refresh schedule data from ESPN
cd agent-service && python utils/schedule_loader.py --seasons 2021-2025

# Frontend dev server
cd demo && npm start
```

## Prediction flow

`POST /predict` in `main.py`:

1. `DataCollectorAgent.collect_game_data()` (`agents/data_collector.py`) builds a context dict.
   Everything it returns is **simulated** — it exists mostly to supply shape, not signal.
2. Four agents each return `{winner, confidence, reasoning, ...}`:
   - `agents/basic_predictor.py` — the only agent with real predictive signal. Pulls records
     from ESPN via `utils/api_clients.py` (ESPN → PFR scrape → sportsdata.io fallback chain),
     caches 2h, scores a weighted strength function plus 2.5 home-field points.
   - `agents/weather_agent.py` — real weather (Open-Meteo → WeatherAPI → NOAA). Backtests at
     ~50%; only 10 of 32 teams have a `team_weather_profiles` entry, so for the other 22 both
     advantages compute to 0.0 and line ~536 resolves the pick with `random.random()`.
   - `agents/news_sentiment_agent.py` — RSS scraping via `utils/news_scraper.py`, scored by
     positive/negative keyword counts. Backtests at ~49%.
   - `agents/market_intelligence_agent.py` — **entirely synthetic.** No sportsbook is contacted;
     lines, splits, and "sharp money" are `random` draws. Backtests at ~50%.
3. `agents/consensus.py::build_consensus()` — majority vote, mean confidence of the winning
   side, +0.05 if unanimous, 2–2 split broken by the most confident agent (×0.9).

**Keep `build_consensus` shared.** `main.py` and `backtest.py` both call it so that measured
accuracy reflects the code that actually serves predictions. Don't inline voting logic back
into either caller.

## Measured accuracy

Walk-forward backtest, mean of 20 runs per season (see README for the per-week table):

| Season | Ensemble | Basic Predictor alone | Always-home |
|--------|----------|----------------------|-------------|
| 2021 | 57.2% | 59.2% | 51.5% |
| 2022 | 59.6% | 61.3% | 55.7% |
| 2023 | 60.0% | 62.9% | 55.5% |
| 2024 | 61.7% | 65.1% | 53.3% |
| 2025 | 62.3% | 66.9% | 53.7% |

The ensemble scores **below its own best component in every season**, because three of four
equal-weight voters are near-random. Any accuracy work should start here: confidence-weight the
vote, or stop counting the synthetic agents.

## Data layer

Two unrelated databases:

- **`agent-service/nfl_schedule.db`** (SQLite, committed) — the `games` table: schedule, venue,
  final scores, playoff seeds/rounds. Holds 2021–2025 regular season and playoffs. `espn_game_id`
  carries a UNIQUE index and `_store_games()` upserts on it. This is what the app actually reads.
- **PostgreSQL** — team metadata only, via `database/init.sql`. Only Spring Boot touches it.

`NFLScheduleLoader.__init__` runs DDL and a dedupe DELETE on every instantiation, so importing
`main.py` mutates the SQLite file. Expect `nfl_schedule.db` to show as modified in `git status`.

## Gotchas

- **Path traversal in the SPA catch-all.** `main.py` `/{full_path:path}` joins unsanitized user
  input onto `demo_build` and returns it as a `FileResponse`. Encoded `../` can escape the build
  directory. Not yet fixed.
- **The playoff simulator doesn't propagate a bracket.** `/playoffs/{season}/simulate` flips a
  seed-gap-weighted coin on each round's *stored* matchups independently; winners never advance,
  and the agents aren't involved. Only meaningful for seasons already played.
- **`weather_agent.predict_game` overwrites `home_team`** from `game_context['home_team_stats']['team']`
  at lines 162–164, and `KeyError`s if the context is incomplete. It also ignores `game_data.venue`
  in favor of the `TEAM_TO_VENUE` lookup.
- **`/games/week/{week}` opens `sqlite3.connect("nfl_schedule.db")` on a relative path** rather
  than going through `schedule_loader`, so it depends on the process working directory.
- **CORS is inconsistent** — FastAPI allowlists three origins; the Spring Boot controllers use
  `@CrossOrigin(origins = "*")`.
- **One known-failing test**: `test_analyze_team_sentiment_fallback` asserts `article_count == 0`
  but the collector's fallback payload carries 2 headlines. Pre-existing.
- **Agent randomness is module-global `random`.** Backtests average over multiple runs rather
  than seeding for bit-exact reproducibility.

## Conventions

- Agents are plain classes, not a framework. Each exposes `async get_status()`, `async refresh()`,
  and `async predict_game(game_data, game_context)` returning `{winner, confidence, reasoning}`.
  Follow that shape when adding one, and register it in `main.py`'s module-level agent block.
- `game_data` is duck-typed — agents read `.home_team_name`, `.away_team_name`, `.game_id`,
  `.venue`, `.is_dome`. `backtest.py::GameStub` relies on this; don't tighten it to the pydantic
  model without updating the stub.
- Every external call has a simulation fallback, and the returned dict carries a `source` field
  recording which path was taken. Preserve that when adding data sources — the backtest and the
  reasoning strings both key off it.

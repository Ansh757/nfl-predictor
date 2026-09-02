# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Architecture

Two services with a clear split of responsibility:

| Path | Role |
|------|------|
| `agent-service/` | FastAPI. Runs the five agents, owns the SQLite schedule/results database, serves the built React app. |
| `backend/` | Spring Boot gateway. Orchestrates the agents, **owns the weighted vote**, persists predictions to Postgres, caches in Redis. |
| `demo/` | React 19 + Tailwind dashboard. Built into the Python image at Docker stage 1. |
| `mobile-app/` | Empty placeholder for the planned React Native app. |
| `database/init.sql` | PostgreSQL seed — 32 teams with fixed IDs. |

The Python service runs the agents; the Java gateway decides what their output means. That
split is deliberate: agent weights live in Postgres and can be recalibrated without a redeploy,
and every prediction is recorded so accuracy can be measured continuously.

**Deployment note:** the Railway deploy still runs only the Python service (root `Dockerfile`
builds React into it, `railway.json` runs `python main.py`), and the dashboard calls FastAPI
directly. The gateway is wired into `docker-compose.yml` and works locally, but is not yet in
the hosted deploy.

`App.js::resolveApiUrl` no longer hardcodes the Railway host as the primary: it uses
`REACT_APP_API_URL` if set, otherwise **the origin the page was served from** (the service
serves its own bundle, so a custom domain or preview deploy needs no rebuild), and falls back
to the Railway URL only on `localhost`, where `npm start` has no API behind it.

## Commands

```bash
# Full stack: postgres + redis + agent service + gateway
docker-compose up -d

# Agent service alone (serves API + frontend if demo/build exists)
cd agent-service && python main.py            # → :8001

# Gateway alone (needs postgres + redis)
cd backend && ./mvnw spring-boot:run          # → :8080

# Tests
cd agent-service && python -m pytest tests/ -q      # consensus tests, mirrors the Java suite
cd backend && ./mvnw compile

# Backtest
cd agent-service && python backtest.py --season 2025 --runs 10
cd agent-service && python backtest.py --season 2025 --runs 10 --method majority

# Load schedule data
cd agent-service && python utils/schedule_loader.py --seasons 2021-2026

# Refresh results / run settlement without waiting for the weekly cron
curl -X POST "http://localhost:8001/games/refresh?season=2026"
curl -X POST "http://localhost:8080/api/gateway/settle/run?season=2026\&refresh=false" 
```

Java 17 is the target. `mvn` is not installed — use `./mvnw`, and set
`JAVA_HOME=$(/usr/libexec/java_home -v 17)` if the default JDK is older.

## The agents

All in `agent-service/agents/`, each exposing `async get_status()`, `async refresh()`, and
`async predict_game(game_data, game_context)` returning `{winner, confidence, reasoning}`.

| Agent | Accuracy (2021-24) | Weight | Notes |
|---|---|---|---|
| `odds_agent.py` | **66.4%** | 0.164 | Strongest agent. Live: The Odds API (needs `ODDS_API_KEY`). Backtest: nflverse closing lines |
| `elo_agent.py` | 61.5% | 0.115 | Ratings from `utils/elo.py`, no network calls |
| `basic_predictor.py` | 61.0% | 0.110 | Form from `utils/team_stats.py` (local game log); ESPN only as fallback |
| `rest_travel_agent.py` | 52.2% | 0.022 | Schedule situation via `utils/venues.py` |
| `injury_agent.py` | not backtestable | 0.02 | ESPN league-wide injury endpoint |

**Retired, do not re-add without evidence.** Weather Impact (51.1%) and News Sentiment
(49.7%) were removed: dropping both *improved* the ensemble by 0.07 points and cut ~4s of
cold latency. They chase information the closing line already prices, so an agent
re-deriving them is redundant next to Market Odds. Weather survives as
`utils/weather.py::WeatherProvider` - display-only context, no vote, now cached and using
the complete 32-venue table.

Elo's 61.5% understates it — 2021 is a cold start since the game log begins there. From 2022 on
it averages 63.8%.

**Market Odds is backtested via nflverse, not The Odds API.** The Odds API's historical
endpoint is paid-only (401 on the free tier). `utils/historical_odds.py` pulls free closing
moneylines from nflverse instead — full coverage, all 272 games per season — and the backtest
drives the *real* `MarketOddsAgent` through `HistoricalOddsClient`, so it exercises the agent's
actual de-vigging logic rather than a reimplementation. Closing lines are fixed before kickoff,
so this is not lookahead. The CSV is cached at `agent-service/historical_odds.csv` (gitignored,
auto-downloaded).

**Injury Impact has still never been measured.** ESPN publishes no historical injury archive, so
it sits at `DEFAULT_WEIGHT` (0.02). Do not raise it on intuition — the gateway records live
predictions precisely so it can be calibrated from data.

## Consensus — read before touching

`agents/consensus.py` is the single source of truth for voting in Python; `ConsensusService.java`
mirrors it for live traffic. `main.py` and `backtest.py` both call `build_consensus`, so measured
accuracy reflects the code that serves predictions. **Do not inline voting logic into either
caller.**

Weighted method (default): each agent contributes `weight × (confidence − 0.5)` to its pick.
Consequences worth knowing:

- An agent with no data should return confidence **exactly 0.50**, not a guess. That contributes
  zero without injecting noise. `odds_agent` and `injury_agent` both do this.
- Weights are the measured edge over a coin flip, floored at zero. An agent that cannot beat 50%
  literally cannot swing a prediction.
- Re-derive weights from `backtest.py` output; the Java copy reads them from the `agent_weights`
  table, seeded by `config/AgentWeightSeeder.java`.

**Historical bug, fixed:** the original counter only handled N-0 and (N-1)-1 splits and fell
through to "most confident agent wins" for everything else. Invisible with exactly four agents
(4-0, 3-1, 2-2 are the only splits), but it discarded the majority on a 3-2 split the moment a
fifth agent appeared. Any change here needs testing at N ≥ 5.

## Measured accuracy

Walk-forward backtest, weights fitted on 2021-2024 (2025 is out-of-sample):

| Season | Equal-weight (old) | Weighted (current) | Best single agent |
|--------|--------------------|--------------------|-------------------|
| 2021 | 57.2% | 59.9% | 60.7% |
| 2022 | 59.6% | 62.4% | 65.7% |
| 2023 | 60.0% | 64.0% | 67.6% |
| 2024 | 61.7% | 68.8% | 71.7% |
| 2025 | 62.3% | **66.9%** | 66.2% |
| Mean | 60.2% | **64.4%** | 66.2% |

Weighted voting is worth +4.2 points over equal-weight. Note that 2021-2024 are **in-sample**
(the weights were fitted on them) and Market Odds alone beats the ensemble on three of those.
**2025 is the only unbiased estimate**, and there the ensemble beats every component — Basic
66.2%, Market Odds 65.4%, Elo 64.3%. Quote 66.9%, not the mean. Predictions are deterministic:
every agent carrying weight is deterministic, so backtests reproduce exactly.

**Numbers revised down ~1 point in Aug 2026.** The Basic Predictor's point-in-time stats were
injected into a *team*-keyed cache while 12 games ran concurrently, letting a game read stats
written by a later one - limited lookahead. Overrides are now keyed by `game_id` and results are
identical at concurrency 1, 4 and 12. Anything that reports a jump back to ~68% mean should be
suspected of reintroducing that race.

## The market question — settled

`analyze_market_edge.py` answers whether the ensemble knows anything the closing
line does not. It does not.

Over 1,337 games (2021-2025) with a market: ensemble 64.6%, market-favourite
66.6%. They agree on 83%. On the 227 disagreements the ensemble is right 44.1%
and the market 55.9% - so overriding the line makes predictions worse, not
better. Against the spread the ensemble's preferred side returns 48.7%, under
the 52.38% break-even; higher-conviction buckets look profitable but are all
|z| < 2 on 38-126 bets.

Do not read a single season here. On 2025 alone the ensemble looked right on
55.1% of disagreements; four more seasons flipped that to 44.1%. One season is
~50 disagreement games.

Practical consequence: raising a non-market agent's weight to "beat" the market
is not supported by any measurement in this repo. If accuracy is the goal, the
honest move is weighting Market Odds higher, not adding agents.

## Backtest discipline

`backtest.py` enforces point-in-time correctness. Preserve these properties in any change:

- Team stats come from a rolling 17-game window of games that kicked off **before** the game
  being predicted, via `utils/team_stats.py`. The live agent calls the *same* helper with a
  cutoff of now, so backtest and production compute form identically - they previously did not,
  and the backtest was measuring code that never ran in production.
- The live ESPN endpoint is never called in backtest — it returns current standings and would
  leak the season under test.
- Elo records pre-kickoff ratings during `build()`, so building through the tested season is
  still point-in-time.
- Weather uses seasonal simulation keyed to the game's real month, never today's conditions.
- News runs in simulated-scenario mode (RSS carries today's headlines).
- Injuries run as `InertAgent` — using today's report for a 2025 game is an anachronism. It
  reports ~53.7% purely because it always names the home team; the report flags it `[inert]`.
- Odds use `HistoricalOddsClient` wrapping the real agent, not a stub.

## Data layer

- **`agent-service/nfl_schedule.db`** (SQLite, committed) — the `games` table: schedule, venue,
  final scores, playoff seeds/rounds. 2021-2025. `espn_game_id` has a UNIQUE index and
  `_store_games()` upserts on it. This is what the agents and backtest read.
- **PostgreSQL** — `teams` (from `init.sql`), plus `agent_weights` and `predictions` created by
  JPA. Only the gateway touches it.
- **Redis** — `gamePredictions` (30 min TTL) and `agentWeights` (24 h). Falls back to an
  in-memory cache when `spring.cache.type=simple`, which is the local default.

`NFLScheduleLoader.__init__` runs DDL and a dedupe DELETE on every instantiation, so importing
`main.py` mutates the SQLite file. Expect it to show as modified in `git status`.

## Season operations

- **Schedule**: 2021-2026 loaded. `schedule_loader.py --seasons <year>` for a new one.
- **Settlement**: `SettlementService` runs Tuesdays 09:00 (`prediction.settlement.cron`),
  re-pulls results from ESPN and scores stored predictions. Without it, Injury Impact can never
  be calibrated - it has no historical archive, so settled live predictions are its only path
  to a measured weight.
- **The schedule that actually fires lives in GitHub Actions**, not in the JVM.
  `record-predictions.yml` (Wed + Thu) and `settle-predictions.yml` (Tue) drive the gateway's
  existing endpoints; the in-app `@Scheduled` job is only a backstop, because Railway stops the
  container when idle and a cron in a stopped JVM never runs. Needs the repo variable
  `GATEWAY_URL`. Neither workflow hardcodes a week or season - the week comes from
  `/games/upcoming`, the season from the date.
- **A season is not a calendar year.** `SettlementService.seasonOf` puts January and February in
  the *previous* season, because season 2026 runs into February 2027. The original code took
  `LocalDate.now().getYear()`, so every January settlement searched a season that had not
  started and scored nothing - through the playoffs. The frontend derives its season the same
  way; keep the two in step.
- **Official predictions are unique per game.** `predictions.game_id` has a unique index and
  `persistOfficial` refuses to write at or after kickoff, or when kickoff is unknown. So the
  weekly endpoint is safe to re-run, which is why the workflow runs twice a week rather than
  hoping a single cron fires. `/api/gateway/accuracy`'s `total_predictions` is the cheapest way
  to check idempotency from outside.
- **Odds quota**: 500/month free. `OddsClient` caches the whole payload with a kickoff-aware
  TTL - 12 h idle, 10 min within 30 min of a kickoff (`ODDS_IDLE_TTL_HOURS`,
  `ODDS_KICKOFF_TTL_MINUTES`, `ODDS_KICKOFF_WINDOW_MINUTES`). ~125 requests/month. Never make
  this per-game; one request returns every upcoming game.
- **Frontend season bounds** are derived, not hardcoded: before March the selectable season is
  the previous calendar year, since NFL seasons run into January. No annual edit needed.
- **`REACT_APP_API_URL`** repoints the dashboard at the gateway or a local service; unset falls
  back to the production Python service.

## Frontend presentation

Decisions here came out of a launch review; do not undo them without a reason.

- **Kickoffs always carry a zone.** `utils/time.js` is the only formatter — local time with
  the zone abbreviation, plus the ET rendering next to it for anyone not already on Eastern.
  A bare "5:20 PM" made the site look factually wrong to a reader in another zone.
- **Accuracy is labelled as historical everywhere it appears.** 66.9% is the held-out 2025
  backtest, not a forward promise, and the landing page says so next to the number. Any new
  surface quoting an accuracy figure needs the same framing.
- **The disclaimer is sitewide.** `components/Disclaimer.jsx` renders in the footer on every
  view and inline next to each prediction. Keep both — the footer is coverage, the inline
  copy is where someone might actually act.
- **Cold starts are announced, not hidden.** The health probe retries with backoff
  (`HEALTH_PROBE_*`), a failed schedule load retries through a boot (`GAMES_RETRY_BACKOFF_MS`,
  4xx excluded — an answer is not a cold start), and `WakeBanner` explains the wait. A 5xx
  therefore takes ~11s to surface as an error; the test for it drives fake timers.
- **`.github/workflows/keep-warm.yml`** pings `/health` every 10 minutes. Only inbound traffic
  keeps the container awake, so this cannot live inside the service.
- **The Beta badge is in `TopBar`.** Remove it when the model has a measured live season, not
  before.
- **Theming is one attribute, not two sets of classes.** `src/index.css` defines the palette as
  RGB channel triplets on `:root` and `:root[data-theme='light']`; `tailwind.config.js` consumes
  them as `rgb(var(--token) / <alpha-value>)`, which is what keeps `bg-accent/15` working. So a
  component never mentions a theme — it writes `bg-ink-800` and gets the right colour. Two
  consequences: **extending a stock scale replaces it**, so every shade used must be declared in
  the config or the class silently stops generating; and **inline SVG must use `fill-*`/`stroke-*`
  classes**, never hex attributes, or it will not follow the theme.
  `theme.test.js` parses the CSS and pins every text token to WCAG AA on both surfaces —
  stock `slate-500`/`600` were 3.7:1 and 2.3:1 on a card and had to be lifted.
- **`easternHint` compares rendered clock time, not zone names.** `America/Toronto` is not
  `America/New_York` but shows the same clock, and name matching gave a Toronto reader
  "8:20 PM EDT · 8:20 PM ET" — the exact reader the feature was for.
- **Interaction is covered by `Interactions.test.js`.** It clicks every control and asserts each
  button has an accessible name and an `onClick`. It exists because a theme toggle that flipped
  an unread state variable and two handler-less Settings buttons all shipped unnoticed: the
  suite tested rendering and data, never interaction.

**Two dead components remain**: `DashboardSections.jsx` and `PlayoffsBracket.jsx` are imported by
nothing. They are still scanned by Tailwind's `content` glob, so classes only they use are
generated into the shipped stylesheet.

## Gotchas

- **Path traversal in the SPA catch-all.** `main.py` `/{full_path:path}` joins unsanitized user
  input onto `demo_build` and returns it as a `FileResponse`. Encoded `../` can escape the build
  directory. **Still unfixed.**
- **The postseason final was stored twice.** ESPN seasontype=3 week 4 *is* the Super Bowl, but
  the loader labelled it "Championship", which collided with the rows `add_superbowl_games.py`
  inserts as "Super Bowl". Every season held its final under both names, and since
  `utils/elo.py` reads every game with a score, Elo counted that game twice. Fixed in the round
  map and deduped; do not relabel week 4.
- **No playoff game has a seed recorded** - `home_seed`/`away_seed` are null for all 78 rows.
  The playoff simulator relied on a seed gap, so it could only ever return 0.5. It also never
  advanced winners between rounds. Removed rather than kept as decoration.
- **The 2025 Super Bowl is fictional** - `add_superbowl_games.py:53` says so explicitly. It
  feeds Elo like any other result, so ratings going into 2026 reflect a game that did not happen.
- **Playoff rounds reuse week numbers 1-4.** `/games/week/{week}` now filters on `season_type`
  (default `regular`) for exactly this reason — without it, week 1 returned the season opener
  *and* the Wild Card round, 22 games instead of 16. Keep that filter.
- **The playoff simulator doesn't propagate a bracket.** `/playoffs/{season}/simulate` flips a
  seed-gap-weighted coin on each round's *stored* matchups independently; winners never advance
  and the agents aren't involved. Only meaningful for seasons already played.
- **`weather_agent.predict_game` overwrites `home_team`** from
  `game_context['home_team_stats']['team']` and `KeyError`s if the context is incomplete. It also
  ignores `game_data.venue` in favor of the `TEAM_TO_VENUE` lookup. `utils/venues.py` is the
  complete table (domes included); the weather agent's own is missing dome coordinates.
- **Live accuracy is only meaningful for forward predictions.** Predicting a *past* season
  through the live agents scores badly regardless of model quality: ESPN returns current
  standings, weather is today's, and the odds feed has no market for a game already played. The
  backtest harness is the tool for historical evaluation; `/api/gateway/accuracy` is for games
  predicted before they were played.
- **Docker Hub withdrew the `openjdk` images.** `backend/Dockerfile` uses `eclipse-temurin`.

## Conventions

- **In Python, comment code out rather than deleting it.** Retired logic should stay
  visible in the file behind comments, not only in git history.

- Agents are plain classes, not a framework. Register new ones in `main.py`'s module-level agent
  block, in `_run_all_agents`, and add a weight entry in both `consensus.py` and
  `AgentWeightSeeder.java`.
- `agents/data_collector.py` is gone. Every agent fetches what it needs itself, so the
  `game_context` argument is vestigial - it stays in the signature as part of the agent contract
  but nothing reads it. Do not rebuild a shared context collector without a consumer.
- `game_data` is duck-typed — agents read `.home_team_name`, `.away_team_name`, `.game_id`,
  `.venue`, `.is_dome`, `.game_time`. `backtest.py::GameStub` relies on this.
- Point-in-time overrides go through a `game_id`-keyed dict on the agent (`pregame_ratings`,
  `pregame_rest`), never by mutating shared state — the backtest runs 12 games concurrently and
  mutation would race.
- Every external call has a fallback and returns a `source` field recording which path was taken.

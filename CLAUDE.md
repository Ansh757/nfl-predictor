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
| `elo_agent.py` | 61.6% | 0.116 | Ratings from `utils/elo.py`, no network calls |
| `basic_predictor.py` | 61.2% | 0.111 | Form from `utils/team_stats.py` (local game log); ESPN only as fallback |
| `rest_travel_agent.py` | 52.1% | 0.021 | Schedule situation via `utils/venues.py` |
| `injury_agent.py` | **55.5%** | 0.055 | ESPN live; nflverse weekly reports in backtest |

**Retired, do not re-add without evidence.** Weather Impact (51.1%) and News Sentiment
(49.7%) were removed: dropping both *improved* the ensemble by 0.07 points and cut ~4s of
cold latency. They chase information the closing line already prices, so an agent
re-deriving them is redundant next to Market Odds. Weather survives as
`utils/weather.py::WeatherProvider` - display-only context, no vote, now cached and using
the complete 32-venue table.

Elo's 61.6% understates it — 2021 is a cold start since the game log begins there. From 2022 on
it averages 63.8%.

**Market Odds is backtested via nflverse, not The Odds API.** The Odds API's historical
endpoint is paid-only (401 on the free tier). `utils/historical_odds.py` pulls free closing
moneylines from nflverse instead — full coverage, all 272 games per season — and the backtest
drives the *real* `MarketOddsAgent` through `HistoricalOddsClient`, so it exercises the agent's
actual de-vigging logic rather than a reimplementation. Closing lines are fixed before kickoff,
so this is not lookahead. The CSV is cached at `agent-service/historical_odds.csv` (gitignored,
auto-downloaded).

**Injury Impact is measured now — and the earlier claim here was wrong.** This section used to
say the agent "cannot be backtested" because ESPN publishes no historical archive. True about
ESPN, false as a conclusion: nflverse publishes the official weekly injury reports back to 2009,
the same source that calibrated Market Odds. `utils/historical_injuries.py` feeds them to the
real agent via `pregame_reports`.

Measured: **55.5%** over 2021-2024 (53.7 / 56.8 / 54.8 / 56.6), **z = 3.6** against a coin flip
on 1,088 games, and **57.4%** on the held-out 2025 season. Weight 0.02 → **0.055**.

**But read the ensemble numbers before concluding it matters.** Standalone it beats a coin flip
convincingly; as an ensemble member it changed the mean by 0.0 points (2022 −0.4, 2023 +0.3,
2024 +0.3, 2021 and 2025 unchanged). That is the recurring finding in this repo, not a
disappointment: the closing line already prices Friday's injury report, so an agent re-deriving
it adds little **alongside** Market Odds. It is kept because the signal is real and measured,
and because it is the one agent that can act when the odds feed is unavailable.

The lesson worth keeping: "the obvious source does not have it" is not the same as "the data
does not exist". That mistake cost this agent four seasons of being weighted by guess.

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
| 2021 | 57.2% | 59.2% | 60.7% |
| 2022 | 59.6% | 62.0% | 65.7% |
| 2023 | 60.0% | 64.3% | 67.6% |
| 2024 | 61.7% | 69.1% | 71.7% |
| 2025 | 62.3% | **66.9%** | 66.2% |
| Mean | 60.2% | **64.3%** | 66.2% |

Weighted voting is worth +4.1 points over equal-weight. Note that 2021-2024 are **in-sample**
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
- Injuries use `HistoricalInjuryLookup`, not the live feed — today's report for a 2025 game
  would be an anachronism. Reports are precomputed per game before the run starts (never a
  client mutated per prediction: twelve games run concurrently and are not in the same week),
  each game sees only its own week, and designations amended after kickoff are filtered out.
  Practice-participation rows are ignored - only the Out/Doubtful/Questionable game designation
  counts, which is what the live ESPN feed is equivalent to.
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

Decisions here came out of a design changeover; do not undo them without a reason.

**Three sections, and only three: Overview, Predictions, Playoffs.** There is no simulator, no
performance tab, no user picks and no scenario storage. The model's pick does not respond to a
reader, so a control implying it does would be a lie about what the application is.
`Interactions.test.js` asserts no pick/simulator control exists on any view.

- **Views are state, not routes.** `activeView` in `App.js`, mapped `overview | predictions |
  playoffs`. Adding a router would give shareable deep links but also a dependency and a new
  interaction with the SPA catch-all; it was not worth it for three sections. Worth revisiting if
  linking to a specific week is ever wanted.
- **Tokens are semantic, not a colour ramp.** `--surface`, `--border-subtle`, `--text-muted` in
  `index.css`, consumed through `tailwind.config.js`. The two themes are not inversions - dark is
  navy, light is warm paper - so names like "slate-700" stop meaning anything.
- **The accent carries a dark label, not white.** White on `#4d7cfe` is 3.73:1, under AA. The
  specified accent is kept and `--on-accent` is the page navy at 5.07:1. `theme.test.js` asserts
  the pair rather than a hardcoded white.
- **`.tnum` on every compared number.** Probabilities, records, seeds, scores. Proportional
  digits make a column of percentages ripple.
- **One week control per breakpoint.** `WeekNavigator` renders a list above `lg` and a native
  select below it; `PredictionFilters` deliberately has no Week field. Tailwind's `lg:hidden`
  only hides visually, so two week controls would both sit in the accessibility tree under one
  label - which is exactly what the test caught.
- **Status is never colour alone.** The connection dot has text beside it; a finished game says
  "Model correct" / "Model wrong" as words.
- **Display type appears on the Overview headline and nowhere else.** A serif in a data table is
  decoration.

**Playoffs standings are derived, and are not seeds.** There is no standings endpoint.
`utils/standings.js` counts records from `/games/results`, one request per season, cached by
season. Real NFL seeding puts division winners 1-4 regardless of record and resolves ties through
a procedure this data cannot reproduce, and `games.home_seed` is null on all 77 playoff rows - so
the column is "#", the caption says "ordered by win percentage", and nothing claims to be
projected, clinched or eliminated. `standings.test.js` asserts an unplayed game counts as nothing
for anybody, which is how a standings table starts inventing itself.

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
- **The 2025 Super Bowl is fictional, and now flagged as such.** `add_superbowl_games.py` marks
  it `fictional`, which becomes `games.is_synthetic = 1`. `utils/elo.py` and
  `utils/team_stats.py` both filter on `COALESCE(is_synthetic, 0) = 0` - both were learning
  from it, and the invention was Seattle over New England, who opened 2026 against each other.
  Excluding it moves exactly those two ratings by 5.4 Elo each and nothing else. **Any new query
  that learns from results needs the same filter.** The row is still displayed in the playoffs
  bracket; replacing it with the real result, or dropping it, is a separate decision.
- **Playoff rounds reuse week numbers 1-4.** `/games/week/{week}` now filters on `season_type`
  (default `regular`) for exactly this reason — without it, week 1 returned the season opener
  *and* the Wild Card round, 22 games instead of 16. Keep that filter.
- **The playoff simulator doesn't propagate a bracket.** `/playoffs/{season}/simulate` flips a
  seed-gap-weighted coin on each round's *stored* matchups independently; winners never advance
  and the agents aren't involved. Only meaningful for seasons already played.
**Numbers revised again in Sept 2026, for neutral sites.** Historical Elo credited the
designated home team with home-field advantage at *every* venue, including ~30 completed
games where nobody was at home - international fixtures and four of the five Super Bowls.
Correcting it moved only 2021 (59.9% -> 59.2%); every other season, including the held-out
2025, is unchanged. Weights were re-derived from the corrected runs.

## International and neutral-site games

**`neutralSite` and `internationalGame` are independent and must stay that way.**

- `neutral_site` - the designated home team is not at its own ground. Governs **home-field
  advantage only**. A Super Bowl is neutral and domestic. Super Bowl LVI was at SoFi with the
  Rams designated home, so it was **not** neutral and they kept the 65 points.
- `international_game` - the venue is outside the United States. Governs the **travel
  adjustment and the wording**. Never inferred from `neutral_site`, nor `neutral_site` from
  the country.

Collapsing them gives a domestic Super Bowl international wording, or gives a London game
home-field advantage. Both are pinned by test.

- **Source of truth**: ESPN supplies both (`competition.neutralSite`, `venue.address.country`)
  and the loader now stores them. `utils/venues.py::game_context` resolves local table → ESPN
  columns → domestic. Country strings are ESPN's: "England", not "United Kingdom" - see
  `DOMESTIC_COUNTRIES`.
- **Unknown venue means domestic and non-neutral.** The tempting inference - "not their listed
  stadium, so they must be away" - is backwards for the likeliest cause, a sponsor rename, and
  would strip home-field advantage from every home game that team plays.
- **Removing home-field advantage is context, not adjustment.** It moves the Elo agent's own
  output ~9 points but the ensemble only ~2.4, because Elo carries 0.116 against Market Odds'
  0.164.
- **The international travel effect is capped** at `INTL_MAX_AGENT_EDGE`, sized so the ensemble
  moves ≤1.5 points. The cap does the real work: the coefficients are not fitted, because
  there is nothing to fit them to. 24 completed international games 2021-2025 give a
  designated-home win rate of 58.3% against 53.9% domestic - z = 0.44. `INTL_FAMILIARITY_BONUS`
  is 0.0 and pinned there by test for the same reason.
- **No arrival or acclimation date is used anywhere.** Nothing upstream records when a team
  actually flew, and inferring one from kickoff would be inventing the signal.

- **Neutral-site games are resolved by venue, not by home team.** `utils/venues.py` has
  `NEUTRAL_VENUES` and `venue_location(home_team, venue)`; `travel_between` takes an optional
  `venue`. Without it the destination came from the home team, so San Francisco at the Melbourne
  Cricket Ground scored as a 313-mile trip to SoFi and the Rams were treated as not having
  travelled. The 2026 season has **nine** such games - Melbourne (wk1), Rio (3), London x3
  (4, 5, 6), Paris (7), Madrid (9), Munich (10), Mexico City (11). Counting only venues absent
  from 2025 gives five and misses London and Madrid, which recur every season; that mistake
  left four games mis-scored. `classify_venue` plus a test over every venue in the schedule is
  the guard - an unrecognised venue does not fail, it silently becomes a home game. `rest_travel_agent` now charges travel **net of what the home side also flew**,
  which is identical to the old behaviour for a normal home game (home travel is zero) and
  cancels correctly at a neutral site. A new international venue must be added to
  `NEUTRAL_VENUES` or it degrades silently to a home game.
- **Week 1 rest differentials are meaningless.** Rest is measured from a team's previous game in
  the database, so in week 1 that is their last game of the prior season - months earlier, and
  differing only by how deep into the playoffs they went. Pre-existing, capped by
  `MAX_REST_EDGE`, and worth about 0.002 of ensemble contribution at the agent's weight.
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

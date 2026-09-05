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
- **The design language is beige and green, with a serif for display type.**
  Light is the default; dark is a warm near-black on the same brown-grey axis, so the two read
  as one design rather than two. Three things carry it and none of them live in a component:
  the tokens in `index.css`, the `--font-serif` stack applied to `h1/h2/h3` by element, and the
  `borderRadius` scale in the Tailwind config. Restyling means editing those, not twelve files.
- **The serif is a system stack on purpose.** A webfont would mean widening the CSP to a font
  CDN and accepting a flash of unstyled text, for a face most readers cannot name.
- **The palette is Desert Sand / Ash Grey / Muted Teal / Jungle Teal / Turf Green.** Four are
  used literally, at the role each can actually hold: Turf Green `#04724D` as the light accent
  (5.97:1 under white button text, 5.19:1 as text), Desert Sand `#D2AB99` as the losing half of
  the win-probability bar, Muted Teal `#8DB38B` as the dark-theme positive, Ash Grey `#BDBEA9`
  as dim text on dark. Two needed adjusting and the reason is recorded so nobody "restores" them:
  Turf Green reads at only 2.7:1 on a dark card, so the dark accent is lifted to `#0F855C`; and
  Jungle Teal cannot carry white button text at 4.13:1, so it is deepened where used as a label.
- **All five source colours are mid-to-light.** None can be body text or a dark surface, so the
  ink and mist tokens are derived. A palette of five swatches does not furnish a UI on its own.
- **The accent is constrained from both directions** - it carries white button text *and* is
  used as text on a dark card - so it needs 4.5:1 against white and 3:1 against the card at
  once. Solve any new accent against `theme.test.js` before writing CSS.
- **`--opposing` exists because a green accent broke the win-probability bar.** The losing share
  used `slate-500`, which was obviously distinct from terracotta and reads as the same colour
  beside green. It is a pale taupe on the opposite side of the neutral axis, and it cannot just
  be `slate-500` lightened because that token doubles as tertiary text and has a contrast floor.
  Any future accent change needs this checked - the failure is invisible to the contrast tests,
  which only compare text against surfaces, never two fills against each other.
- **This is a personal project wearing a familiar look, not an Anthropic product.** No Anthropic
  marks, no claim of affiliation; the footer credits the repo.
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

## Security

- **The gateway's write and fan-out endpoints need `X-Gateway-Token`.** `GatewayAuthFilter`
  checks it against `GATEWAY_AUTH_TOKEN` in constant time and **fails closed** - unset means
  503, not "allow". Open: `/api/health`, `/api/gateway/accuracy`, `/api/gateway/weights`. The
  endpoint that made this urgent is `POST /predictions/{id}/settle`, which accepts an arbitrary
  `actualWinner`; since settlement only revisits unsettled rows, one forged call would corrupt
  live accuracy permanently.
- **`_resolve_within_build` must exist.** It is the SPA catch-all's path-traversal guard. It was
  written, then deleted by an unrelated refactor (`bb8f006`, retiring News Sentiment) while its
  call site stayed - so every unknown path raised NameError and returned 500 for weeks.
  `tests/test_security.py` pins both the guard and its existence.
- **Percent-decoding happens before the route.** Test encoded traversal over HTTP, not against
  `_resolve_within_build` directly - `%2e%2e` reaching the function as a literal is just an odd
  filename. And `....//` is not traversal here: nothing strips `../`, so `....` is an ordinary
  directory name that stays inside the root.
- **Never put `str(e)` in an HTTP response.** `_server_error` logs the cause and returns a
  generic message; the previous version echoed sqlite paths and SQL fragments to callers.
- **Rate limits are sized by unit of work, not request count.** Nothing asks for one
  prediction: a dashboard page view is `WEEK_FAN_OUT` (16) concurrent `/predict` calls, and the
  gateway fans out the same way over `/agents/predict-all` when recording a week. The first
  version allowed 30/minute, which permitted exactly one page view and rejected the next - an
  outage with a timer. Any new limit must be a multiple of `WEEK_FAN_OUT`, and
  `tests/test_security.py` pins that four consecutive week-loads are never throttled.
- **A 429 is a queueing problem, not an error.** The frontend backs off and retries
  (`PREDICTION_RETRY_ATTEMPTS`) rather than rendering "Prediction unavailable" for something
  that clears on its own.
- **Limits are per-process and keyed on `X-Forwarded-For`.** Spoofable by design - they exist to
  stop accidental hammering and casual abuse of `/predict` and `/games/refresh`, not a
  determined attacker.
- **Actuator is deliberately configured down** to `health` with `show-details: never`, even
  though the dependency is absent. Adding `spring-boot-starter-actuator` under the old config
  would have published metrics, routes and DB versions publicly in one line.
- **Both containers run as non-root.** Keep the `USER appuser` lines.

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

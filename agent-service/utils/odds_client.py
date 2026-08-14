"""
odds_client.py - Real betting lines from The Odds API.

Closing lines are among the strongest publicly available predictors of NFL
winners, which is what makes this worth wiring up properly instead of the
synthetic numbers MarketIntelligenceAgent generates.

Quota discipline: the free tier allows 500 requests/month, and one request
returns every upcoming NFL game - so the whole payload is fetched once and
cached rather than queried per game.

The cache TTL is kickoff-aware. Lines barely move days out, so outside game
time the payload is held for IDLE_CACHE_TTL. Within KICKOFF_WINDOW of any
kickoff it refreshes on KICKOFF_CACHE_TTL instead, which is both cheaper and
*more accurate*: the 66.4% backtest figure was measured on closing lines, so
pricing captured near kickoff is what the agent's weight was calibrated against.

Rough monthly cost with the defaults: ~2 requests/day idle (~60/month) plus
~3 per game slate inside the window (~65/month) - about 125 of the 500.

Set ODDS_API_KEY in .env. Without it every call returns None and the agent
falls back to a neutral, zero-weight prediction.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

ODDS_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
REQUEST_TIMEOUT = 15

# Kickoff-aware caching. All three are overridable so the cadence can be tuned
# against the quota without a code change.
IDLE_CACHE_TTL = timedelta(hours=float(os.getenv("ODDS_IDLE_TTL_HOURS", "12")))
KICKOFF_CACHE_TTL = timedelta(minutes=float(os.getenv("ODDS_KICKOFF_TTL_MINUTES", "10")))
KICKOFF_WINDOW = timedelta(minutes=float(os.getenv("ODDS_KICKOFF_WINDOW_MINUTES", "30")))


def american_to_probability(odds: float) -> float:
    """Convert American moneyline odds to an implied probability (with vig)."""
    if odds < 0:
        return -odds / (-odds + 100.0)
    return 100.0 / (odds + 100.0)


def remove_vig(home_prob: float, away_prob: float) -> float:
    """
    Normalise a two-way market so the probabilities sum to 1.

    Books price in an overround (the two implied probabilities sum to >1);
    dividing through by the total recovers a fair probability.
    """
    total = home_prob + away_prob
    if total <= 0:
        return 0.5
    return home_prob / total


class OddsClient:
    """Fetches and caches NFL moneyline and spread data."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        self.logger = logging.getLogger("api.odds")
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cached_at: Optional[datetime] = None
        self._lock = asyncio.Lock()
        self.quota_remaining: Optional[str] = None
        self.request_count = 0

        if not self.api_key:
            self.logger.info("ODDS_API_KEY not set; odds agent will stay inert")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _kickoff_imminent(self) -> bool:
        """True if any cached game starts within KICKOFF_WINDOW."""
        if not self._cache:
            return False

        now = datetime.now(timezone.utc)
        for event in self._cache:
            starts = event.get("commence_time")
            if not starts:
                continue
            try:
                kickoff = datetime.fromisoformat(str(starts).replace("Z", "+00:00"))
            except ValueError:
                continue
            if now <= kickoff <= now + KICKOFF_WINDOW:
                return True
        return False

    def current_ttl(self) -> timedelta:
        return KICKOFF_CACHE_TTL if self._kickoff_imminent() else IDLE_CACHE_TTL

    def _cache_valid(self) -> bool:
        if self._cache is None or self._cached_at is None:
            return False
        return datetime.now() - self._cached_at < self.current_ttl()

    async def get_all_odds(self) -> Optional[List[Dict[str, Any]]]:
        """Every upcoming NFL game with consensus pricing, or None if disabled."""
        if not self.enabled:
            return None
        if self._cache_valid():
            return self._cache

        async with self._lock:
            if self._cache_valid():
                return self._cache

            try:
                import aiohttp
            except ImportError:
                self.logger.warning("aiohttp unavailable; odds disabled")
                return None

            params = {
                "apiKey": self.api_key,
                "regions": "us",
                "markets": "h2h,spreads",
                "oddsFormat": "american",
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(ODDS_URL, params=params,
                                           timeout=REQUEST_TIMEOUT) as response:
                        # The API reports quota in response headers
                        self.quota_remaining = response.headers.get("x-requests-remaining")

                        if response.status == 401:
                            self.logger.error("Odds API rejected the key (401)")
                            return None
                        if response.status == 429:
                            self.logger.warning("Odds API quota exhausted (429)")
                            return self._cache
                        if response.status != 200:
                            self.logger.warning(f"Odds API returned {response.status}")
                            return self._cache

                        payload = await response.json()

                self._cache = [self._parse_event(event) for event in payload]
                self._cache = [event for event in self._cache if event]
                self._cached_at = datetime.now()
                self.request_count += 1
                self.logger.info(
                    f"Loaded odds for {len(self._cache)} games "
                    f"(quota remaining: {self.quota_remaining}, "
                    f"next refresh in {self.current_ttl()})"
                )
                return self._cache

            except Exception as exc:
                self.logger.error(f"Error fetching odds: {exc}")
                return self._cache

    def _parse_event(self, event: Dict) -> Optional[Dict[str, Any]]:
        """Average the moneyline and spread across books, then strip the vig."""
        home_team = event.get("home_team")
        away_team = event.get("away_team")
        if not home_team or not away_team:
            return None

        home_probs, away_probs, spreads = [], [], []

        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                outcomes = market.get("outcomes", [])

                if market.get("key") == "h2h":
                    prices = {o.get("name"): o.get("price") for o in outcomes}
                    home_price, away_price = prices.get(home_team), prices.get(away_team)
                    if home_price is not None and away_price is not None:
                        home_probs.append(american_to_probability(home_price))
                        away_probs.append(american_to_probability(away_price))

                elif market.get("key") == "spreads":
                    for outcome in outcomes:
                        if outcome.get("name") == home_team and outcome.get("point") is not None:
                            spreads.append(float(outcome["point"]))

        if not home_probs:
            return None

        mean_home = sum(home_probs) / len(home_probs)
        mean_away = sum(away_probs) / len(away_probs)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "commence_time": event.get("commence_time"),
            "home_win_probability": round(remove_vig(mean_home, mean_away), 4),
            "home_spread": round(sum(spreads) / len(spreads), 1) if spreads else None,
            "book_count": len(home_probs),
            "overround": round(mean_home + mean_away, 4),
        }

    async def get_game_odds(self, home_team: str, away_team: str) -> Optional[Dict[str, Any]]:
        """Find pricing for one matchup, or None if the game is not listed."""
        events = await self.get_all_odds()
        if not events:
            return None
        for event in events:
            if event["home_team"] == home_team and event["away_team"] == away_team:
                return event
        return None

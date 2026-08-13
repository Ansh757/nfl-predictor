"""
injury_client.py - Real NFL injury reports from ESPN.

One request returns the current report for all 32 teams, so the whole payload
is fetched once and cached rather than queried per team.

Note this is a *current* snapshot. ESPN publishes no historical injury archive,
so an injury-based agent cannot be validated in backtest the way Elo or the
Basic Predictor can.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

INJURIES_URL = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
CACHE_TTL = timedelta(hours=1)
REQUEST_TIMEOUT = 15

# ESPN reports plenty of players as "Active" - those carry no impact
SEVERITY = {
    "out": 1.0,
    "injured reserve": 1.0,
    "suspension": 1.0,
    "doubtful": 0.75,
    "questionable": 0.35,
    "probable": 0.10,
    "active": 0.0,
}


class InjuryClient:
    """Fetches and caches the league-wide ESPN injury report."""

    def __init__(self):
        self.logger = logging.getLogger("api.injuries")
        self._cache: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._cached_at: Optional[datetime] = None
        self._lock = asyncio.Lock()

    def _cache_valid(self) -> bool:
        return (
            self._cache is not None
            and self._cached_at is not None
            and datetime.now() - self._cached_at < CACHE_TTL
        )

    async def get_all_injuries(self) -> Dict[str, List[Dict[str, Any]]]:
        """Team display name -> list of meaningful injuries. Empty dict on failure."""
        if self._cache_valid():
            return self._cache

        async with self._lock:
            # Another coroutine may have refreshed while we waited
            if self._cache_valid():
                return self._cache

            try:
                import aiohttp
            except ImportError:
                self.logger.warning("aiohttp unavailable; injury data disabled")
                return {}

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(INJURIES_URL, timeout=REQUEST_TIMEOUT) as response:
                        if response.status != 200:
                            self.logger.warning(f"ESPN injuries returned {response.status}")
                            return self._cache or {}
                        payload = await response.json()

                self._cache = self._parse(payload)
                self._cached_at = datetime.now()
                total = sum(len(items) for items in self._cache.values())
                self.logger.info(f"Loaded {total} active injuries across {len(self._cache)} teams")
                return self._cache

            except Exception as exc:
                self.logger.error(f"Error fetching ESPN injuries: {exc}")
                return self._cache or {}

    def _parse(self, payload: Dict) -> Dict[str, List[Dict[str, Any]]]:
        report: Dict[str, List[Dict[str, Any]]] = {}

        for team_block in payload.get("injuries", []):
            team_name = team_block.get("displayName")
            if not team_name:
                continue

            entries = []
            for item in team_block.get("injuries", []):
                status = (item.get("status") or "").strip()
                severity = SEVERITY.get(status.lower(), 0.0)
                if severity <= 0:
                    continue  # Active / unknown - no meaningful impact

                athlete = item.get("athlete") or {}
                position = (athlete.get("position") or {}).get("abbreviation", "")

                entries.append({
                    "player": athlete.get("displayName", "Unknown"),
                    "position": position,
                    "status": status,
                    "severity": severity,
                    "detail": (item.get("shortComment") or "")[:160],
                })

            report[team_name] = entries

        return report

    async def get_team_injuries(self, team_name: str) -> List[Dict[str, Any]]:
        report = await self.get_all_injuries()
        return report.get(team_name, [])

    async def test_connection(self) -> bool:
        return bool(await self.get_all_injuries())

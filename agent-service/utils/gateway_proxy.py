"""
Read-only pass-through to the Java gateway's public endpoints.

The dashboard is served by this service and calls it on its own origin, but the
live record - official pre-kickoff picks and how they settled - lives in the
gateway's Postgres. Without this the dashboard's live-accuracy tile only ever
worked when REACT_APP_API_URL pointed the whole app at the gateway, so in
production it was permanently a dash.

Only the two public, read-only routes are forwarded, never anything that
writes or fans out to the agents, so no gateway token is held here. Responses
are cached briefly: the data changes once a day at most, and the gateway may be
asleep - a cold start should be paid once, not once per page view.
"""
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

CACHE_SECONDS = int(os.getenv("GATEWAY_CACHE_SECONDS", "120"))
# The gateway sleeps when idle; a cold start can take most of a minute.
TIMEOUT_SECONDS = float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "45"))

_cache: Dict[str, Tuple[float, Any]] = {}


class GatewayUnavailable(Exception):
    """The gateway is not configured, or did not answer usefully."""


def gateway_url() -> Optional[str]:
    url = os.getenv("GATEWAY_URL", "").strip()
    return url.rstrip("/") or None


async def fetch(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """GET a gateway path, cached on the full URL. Raises GatewayUnavailable."""
    base = gateway_url()
    if base is None:
        raise GatewayUnavailable("GATEWAY_URL is not set")

    clean = {k: v for k, v in (params or {}).items() if v is not None}
    key = path + "?" + "&".join(f"{k}={clean[k]}" for k in sorted(clean))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(base + path, params=clean)
    except httpx.HTTPError as exc:
        logger.warning("Gateway request %s failed: %s", path, exc)
        raise GatewayUnavailable(str(exc)) from exc

    if response.status_code != 200:
        logger.warning("Gateway %s returned %s", path, response.status_code)
        raise GatewayUnavailable(f"status {response.status_code}")

    body = response.json()
    _cache[key] = (time.monotonic(), body)
    return body


def clear_cache():
    _cache.clear()

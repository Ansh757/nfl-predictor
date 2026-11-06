"""
service.py - Rotobot's play-by-play simulation, as the API serves it.

A game takes about 8 seconds (calibration plus 10,000 runs), which is fine once
and wrong per page view. So results are computed in the background and cached:

  * The cache key is a fingerprint of every input - the line, each side's
    projected players and their roles, who is out, the model version. If the
    line moves or a starter is ruled out, the fingerprint changes and the next
    request queues a fresh run; nothing has to remember to invalidate it.
  * A precompute endpoint queues a whole week (driven daily by a GitHub
    Actions workflow), so most page views find a result waiting.
  * A request that finds nothing cached gets status "pending" and queues the
    game; the page still has the exact score model and part 2's projections to
    show meanwhile.

One worker thread, so a batch cannot starve the API of CPU. Results are kept in
memory and on disk; the disk copy survives a restart but not a redeploy, which
only means the first view after a deploy waits for the batch.
"""
import hashlib
import json
import logging
import os
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from rotobot.pbp.data import plays
from rotobot.pbp.engine import Side
from rotobot.pbp.simulate import RUNS, calibrate, roles_from_projection, simulate
from rotobot.pbp.teams import TeamHistory, build_side, league_rates
from rotobot.score import GameLine

logger = logging.getLogger("rotobot.pbp.service")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "league_model.json")
CACHE_DIR = os.getenv("ROTOBOT_CACHE_DIR", "rotobot_cache")
HISTORY_REFRESH_SECONDS = 12 * 3600
# A result for a game not yet played is recomputed at least this often even if
# no input changed, so team form keeps up with games played in between
MAX_AGE_SECONDS = 24 * 3600

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rotobot-sim")
_lock = threading.Lock()
_results: Dict[str, Dict[str, Any]] = {}          # fingerprint -> result
_pending: Dict[str, float] = {}                   # fingerprint -> queued at
_history: Dict[str, Any] = {"season": None, "built": 0.0, "history": None, "league": None}
_model: Optional[Dict] = None


def _league_model() -> Dict:
    global _model
    if _model is None:
        with open(MODEL_PATH) as handle:
            _model = json.load(handle)
    return _model


def model_version() -> str:
    with open(MODEL_PATH, "rb") as handle:
        return hashlib.sha1(handle.read()).hexdigest()[:10]


def _team_history(season: int):
    stale = time.time() - _history["built"] > HISTORY_REFRESH_SECONDS
    if _history["history"] is None or _history["season"] != season or stale:
        history = TeamHistory(plays([season - 1, season], current_season=season), _league_model()["pass_beta"])
        _history.update(season=season, built=time.time(), history=history, league=league_rates(history))
    return _history["history"], _history["league"]


def fingerprint(game: Dict, line: GameLine, players: Dict) -> str:
    """Everything that should trigger a re-run if it changes."""
    parts = {
        "game": game["game_id"], "spread": line.home_spread, "total": line.total,
        "model": model_version(), "runs": RUNS,
        "sides": {side: {
            "out": sorted(players[side].get("out", [])),
            "roles": sorted((p["player_id"], round(p["stats"]["targets"], 1), round(p["stats"]["carries"], 1))
                            for p in players[side].get("players", [])),
        } for side in ("home", "away") if players.get(side)},
    }
    return hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


def _disk_path(fp: str) -> str:
    return os.path.join(CACHE_DIR, f"{fp}.json")


def cached(fp: str, played: bool) -> Optional[Dict]:
    result = _results.get(fp)
    if result is None and os.path.exists(_disk_path(fp)):
        try:
            with open(_disk_path(fp)) as handle:
                result = json.load(handle)
            _results[fp] = result
        except (OSError, ValueError):
            return None
    if result and not played and time.time() - result.get("computed_at", 0) > MAX_AGE_SECONDS:
        return None
    return result


def _sides(game: Dict, players: Dict, season: int, week: int):
    from rotobot.live_players import ABBREVIATION
    history, league = _team_history(season)
    sides = []
    for side in ("home", "away"):
        code = ABBREVIATION.get(game[f"{side}_team"])
        s = build_side(history, league, code, season, week) if code else Side(code or side)
        block = players.get(side) or {}
        if block.get("players"):
            s.qb, s.roles, s.positions = roles_from_projection(block["players"], block.get("team_line") or {})
        sides.append(s)
    return sides


def run(game: Dict, line: GameLine, players: Dict, fp: str, season: int, week: int) -> Dict:
    """Calibrate and simulate one game. Blocking - call through queue()."""
    started = time.time()
    model = _league_model()
    home, away = _sides(game, players, season, week)
    seed = zlib.crc32(str(game["game_id"]).encode())
    calibrate(model, home, away, line.home_points, line.away_points, seed)
    result = simulate(model, home, away, seed, runs=RUNS, home_spread=line.home_spread, total=line.total)
    result.update(status="ready", fingerprint=fp, computed_at=time.time(),
                  seconds=round(time.time() - started, 1), model_version=model_version())
    with _lock:
        _results[fp] = result
        _pending.pop(fp, None)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_disk_path(fp) + ".part", "w") as handle:
            json.dump(result, handle)
        os.replace(_disk_path(fp) + ".part", _disk_path(fp))
    except OSError as exc:
        logger.warning("Could not write simulation cache: %s", exc)
    logger.info("Simulated game %s (%d runs) in %.1fs", game["game_id"], RUNS, result["seconds"])
    return result


def queue(game: Dict, line: GameLine, players: Dict, fp: str, season: int, week: int) -> bool:
    """Queue a run unless one is already queued or running. Returns True if newly queued."""
    with _lock:
        existing = _results.get(fp)
        fresh = existing is not None and time.time() - existing.get("computed_at", 0) <= MAX_AGE_SECONDS
        if fp in _pending or fresh:
            return False
        _pending[fp] = time.time()

    def job():
        try:
            run(game, line, players, fp, season, week)
        except Exception:
            logger.exception("Simulation failed for game %s", game["game_id"])
            with _lock:
                _pending.pop(fp, None)

    _executor.submit(job)
    return True


def status() -> Dict:
    with _lock:
        return {"queued_or_running": len(_pending), "cached": len(_results)}

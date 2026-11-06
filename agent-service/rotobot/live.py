"""
live.py - Find the line Rotobot anchors a game to, and say where it came from.

In order of preference, separately for the spread and the total:

  1. The live market (The Odds API, via the Market Odds agent's client) - for
     games that have not been played.
  2. The nflverse line - for games that have been played, where the live feed
     no longer lists a market, this is the closing line the backtest uses. For
     a game not yet played nflverse carries the current line, which can still
     move, so it is labelled "nflverse_line" rather than "closing_line".
  3. A fallback: the spread implied by the Elo agent's win probability, and the
     league-average total. Clearly labelled, because it is a much weaker anchor.

A spread can also come from the market's moneyline when books quote a price but
no spread, through the same win-probability conversion.
"""
import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

from rotobot.score import LEAGUE_AVERAGE_TOTAL, GameLine, spread_from_win_probability
from utils.historical_odds import HistoricalOddsLookup

logger = logging.getLogger("rotobot.live")

_historical: Optional[HistoricalOddsLookup] = None


def _historical_lookup() -> HistoricalOddsLookup:
    # Lazy: the CSV is downloaded on first use, not at import
    global _historical
    if _historical is None:
        _historical = HistoricalOddsLookup()
    return _historical


async def resolve_line(game: Dict[str, Any], odds_client, elo_agent) -> Tuple[GameLine, Dict[str, str]]:
    home, away = game["home_team"], game["away_team"]
    spread: Optional[float] = None
    total: Optional[float] = None
    source = {"spread": None, "total": None}

    market = None
    try:
        market = await odds_client.get_game_odds(home, away) if odds_client.enabled else None
    except Exception as exc:                      # the feed is optional; never fatal here
        logger.warning("Live odds unavailable for %s @ %s: %s", away, home, exc)

    if market:
        if market.get("home_spread") is not None:
            spread, source["spread"] = float(market["home_spread"]), "live_market"
        elif market.get("home_win_probability") is not None:
            spread = spread_from_win_probability(market["home_win_probability"])
            source["spread"] = "live_moneyline"
        if market.get("total") is not None:
            total, source["total"] = float(market["total"]), "live_market"

    if spread is None or total is None:
        closing = _historical_lookup().get(game["season"], home, away)
        played = game.get("home_score") is not None
        label = "closing_line" if played else "nflverse_line"
        if closing:
            if spread is None and closing.get("home_spread") is not None:
                spread, source["spread"] = float(closing["home_spread"]), label
            if total is None and closing.get("total") is not None:
                total, source["total"] = float(closing["total"]), label

    if spread is None:
        stub = SimpleNamespace(
            game_id=game["game_id"], home_team_name=home, away_team_name=away,
            venue=game.get("venue"), is_dome=bool(game.get("is_dome")),
            game_time=game.get("game_date"), neutral_site=game.get("neutral_site"),
            venue_country=game.get("venue_country"),
        )
        try:
            elo = await elo_agent.predict_game(stub, {})
            spread = spread_from_win_probability(elo["home_win_probability"])
            source["spread"] = "elo_fallback"
        except Exception as exc:
            logger.warning("Elo fallback failed for game %s: %s", game["game_id"], exc)
            spread, source["spread"] = 0.0, "pick_em_fallback"

    if total is None:
        total, source["total"] = LEAGUE_AVERAGE_TOTAL, "league_average"

    return GameLine(home_spread=spread, total=total), source

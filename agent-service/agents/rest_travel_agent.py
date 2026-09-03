"""
rest_travel_agent.py - Schedule-situation agent.

Looks at the things a team knows before the season even starts: who is on a
short week, who is coming off a bye, and how far the visitors had to fly.

This is a deliberately small signal - a couple of points of spread at most -
so the agent reports modest confidences and will earn a correspondingly small
weight in the ensemble. Everything it uses is known in advance, so there is no
leakage and it replays exactly in backtest.
"""
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from utils.venues import (
    game_context as resolve_game_context,
    is_neutral_site,
    travel_between,
    venue_for,
)

# Effect sizes in "win probability" terms, kept small on purpose.
BYE_WEEK_EDGE = 0.035          # 13+ days off
EXTRA_REST_PER_DAY = 0.006     # per day of rest advantage, capped below
MAX_REST_EDGE = 0.045
SHORT_WEEK_TRAVEL_PENALTY = 0.025   # <=4 days rest AND travelling
LONG_TRIP_PENALTY = 0.020      # 2000+ miles
MEDIUM_TRIP_PENALTY = 0.010    # 1000-2000 miles
EASTWARD_TZ_PENALTY = 0.008    # per timezone crossed heading east

BYE_THRESHOLD_DAYS = 13
SHORT_WEEK_DAYS = 4

# --- International games -----------------------------------------------------
#
# Budget, not a model. The whole international effect is capped so that after
# the weighted vote it can move the final probability by about 1.5 points at
# most. Everything below is sized against that ceiling rather than fitted,
# because there is nothing to fit it to: 24 completed international games in
# 2021-2025 give a designated-home win rate of 58.3% against 53.9% domestic,
# z = 0.44. The honest position is "no measurable effect", so the numbers here
# are deliberately small and the cap is what actually governs the outcome.
#
# The agent's own confidence is capped at INTL_MAX_AGENT_EDGE; with this
# agent's measured weight of 0.022 that works out to well under 1.5 points of
# final probability. The conversion is asserted in the tests rather than
# assumed here, so a future re-weighting cannot silently breach the budget.
INTL_MAX_AGENT_EDGE = 0.06          # ceiling on |edge| contributed by travel
INTL_TZ_EAST_PENALTY = 0.004        # per timezone crossed eastward, per team
INTL_TZ_WEST_PENALTY = 0.0016       # westward is milder - about 40%
INTL_LONG_HAUL_MILES = 3000         # beyond this, the flight itself counts
INTL_LONG_HAUL_PENALTY = 0.008
INTL_SHORT_WEEK_PENALTY = 0.010     # a long flight on four days' rest
INTL_PRIOR_TRAVEL_MILES = 1500      # heavy travel the previous week
INTL_PRIOR_TRAVEL_PENALTY = 0.004
# Venue familiarity from a prior appearance. Zero by default and pinned there by
# test: the sample cannot distinguish it from noise, and shipping a number that
# looks measured when it is not is how a model acquires false confidence.
INTL_FAMILIARITY_BONUS = 0.0


class RestTravelAgent:
    """Predicts from rest differential, travel burden and body-clock shift."""

    def __init__(self, name: str, db_path: str = "nfl_schedule.db"):
        self.name = name
        self.status = "active"
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        self.db_path = db_path

        # team -> sorted list of kickoff datetimes, used to derive rest days
        self.schedule: Dict[str, List[datetime]] = defaultdict(list)
        # team -> per-game rows, for the previous week's travel burden and prior
        # visits to a venue. Kept alongside `schedule` rather than replacing it
        # so the rest-day path is unchanged.
        self.game_log: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # Optional per-game override supplied by the backtest
        self.pregame_rest: Dict[int, Tuple[Optional[float], Optional[float]]] = {}

        self._load_schedule()

    # ----------------------------------------------------------------- setup

    def _load_schedule(self):
        """Load every scheduled kickoff so rest days can be derived."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT game_date, home_team, away_team, venue, neutral_site
                FROM games
                WHERE home_team IS NOT NULL AND away_team IS NOT NULL
                ORDER BY game_date
            ''')
            rows = cursor.fetchall()
            conn.close()

            for game_date, home, away, venue, neutral in rows:
                kickoff = self._parse_date(game_date)
                if kickoff is None:
                    continue
                self.schedule[home].append(kickoff)
                self.schedule[away].append(kickoff)
                entry = {
                    "kickoff": kickoff,
                    "home_team": home,
                    "away_team": away,
                    "venue": venue,
                    "neutral_site": bool(neutral),
                }
                self.game_log[home].append(entry)
                self.game_log[away].append(entry)

            for team in self.schedule:
                self.schedule[team].sort()
            for team in self.game_log:
                self.game_log[team].sort(key=lambda game: game["kickoff"])

            self.logger.info(f"Schedule loaded for {len(self.schedule)} teams")
        except Exception as exc:
            self.logger.warning(f"Could not load schedule for rest calculation: {exc}")

    @staticmethod
    def _parse_date(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    async def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "last_activity": self.last_activity,
            "message": f"Rest and travel data loaded for {len(self.schedule)} teams."
        }

    async def refresh(self):
        self.last_activity = datetime.now()
        self.schedule.clear()
        self._load_schedule()

    # ------------------------------------------------------------ rest logic

    def _rest_days(self, team: str, kickoff: Optional[datetime]) -> Optional[float]:
        """Days since this team's previous game, or None if unknown."""
        if kickoff is None:
            return None
        previous = [date for date in self.schedule.get(team, []) if date < kickoff]
        if not previous:
            return None
        return (kickoff - previous[-1]).total_seconds() / 86400.0

    def _rest_for(self, game_data, kickoff: Optional[datetime]) -> Tuple[Optional[float], Optional[float]]:
        game_id = getattr(game_data, "game_id", None)
        if game_id is not None and game_id in self.pregame_rest:
            return self.pregame_rest[game_id]
        return (
            self._rest_days(game_data.home_team_name, kickoff),
            self._rest_days(game_data.away_team_name, kickoff)
        )

    # -------------------------------------------------------------- predict

    async def predict_game(self, game_data, game_context: Dict[str, Any]) -> Dict[str, Any]:
        self.last_activity = datetime.now()
        self.status = "analyzing_schedule"

        try:
            home_team = game_data.home_team_name
            away_team = game_data.away_team_name

            kickoff = self._parse_date(getattr(game_data, "game_time", None))
            home_rest, away_rest = self._rest_for(game_data, kickoff)

            # Where the game is actually played, not where the home team lives.
            # At a neutral site the home team flies too, and for the five
            # international games on the 2026 schedule it flies about as far as
            # the visitors - so the travel burden nearly cancels instead of
            # counting against one side.
            venue = getattr(game_data, "venue", None)
            context = resolve_game_context(
                home_team, venue,
                getattr(game_data, "neutral_site", None),
                getattr(game_data, "venue_country", None),
            )
            neutral = context["neutral_site"]
            international = context["international_game"]
            travel = travel_between(away_team, home_team, venue)
            home_travel = (travel_between(home_team, home_team, venue) if neutral
                           else {"distance_miles": 0.0, "timezone_shift": 0.0})

            edge, factors = self._calculate_edge(
                home_team, away_team, home_rest, away_rest, travel, home_travel, neutral
            )

            # International travel is scored separately and clamped, so it can
            # colour a prediction but never drive it. Domestic games - including
            # domestic neutral sites - skip this entirely and keep their
            # existing behaviour byte for byte.
            intl_detail = None
            if international:
                intl_edge, intl_factors, intl_detail = self._international_edge(
                    home_team, away_team, home_rest, away_rest,
                    travel, home_travel, kickoff, context
                )
                edge += intl_edge
                factors = intl_factors + factors

            if edge > 0.005:
                winner = home_team
            elif edge < -0.005:
                winner = away_team
            else:
                # Genuinely neutral situation - defer to home field, the weakest
                # possible claim, and report it as such with minimum confidence
                winner = home_team
                factors.append("No meaningful rest or travel edge")

            confidence = min(0.70, 0.50 + abs(edge) * 2.0)

            self.status = "active"
            return {
                "winner": winner,
                "confidence": round(confidence, 3),
                "reasoning": self._generate_reasoning(factors, winner, confidence),
                "home_rest_days": round(home_rest, 1) if home_rest is not None else None,
                "away_rest_days": round(away_rest, 1) if away_rest is not None else None,
                "travel_miles": travel["distance_miles"],
                "timezone_shift": travel["timezone_shift"],
                "home_travel_miles": home_travel["distance_miles"],
                "neutral_site": neutral,
                "international_game": international,
                "venue_country": context["venue_country"],
                "venue_timezone": context["venue_timezone"],
                "international_detail": intl_detail,
                "situational_edge": round(edge, 4),
                "source": "schedule"
            }

        except Exception as exc:
            self.status = "error"
            self.logger.error(f"Error in rest/travel analysis: {exc}")
            raise

    def _calculate_edge(self, home_team: str, away_team: str,
                        home_rest: Optional[float], away_rest: Optional[float],
                        travel: Dict[str, float],
                        home_travel: Optional[Dict[str, float]] = None,
                        neutral: bool = False) -> Tuple[float, List[str]]:
        """
        Positive edge favours the home team.

        Travel is scored on the *difference* between what the two sides flew.
        For an ordinary home game the home team flies nothing, so this is
        identical to charging the visitors for the whole trip - the previous
        behaviour, unchanged. At a neutral site both sides fly and the burden
        largely cancels, which is the point: it is not an away game.
        """
        edge = 0.0
        factors: List[str] = []
        home_travel = home_travel or {"distance_miles": 0.0, "timezone_shift": 0.0}
        if neutral:
            factors.append("Neutral site - neither side is at home")

        # --- Rest differential
        if home_rest is not None and away_rest is not None:
            if home_rest >= BYE_THRESHOLD_DAYS and away_rest < BYE_THRESHOLD_DAYS:
                edge += BYE_WEEK_EDGE
                factors.append(f"{home_team} coming off a bye ({home_rest:.0f} days rest)")
            elif away_rest >= BYE_THRESHOLD_DAYS and home_rest < BYE_THRESHOLD_DAYS:
                edge -= BYE_WEEK_EDGE
                factors.append(f"{away_team} coming off a bye ({away_rest:.0f} days rest)")

            rest_gap = home_rest - away_rest
            if abs(rest_gap) >= 1:
                rest_edge = max(-MAX_REST_EDGE, min(MAX_REST_EDGE, rest_gap * EXTRA_REST_PER_DAY))
                edge += rest_edge
                rested = home_team if rest_gap > 0 else away_team
                factors.append(f"{rested} has {abs(rest_gap):.0f} more days of rest")

            # Short week is harder on the team that also has to travel
            if away_rest <= SHORT_WEEK_DAYS and travel["distance_miles"] > 500:
                edge += SHORT_WEEK_TRAVEL_PENALTY
                factors.append(f"{away_team} on a short week with travel")
            if home_rest <= SHORT_WEEK_DAYS and away_rest > SHORT_WEEK_DAYS:
                edge -= SHORT_WEEK_TRAVEL_PENALTY * 0.5
                factors.append(f"{home_team} on a short week")

        # --- Travel burden, net of what the home side also had to fly
        distance = travel["distance_miles"] - home_travel["distance_miles"]
        if distance >= 2000:
            edge += LONG_TRIP_PENALTY
            factors.append(f"{away_team} travelling {travel['distance_miles']:,.0f} miles")
        elif distance >= 1000:
            edge += MEDIUM_TRIP_PENALTY
            factors.append(f"{away_team} travelling {travel['distance_miles']:,.0f} miles")
        elif neutral and travel["distance_miles"] >= 1000:
            # Both flew a long way, so neither is disadvantaged - but a reader
            # deserves to know a trip happened rather than see nothing at all.
            factors.append(
                f"Both sides travelling ~{travel['distance_miles']:,.0f} miles"
            )

        # --- Body clock: flying east is the harder direction
        tz_shift = travel["timezone_shift"] - home_travel["timezone_shift"]
        if tz_shift > 0:
            edge += EASTWARD_TZ_PENALTY * tz_shift
            factors.append(
                f"{away_team} crossing {tz_shift:.0f} timezone(s) eastward"
            )
        elif tz_shift < 0:
            edge += EASTWARD_TZ_PENALTY * 0.4 * tz_shift  # westward, milder
            factors.append(f"{away_team} crossing {abs(tz_shift):.0f} timezone(s) westward")

        return edge, factors

    def _international_edge(self, home_team: str, away_team: str,
                            home_rest: Optional[float], away_rest: Optional[float],
                            travel: Dict[str, float], home_travel: Dict[str, float],
                            kickoff: Optional[datetime],
                            context: Dict[str, Any]) -> Tuple[float, List[str], Dict[str, Any]]:
        """
        The international travel effect, as a difference between the two sides.

        Only reached when the venue is outside the United States. Everything is
        symmetric - each team is charged for its own journey and the edge is
        what remains - so two teams flying comparable distances from comparable
        time zones cancel to roughly zero, which is the correct answer and the
        common case for two American teams meeting in London.

        Positive favours the home team. The result is clamped to
        INTL_MAX_AGENT_EDGE; see that constant for why the cap does the real
        work here rather than the coefficients.
        """
        factors: List[str] = []
        country = context.get("venue_country") or "overseas"

        away_tz = travel["timezone_shift"]
        home_tz = home_travel["timezone_shift"]

        def body_clock_cost(shift: float) -> float:
            # Eastward is the harder direction: the body clock lands behind
            # local time and has to be dragged forward.
            return (shift * INTL_TZ_EAST_PENALTY if shift > 0
                    else abs(shift) * INTL_TZ_WEST_PENALTY)

        # Positive edge favours home, so the *away* team's cost is added.
        edge = body_clock_cost(away_tz) - body_clock_cost(home_tz)

        for miles, label in ((travel["distance_miles"], away_team),
                             (home_travel["distance_miles"], home_team)):
            if miles >= INTL_LONG_HAUL_MILES:
                edge += INTL_LONG_HAUL_PENALTY * (1 if label == away_team else -1)

        # A long flight on a short week compounds; the two are not independent.
        if away_rest is not None and away_rest <= SHORT_WEEK_DAYS \
                and travel["distance_miles"] >= INTL_LONG_HAUL_MILES:
            edge += INTL_SHORT_WEEK_PENALTY
            factors.append(f"{away_team} on a short week before a long flight")
        if home_rest is not None and home_rest <= SHORT_WEEK_DAYS \
                and home_travel["distance_miles"] >= INTL_LONG_HAUL_MILES:
            edge -= INTL_SHORT_WEEK_PENALTY
            factors.append(f"{home_team} on a short week before a long flight")

        # Heavy travel the previous week, from the schedule we already hold. No
        # arrival or acclimation date is used anywhere: nothing in the upstream
        # data records when a team actually flew, and inventing one would be
        # inventing the signal.
        away_prior = self._previous_week_burden(away_team, kickoff)
        home_prior = self._previous_week_burden(home_team, kickoff)
        if away_prior >= INTL_PRIOR_TRAVEL_MILES:
            edge += INTL_PRIOR_TRAVEL_PENALTY
            factors.append(f"{away_team} also travelled heavily the previous week")
        if home_prior >= INTL_PRIOR_TRAVEL_MILES:
            edge -= INTL_PRIOR_TRAVEL_PENALTY
            factors.append(f"{home_team} also travelled heavily the previous week")

        # Venue familiarity. Zero by default - see INTL_FAMILIARITY_BONUS.
        away_visits = self._prior_international_visits(away_team, context.get("venue"), kickoff)
        home_visits = self._prior_international_visits(home_team, context.get("venue"), kickoff)
        if INTL_FAMILIARITY_BONUS:
            edge -= INTL_FAMILIARITY_BONUS * min(away_visits, 2)
            edge += INTL_FAMILIARITY_BONUS * min(home_visits, 2)

        clamped = max(-INTL_MAX_AGENT_EDGE, min(INTL_MAX_AGENT_EDGE, edge))

        # The headline sentence, built from the numbers actually used.
        tz_sentence = (
            f"{away_team} crosses {abs(away_tz):.0f} time zones "
            f"{'eastward' if away_tz > 0 else 'westward'} compared with "
            f"{home_team} crossing {abs(home_tz):.0f}"
        )
        if clamped > 0.0005:
            tz_sentence += f", giving {home_team} a small travel/rest advantage"
        elif clamped < -0.0005:
            tz_sentence += f", giving {away_team} a small travel/rest advantage"
        else:
            tz_sentence += ", so neither side gains a travel advantage"

        factors = [
            f"International neutral-site game in {country}",
            "Standard home-field advantage removed",
            tz_sentence,
        ] + factors

        detail = {
            "venue_country": country,
            "away_travel_miles": round(travel["distance_miles"]),
            "home_travel_miles": round(home_travel["distance_miles"]),
            "away_timezones": away_tz,
            "home_timezones": home_tz,
            "away_prior_week_miles": round(away_prior),
            "home_prior_week_miles": round(home_prior),
            "away_prior_visits": away_visits,
            "home_prior_visits": home_visits,
            "raw_edge": round(edge, 4),
            "applied_edge": round(clamped, 4),
            "clamped": abs(edge) > INTL_MAX_AGENT_EDGE,
        }
        return clamped, factors, detail

    def _previous_week_burden(self, team: str, kickoff: Optional[datetime]) -> float:
        """
        Miles the team flew for its previous game, if there was one within a
        fortnight. Derived from the schedule already loaded - no new data, and
        no guess about when anyone actually travelled.
        """
        if kickoff is None:
            return 0.0
        previous = [game for game in self.game_log.get(team, [])
                    if game["kickoff"] < kickoff and (kickoff - game["kickoff"]).days <= 14]
        if not previous:
            return 0.0
        last = max(previous, key=lambda game: game["kickoff"])
        if last["home_team"] == team and not last.get("neutral_site"):
            return 0.0
        return travel_between(team, last["home_team"], last.get("venue"))["distance_miles"]

    def _prior_international_visits(self, team: str, venue: Optional[str],
                                    kickoff: Optional[datetime]) -> int:
        """How often this team has played at this venue before now."""
        if not venue or kickoff is None:
            return 0
        return sum(1 for game in self.game_log.get(team, [])
                   if game.get("venue") == venue and game["kickoff"] < kickoff)

    def _generate_reasoning(self, factors: List[str], winner: str, confidence: float) -> str:
        parts = list(factors[:3])
        if not parts:
            parts.append("No notable schedule situation")
        parts.append(f"Situational edge to {winner}")
        if confidence < 0.55:
            parts.append("Low confidence - schedule effects are small by nature")
        return ". ".join(parts) + "."

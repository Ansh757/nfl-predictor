"""
Neutral-site games.

The 2026 schedule has five games at venues that are nobody's home stadium -
Melbourne, Rio, Paris, Munich and Mexico City - and one of them is in week 1.
travel_between resolved its destination from the *home team*, never from the
venue, so San Francisco at the Melbourne Cricket Ground was scored as a
313-mile trip to SoFi instead of a 7,900-mile one, and the Rams were treated as
if they had not travelled at all.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.rest_travel_agent import RestTravelAgent  # noqa: E402
from utils.venues import (  # noqa: E402
    NEUTRAL_VENUES, is_neutral_site, travel_between, venue_location,
)

MCG = "Melbourne Cricket Ground"


class GameStub:
    """Duck-typed the same way backtest.py's stub is."""

    def __init__(self, home, away, venue, game_time="2026-09-11T00:35Z"):
        self.game_id = 9001
        self.home_team_name = home
        self.away_team_name = away
        self.venue = venue
        self.game_time = game_time
        self.is_dome = False


class TestVenueResolution:
    def test_a_home_game_resolves_to_the_home_stadium(self):
        assert venue_location("Los Angeles Rams") == venue_location("Los Angeles Rams", "SoFi Stadium")

    def test_a_neutral_site_overrides_the_home_stadium(self):
        home = venue_location("Los Angeles Rams")
        neutral = venue_location("Los Angeles Rams", MCG)
        assert neutral != home
        assert neutral["lat"] == pytest.approx(-37.82, abs=0.01)

    def test_an_unknown_venue_falls_back_rather_than_failing(self):
        # A stadium rename or a venue we have not catalogued must degrade to the
        # old behaviour, not raise.
        assert venue_location("Los Angeles Rams", "Some New Stadium") == \
               venue_location("Los Angeles Rams")

    def test_every_2026_international_venue_is_catalogued(self):
        # These are exactly the venues in the 2026 schedule that appear in no
        # earlier season. Missing one means silently scoring it as a home game.
        for venue in ["Melbourne Cricket Ground", "Maracanã Stadium", "Stade de France",
                      "FC Bayern Munich Stadium", "Estadio Banorte"]:
            assert is_neutral_site(venue), f"{venue} would be treated as a home game"

    def test_real_stadiums_are_not_neutral(self):
        assert not is_neutral_site("SoFi Stadium")
        assert not is_neutral_site(None)

    def test_catalogued_venues_have_what_the_maths_needs(self):
        for name, venue in NEUTRAL_VENUES.items():
            assert -90 <= venue["lat"] <= 90, name
            assert -180 <= venue["lon"] <= 180, name
            assert -12 <= venue["utc_offset"] <= 14, name


class TestTravelToNeutralSites:
    def test_the_visitors_trip_is_measured_to_the_real_venue(self):
        near = travel_between("San Francisco 49ers", "Los Angeles Rams")
        far = travel_between("San Francisco 49ers", "Los Angeles Rams", MCG)
        assert near["distance_miles"] < 500
        assert far["distance_miles"] > 7000
        assert far["timezone_shift"] > 12

    def test_the_home_team_travels_too(self):
        # The bug in one line: the Rams' trip to Melbourne used to be zero,
        # because the destination was resolved as their own stadium.
        assert travel_between("Los Angeles Rams", "Los Angeles Rams", MCG)["distance_miles"] > 7000
        assert travel_between("Los Angeles Rams", "Los Angeles Rams")["distance_miles"] == 0

    def test_omitting_the_venue_keeps_the_old_behaviour(self):
        # Every existing caller passes no venue and must be unaffected.
        assert travel_between("New England Patriots", "Seattle Seahawks") == \
               travel_between("New England Patriots", "Seattle Seahawks", None)


class TestAgentAtANeutralSite:
    def _predict(self, venue):
        agent = RestTravelAgent("Rest & Travel")
        game = GameStub("Los Angeles Rams", "San Francisco 49ers", venue)
        return asyncio.run(agent.predict_game(game, {}))

    def test_the_burden_nearly_cancels(self):
        result = self._predict(MCG)
        assert result["neutral_site"] is True
        # Both sides fly from California, so neither gains a travel edge
        assert abs(result["travel_miles"] - result["home_travel_miles"]) < 500

    def test_the_reasoning_says_it_is_a_neutral_site(self):
        # Otherwise the text describes a routine Rams home game, which is the
        # most visible way this was wrong.
        assert "Neutral site" in self._predict(MCG)["reasoning"]

    def test_an_ordinary_home_game_is_untouched(self):
        result = self._predict("SoFi Stadium")
        assert result["neutral_site"] is False
        assert result["home_travel_miles"] == 0
        assert "Neutral site" not in result["reasoning"]

    def test_a_genuine_long_away_trip_is_still_penalised(self):
        # The net-of-home-travel change must not defang the ordinary case.
        agent = RestTravelAgent("Rest & Travel")
        game = GameStub("Seattle Seahawks", "Miami Dolphins", "Lumen Field")
        result = asyncio.run(agent.predict_game(game, {}))
        assert result["travel_miles"] > 2000
        assert result["home_travel_miles"] == 0

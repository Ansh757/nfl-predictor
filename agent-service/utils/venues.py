"""
venues.py - Home venue, coordinates and timezone for all 32 teams.

Single source of truth for anything geographic. The weather agent keeps its own
table for historical reasons; this one is complete (domes included, which the
weather table omits because it short-circuits before needing coordinates).

`utc_offset` is standard-time offset in hours. Arizona is -7 year round because
it does not observe daylight saving.
"""
from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict, Optional

TEAM_VENUES: Dict[str, Dict[str, Any]] = {
    # AFC East
    "Buffalo Bills":        {"venue": "Highmark Stadium",           "lat": 42.7738, "lon": -78.7870, "utc_offset": -5, "dome": False},
    "Miami Dolphins":       {"venue": "Hard Rock Stadium",          "lat": 25.9580, "lon": -80.2389, "utc_offset": -5, "dome": False},
    "New England Patriots": {"venue": "Gillette Stadium",           "lat": 42.0909, "lon": -71.2643, "utc_offset": -5, "dome": False},
    "New York Jets":        {"venue": "MetLife Stadium",            "lat": 40.8128, "lon": -74.0742, "utc_offset": -5, "dome": False},

    # AFC North
    "Baltimore Ravens":     {"venue": "M&T Bank Stadium",           "lat": 39.2780, "lon": -76.6227, "utc_offset": -5, "dome": False},
    "Cincinnati Bengals":   {"venue": "Paycor Stadium",             "lat": 39.0954, "lon": -84.5160, "utc_offset": -5, "dome": False},
    "Cleveland Browns":     {"venue": "Huntington Bank Field",      "lat": 41.5061, "lon": -81.6995, "utc_offset": -5, "dome": False},
    "Pittsburgh Steelers":  {"venue": "Acrisure Stadium",           "lat": 40.4468, "lon": -80.0158, "utc_offset": -5, "dome": False},

    # AFC South
    "Houston Texans":       {"venue": "NRG Stadium",                "lat": 29.6847, "lon": -95.4107, "utc_offset": -6, "dome": True},
    "Indianapolis Colts":   {"venue": "Lucas Oil Stadium",          "lat": 39.7601, "lon": -86.1639, "utc_offset": -5, "dome": True},
    "Jacksonville Jaguars": {"venue": "EverBank Stadium",           "lat": 30.3239, "lon": -81.6373, "utc_offset": -5, "dome": False},
    "Tennessee Titans":     {"venue": "Nissan Stadium",             "lat": 36.1665, "lon": -86.7713, "utc_offset": -6, "dome": False},

    # AFC West
    "Denver Broncos":       {"venue": "Empower Field at Mile High", "lat": 39.7439, "lon": -105.0200, "utc_offset": -7, "dome": False},
    "Kansas City Chiefs":   {"venue": "Arrowhead Stadium",          "lat": 39.0489, "lon": -94.4839, "utc_offset": -6, "dome": False},
    "Las Vegas Raiders":    {"venue": "Allegiant Stadium",          "lat": 36.0909, "lon": -115.1833, "utc_offset": -8, "dome": True},
    "Los Angeles Chargers": {"venue": "SoFi Stadium",               "lat": 33.9535, "lon": -118.3390, "utc_offset": -8, "dome": False},

    # NFC East
    "Dallas Cowboys":       {"venue": "AT&T Stadium",               "lat": 32.7473, "lon": -97.0945, "utc_offset": -6, "dome": True},
    "New York Giants":      {"venue": "MetLife Stadium",            "lat": 40.8128, "lon": -74.0742, "utc_offset": -5, "dome": False},
    "Philadelphia Eagles":  {"venue": "Lincoln Financial Field",    "lat": 39.9008, "lon": -75.1675, "utc_offset": -5, "dome": False},
    "Washington Commanders": {"venue": "Northwest Stadium",         "lat": 38.9076, "lon": -76.8645, "utc_offset": -5, "dome": False},

    # NFC North
    "Chicago Bears":        {"venue": "Soldier Field",              "lat": 41.8623, "lon": -87.6167, "utc_offset": -6, "dome": False},
    "Detroit Lions":        {"venue": "Ford Field",                 "lat": 42.3400, "lon": -83.0456, "utc_offset": -5, "dome": True},
    "Green Bay Packers":    {"venue": "Lambeau Field",              "lat": 44.5013, "lon": -88.0622, "utc_offset": -6, "dome": False},
    "Minnesota Vikings":    {"venue": "U.S. Bank Stadium",          "lat": 44.9736, "lon": -93.2575, "utc_offset": -6, "dome": True},

    # NFC South
    "Atlanta Falcons":      {"venue": "Mercedes-Benz Stadium",      "lat": 33.7554, "lon": -84.4008, "utc_offset": -5, "dome": True},
    "Carolina Panthers":    {"venue": "Bank of America Stadium",    "lat": 35.2258, "lon": -80.8530, "utc_offset": -5, "dome": False},
    "New Orleans Saints":   {"venue": "Caesars Superdome",          "lat": 29.9511, "lon": -90.0812, "utc_offset": -6, "dome": True},
    "Tampa Bay Buccaneers": {"venue": "Raymond James Stadium",      "lat": 27.9759, "lon": -82.5033, "utc_offset": -5, "dome": False},

    # NFC West
    "Arizona Cardinals":    {"venue": "State Farm Stadium",         "lat": 33.5276, "lon": -112.2626, "utc_offset": -7, "dome": True},
    "Los Angeles Rams":     {"venue": "SoFi Stadium",               "lat": 33.9535, "lon": -118.3390, "utc_offset": -8, "dome": False},
    "San Francisco 49ers":  {"venue": "Levi's Stadium",             "lat": 37.4031, "lon": -121.9695, "utc_offset": -8, "dome": False},
    "Seattle Seahawks":     {"venue": "Lumen Field",                "lat": 47.5952, "lon": -122.3316, "utc_offset": -8, "dome": False},
}

EARTH_RADIUS_MILES = 3958.8


# Neutral sites. A game here is nobody's home game: both teams fly, and for the
# international ones both fly a very long way.
#
# Without these, travel_between resolved the destination from the home team and
# so scored San Francisco at Melbourne as a 350-mile trip to SoFi rather than a
# 7,900-mile one with most of a day of body-clock shift. The 2026 season has
# five of them, one in week 1.
#
# `utc_offset` is standard-time offset, matching TEAM_VENUES. None of these
# countries observe DST during the NFL season: Australia's begins in October,
# and Brazil and Mexico abolished it.
NEUTRAL_VENUES: Dict[str, Dict[str, Any]] = {
    "Melbourne Cricket Ground":  {"lat": -37.8200, "lon": 144.9834, "utc_offset": 10,  "dome": False},
    "Maracanã Stadium":          {"lat": -22.9121, "lon": -43.2302, "utc_offset": -3,  "dome": False},
    "Stade de France":           {"lat":  48.9245, "lon":   2.3601, "utc_offset": 1,   "dome": False},
    "FC Bayern Munich Stadium":  {"lat":  48.2188, "lon":  11.6247, "utc_offset": 1,   "dome": False},
    "Estadio Banorte":           {"lat":  19.3029, "lon": -99.1505, "utc_offset": -6,  "dome": False},
}


def venue_for(team: str) -> Optional[Dict[str, Any]]:
    return TEAM_VENUES.get(team)


def is_neutral_site(venue: Optional[str]) -> bool:
    """True when the named venue is nobody's home stadium."""
    return bool(venue) and venue in NEUTRAL_VENUES


def venue_location(home_team: str, venue: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Where the game is actually played.

    Falls back to the home team's own stadium, which is right for all but a
    handful of games a season - and silently wrong for those, which is why the
    venue name is now consulted first.
    """
    if venue and venue in NEUTRAL_VENUES:
        return NEUTRAL_VENUES[venue]
    return venue_for(home_team)


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in miles."""
    lat1_r, lat2_r = radians(lat1), radians(lat2)
    d_lat = lat2_r - lat1_r
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(a))


def travel_between(from_team: str, to_team: str,
                   venue: Optional[str] = None) -> Dict[str, float]:
    """
    Distance and timezone shift for `from_team` travelling to the game's venue.

    A positive `timezone_shift` means travelling east (body clock behind local
    time), which research consistently finds to be the harder direction.

    `venue` names where the game is played. Omit it and the destination is the
    home team's stadium, which is what every caller assumed and what is true for
    all but a few games a season. Pass it and a neutral site resolves correctly -
    including the case that matters most, where the "home" team is the one
    flying 7,000 miles.
    """
    origin = venue_for(from_team)
    destination = venue_location(to_team, venue)
    if not origin or not destination:
        return {"distance_miles": 0.0, "timezone_shift": 0.0}

    return {
        "distance_miles": round(
            haversine_miles(origin["lat"], origin["lon"], destination["lat"], destination["lon"]), 1
        ),
        "timezone_shift": float(destination["utc_offset"] - origin["utc_offset"])
    }

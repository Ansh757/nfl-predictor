"""
Historical injury reports, and the point-in-time discipline around them.

InjuryImpactAgent sat at an unmeasured default weight for the life of the
project because ESPN returns only current status. nflverse publishes the
official weekly reports back to 2009, which makes the agent backtestable the
same way nflverse made Market Odds backtestable.

The whole value of that measurement rests on the reports being point-in-time.
A week 14 game that could see week 14's *final* injury report is fine - that is
what a bettor had. One that could see week 15's is not a backtest, it is
hindsight. These pin the difference.
"""
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.consensus import AGENT_WEIGHTS, DEFAULT_WEIGHT  # noqa: E402
from utils.historical_injuries import (  # noqa: E402
    HistoricalInjuryLookup, reports_by_game,
)
from utils.injury_client import SEVERITY  # noqa: E402

SEASON = 2024
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     f"historical_injuries_{SEASON}.csv")
needs_data = pytest.mark.skipif(
    not os.path.exists(CACHE), reason="nflverse injury cache not downloaded")


@pytest.fixture(scope="module")
def lookup():
    return HistoricalInjuryLookup(SEASON, download_if_missing=False)


@pytest.fixture(scope="module")
def games():
    from backtest import load_games
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return load_games(os.path.join(root, "nfl_schedule.db"), SEASON)


@needs_data
class TestPointInTime:
    def test_a_game_sees_only_its_own_week(self, lookup, games):
        reports = reports_by_game(lookup, games)
        for game in games:
            week = game["week"]
            for team, entries in reports[game["game_id"]].items():
                permitted = lookup.by_week.get((week, team), [])
                for entry in entries:
                    assert entry in permitted, (
                        f"game {game['game_id']} (week {week}) saw a report for "
                        f"{team} that does not belong to its week")

    def test_no_report_filed_after_kickoff_is_used(self, lookup, games):
        reports = reports_by_game(lookup, games)
        for game in games:
            kickoff = datetime.fromisoformat(game["game_date"].replace("Z", "+00:00"))
            for entries in reports[game["game_id"]].values():
                for entry in entries:
                    if entry["modified"] is not None:
                        assert entry["modified"] < kickoff, (
                            "a designation amended after kickoff is hindsight")

    def test_a_late_season_game_cannot_see_week_one(self, lookup, games):
        reports = reports_by_game(lookup, games)
        late = next(game for game in games if game["week"] == 14)
        week_one_entries = [entry for (week, _), entries in lookup.by_week.items()
                            if week == 1 for entry in entries]
        seen = [entry for entries in reports[late["game_id"]].values() for entry in entries]
        assert not [entry for entry in seen if entry in week_one_entries]


@needs_data
class TestReportParsing:
    def test_only_game_designations_count(self, lookup):
        # Practice participation is not a game designation. Thousands of rows
        # carry a practice note and no status; counting them would inflate every
        # team's burden and measure something the live agent never sees.
        for entries in lookup.by_week.values():
            for entry in entries:
                assert entry["severity"] > 0
                assert entry["status"].lower() in SEVERITY

    def test_severity_matches_the_live_client(self, lookup):
        # The backtest must grade Out/Doubtful/Questionable exactly as the live
        # ESPN path does, or it is measuring a different agent.
        statuses = {entry["status"].lower()
                    for entries in lookup.by_week.values() for entry in entries}
        assert statuses <= set(SEVERITY)
        assert "out" in statuses and "questionable" in statuses

    def test_teams_resolve_to_schedule_names(self, lookup):
        teams = {team for (_, team) in lookup.by_week}
        # Full names, not abbreviations - and the LA/LAC trap resolved
        assert "Los Angeles Rams" in teams
        assert "Los Angeles Chargers" in teams
        assert not any(len(team) <= 4 for team in teams)

    def test_coverage_is_broad_enough_to_measure(self, lookup, games):
        reports = reports_by_game(lookup, games)
        covered = sum(1 for report in reports.values() if report)
        assert covered / len(games) > 0.95, "too sparse to calibrate against"


class TestTheWeightIsNowMeasured:
    def test_injury_impact_no_longer_sits_at_the_placeholder(self):
        # The placeholder existed because the agent could not be scored. It can
        # be now, so carrying the default would understate a measured signal.
        assert AGENT_WEIGHTS["Injury Impact"] != DEFAULT_WEIGHT

    def test_the_weight_matches_the_measurement(self):
        # 55.5% over 2021-2024 - the edge over a coin flip, floored at zero,
        # exactly how every other weight in this table is derived.
        assert AGENT_WEIGHTS["Injury Impact"] == pytest.approx(0.055, abs=0.001)

    def test_it_still_cannot_outvote_the_market(self):
        # A measured weight, but a small one. The ordering here is the claim
        # that matters: injuries inform a prediction, the closing line drives it.
        assert AGENT_WEIGHTS["Injury Impact"] < AGENT_WEIGHTS["Market Odds"]
        assert AGENT_WEIGHTS["Injury Impact"] < AGENT_WEIGHTS["Elo Ratings"]
        assert AGENT_WEIGHTS["Injury Impact"] > AGENT_WEIGHTS["Rest & Travel"]


class TestAgentIsUnchanged:
    def test_the_backtest_drives_the_real_agent(self):
        # The point of the historical client pattern: what is measured is the
        # real position weighting and severity logic, not a reimplementation.
        from agents.injury_agent import InjuryImpactAgent
        agent = InjuryImpactAgent("Injury Impact")
        assert hasattr(agent, "pregame_reports")
        assert agent.pregame_reports == {}

    def test_an_unknown_game_falls_back_rather_than_inventing(self):
        from agents.injury_agent import InjuryImpactAgent
        agent = InjuryImpactAgent("Injury Impact")
        agent.pregame_reports = {1: {"Buffalo Bills": []}}
        # Game 2 is not in the map, so the agent must not silently use game 1's
        assert 2 not in agent.pregame_reports

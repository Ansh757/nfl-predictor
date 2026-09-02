package com.nflpredict.service;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.LocalDate;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * A season is not a calendar year, and settlement used to assume it was.
 *
 * <p>Season 2026 runs from September 2026 into February 2027, so from January
 * the calendar year is one ahead of the season label. Taking the calendar year
 * meant that every January the weekly settlement went looking for results in a
 * season that had not started yet, found none, and scored nothing - through the
 * playoffs, which is the stretch where it matters most.
 */
class SeasonBoundaryTest {

    @Test
    @DisplayName("autumn months belong to the season that just started")
    void autumnIsTheCurrentYear() {
        assertEquals(2026, SettlementService.seasonOf(LocalDate.of(2026, 9, 10)));
        assertEquals(2026, SettlementService.seasonOf(LocalDate.of(2026, 12, 31)));
    }

    @Test
    @DisplayName("January and February still belong to the previous season")
    void newYearIsStillTheOldSeason() {
        // Wild card weekend
        assertEquals(2026, SettlementService.seasonOf(LocalDate.of(2027, 1, 1)));
        // Super Bowl
        assertEquals(2026, SettlementService.seasonOf(LocalDate.of(2027, 2, 8)));
        assertEquals(2026, SettlementService.seasonOf(LocalDate.of(2027, 2, 28)));
    }

    @Test
    @DisplayName("March is where the new season label takes over")
    void marchStartsTheNewLabel() {
        // Nothing is played in March; the boundary just has to be unambiguous
        // and to match the frontend, which derives its season the same way.
        assertEquals(2027, SettlementService.seasonOf(LocalDate.of(2027, 3, 1)));
    }
}

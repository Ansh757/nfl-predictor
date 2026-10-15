package com.nflpredict.service;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.LocalDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Official predictions are recorded on game day, not on Wednesday.
 *
 * <p>The record workflow runs daily with a 24-hour window. Because the first
 * record for a game is the one that stands, a run must not touch a game outside
 * its window at all - otherwise Sunday's games would be locked in by whichever
 * earlier run happened to see them.
 */
class RecordingWindowTest {

    /** Sunday 06:00 UTC, the morning run. */
    private static final LocalDateTime SUNDAY_RUN = LocalDateTime.of(2026, 10, 18, 6, 0);

    @Test
    @DisplayName("no window keeps the original whole-week behaviour")
    void noWindowMeansEveryGame() {
        assertTrue(PredictionOrchestrator.inWindow(SUNDAY_RUN.plusDays(4), SUNDAY_RUN, null));
        assertTrue(PredictionOrchestrator.inWindow(null, SUNDAY_RUN, null));
    }

    @Test
    @DisplayName("the Sunday morning run records Sunday's games, including the night game")
    void sundayRunCoversSunday() {
        // London 13:30 UTC, the early slate 17:00, late 20:25, Sunday night 00:20 Monday
        assertTrue(PredictionOrchestrator.inWindow(SUNDAY_RUN.withHour(13).withMinute(30), SUNDAY_RUN, 24));
        assertTrue(PredictionOrchestrator.inWindow(SUNDAY_RUN.withHour(17), SUNDAY_RUN, 24));
        assertTrue(PredictionOrchestrator.inWindow(SUNDAY_RUN.withHour(20).withMinute(25), SUNDAY_RUN, 24));
        assertTrue(PredictionOrchestrator.inWindow(SUNDAY_RUN.plusDays(1).withHour(0).withMinute(20), SUNDAY_RUN, 24));
    }

    @Test
    @DisplayName("the Sunday run leaves Monday night for Monday's run")
    void mondayNightIsNotLockedInEarly() {
        LocalDateTime mondayNight = SUNDAY_RUN.plusDays(2).withHour(0).withMinute(15);
        assertFalse(PredictionOrchestrator.inWindow(mondayNight, SUNDAY_RUN, 24));
    }

    @Test
    @DisplayName("a game already under way, or with no kickoff, is outside any window")
    void startedOrUnknownIsOutside() {
        assertFalse(PredictionOrchestrator.inWindow(SUNDAY_RUN.minusMinutes(1), SUNDAY_RUN, 24));
        assertFalse(PredictionOrchestrator.inWindow(SUNDAY_RUN, SUNDAY_RUN, 24));
        assertFalse(PredictionOrchestrator.inWindow(null, SUNDAY_RUN, 24));
    }
}

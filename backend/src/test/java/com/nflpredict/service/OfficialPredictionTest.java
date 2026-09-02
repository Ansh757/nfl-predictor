package com.nflpredict.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.nflpredict.dto.ConsensusResult;
import com.nflpredict.model.PredictionRecord;
import com.nflpredict.repository.PredictionRecordRepository;
import com.nflpredict.service.PredictionOrchestrator.OfficialOutcome;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.TestPropertySource;

/**
 * The weekly endpoint was not idempotent. Re-running it inserted a second row
 * per game - week 1 of 2026 ended up with 33 rows for 16 games - and settlement
 * then scored the newest copy rather than the original pre-kickoff call.
 *
 * <p>These run against a real database with the real schema, migrations
 * included, because the guarantee being tested is a database constraint. A
 * mocked repository would happily accept two inserts and prove nothing.
 */
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@TestPropertySource(properties = {
    "spring.datasource.url=jdbc:h2:mem:predictions;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.username=sa",
    "spring.datasource.password=",
    "spring.jpa.hibernate.ddl-auto=none",
    "spring.flyway.enabled=true"
})
class OfficialPredictionTest {

    private static final int SEASON = 2026;
    private static final int WEEK = 1;
    /** Kickoff for every fixture below: 2026-09-13T17:00Z. */
    private static final LocalDateTime KICKOFF = LocalDateTime.of(2026, 9, 13, 17, 0);

    @Autowired
    private PredictionRecordRepository repository;

    private PredictionOrchestrator orchestrator;

    /** Fixed at three days before kickoff unless a test moves it. */
    private PredictionOrchestrator orchestratorAt(LocalDateTime now) {
        Clock clock = Clock.fixed(now.toInstant(ZoneOffset.UTC), ZoneOffset.UTC);
        return new PredictionOrchestrator(
                null, repository, Runnable::run, clock,
                "http://localhost:1", 1000, 0);
    }

    private static ConsensusResult resultFor(long gameId) {
        ConsensusResult result = new ConsensusResult();
        result.setGameId(gameId);
        result.setHomeTeam("Home " + gameId);
        result.setAwayTeam("Away " + gameId);
        result.setWinner("Home " + gameId);
        result.setConfidence(0.61);
        result.setMethod("weighted");
        return result;
    }

    /** The sixteen games of a week, as predictWeek would hand them over. */
    private List<ConsensusResult> week() {
        List<ConsensusResult> games = new ArrayList<>();
        for (long gameId = 1; gameId <= 16; gameId++) {
            games.add(resultFor(gameId));
        }
        return games;
    }

    private int recordWeek() {
        int recorded = 0;
        for (ConsensusResult game : week()) {
            if (orchestrator.persistOfficial(game, KICKOFF, SEASON, WEEK) == OfficialOutcome.RECORDED) {
                recorded++;
            }
        }
        return recorded;
    }

    @BeforeEach
    void setUp() {
        repository.deleteAll();
        orchestrator = orchestratorAt(KICKOFF.minusDays(3));
    }

    @Test
    @DisplayName("a first week 1 run stores sixteen predictions")
    void firstRunStoresSixteen() {
        assertEquals(16, recordWeek());
        assertEquals(16, repository.count());
    }

    @Test
    @DisplayName("re-running the identical request leaves the count at sixteen")
    void repeatRunDoesNotDuplicate() {
        recordWeek();
        assertEquals(16, repository.count());

        // This is the reported bug: the second pass added another sixteen rows.
        int recordedAgain = recordWeek();

        assertEquals(0, recordedAgain, "no game should be recorded twice");
        assertEquals(16, repository.count());
    }

    @Test
    @DisplayName("a re-run never overwrites the original prediction")
    void repeatRunDoesNotOverwriteTheOriginal() {
        orchestrator.persistOfficial(resultFor(1L), KICKOFF, SEASON, WEEK);
        PredictionRecord original = repository.findFirstByGameIdOrderByPredictedAtAsc(1L).orElseThrow();
        LocalDateTime originalPredictedAt = original.getPredictedAt();

        // A day later the line has moved and the model now likes the other side
        PredictionOrchestrator later = orchestratorAt(KICKOFF.minusDays(1));
        ConsensusResult changedMind = resultFor(1L);
        changedMind.setWinner("Away 1");
        changedMind.setConfidence(0.72);

        assertEquals(OfficialOutcome.ALREADY_RECORDED,
                later.persistOfficial(changedMind, KICKOFF, SEASON, WEEK));

        PredictionRecord onFile = repository.findFirstByGameIdOrderByPredictedAtAsc(1L).orElseThrow();
        assertEquals("Home 1", onFile.getPredictedWinner(), "the original pick must stand");
        assertEquals(0.61, onFile.getConfidence(), 1e-9);
        assertEquals(originalPredictedAt, onFile.getPredictedAt());
        assertEquals(1, repository.count());
    }

    @Test
    @DisplayName("a request after kickoff cannot create an official prediction")
    void afterKickoffCannotCreate() {
        PredictionOrchestrator tooLate = orchestratorAt(KICKOFF.plusMinutes(1));

        assertEquals(OfficialOutcome.AFTER_KICKOFF,
                tooLate.persistOfficial(resultFor(1L), KICKOFF, SEASON, WEEK));
        assertEquals(0, repository.count());
    }

    @Test
    @DisplayName("a request after kickoff cannot replace an existing prediction either")
    void afterKickoffCannotReplace() {
        orchestrator.persistOfficial(resultFor(1L), KICKOFF, SEASON, WEEK);

        PredictionOrchestrator tooLate = orchestratorAt(KICKOFF.plusHours(4));
        ConsensusResult hindsight = resultFor(1L);
        hindsight.setWinner("Away 1");
        tooLate.persistOfficial(hindsight, KICKOFF, SEASON, WEEK);

        assertEquals(1, repository.count());
        assertEquals("Home 1",
                repository.findFirstByGameIdOrderByPredictedAtAsc(1L).orElseThrow().getPredictedWinner());
    }

    @Test
    @DisplayName("kickoff exactly now is already too late")
    void kickoffBoundaryIsExclusive() {
        PredictionOrchestrator atKickoff = orchestratorAt(KICKOFF);
        assertEquals(OfficialOutcome.AFTER_KICKOFF,
                atKickoff.persistOfficial(resultFor(1L), KICKOFF, SEASON, WEEK));
    }

    @Test
    @DisplayName("an unknown kickoff is refused rather than guessed")
    void unknownKickoffIsRefused() {
        // The single-game endpoint has no kickoff to offer. A record that cannot
        // be certified as pre-kickoff would corrupt the accuracy measurement.
        assertEquals(OfficialOutcome.KICKOFF_UNKNOWN,
                orchestrator.persistOfficial(resultFor(1L), null, SEASON, WEEK));
        assertEquals(0, repository.count());
    }

    @Test
    @DisplayName("concurrent requests for the same game produce exactly one row")
    void concurrentRequestsCannotDuplicate() throws Exception {
        // predictWeek fans out across a thread pool, so two callers really can
        // pass existsByGameId before either inserts. Only the unique constraint
        // stops the second write.
        int threads = 12;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch startLine = new CountDownLatch(1);
        AtomicInteger recorded = new AtomicInteger();

        try {
            for (int i = 0; i < threads; i++) {
                pool.submit(() -> {
                    startLine.await();
                    if (orchestrator.persistOfficial(resultFor(1L), KICKOFF, SEASON, WEEK)
                            == OfficialOutcome.RECORDED) {
                        recorded.incrementAndGet();
                    }
                    return null;
                });
            }
            startLine.countDown();
            pool.shutdown();
            assertTrue(pool.awaitTermination(30, TimeUnit.SECONDS), "threads did not finish");
        } finally {
            pool.shutdownNow();
        }

        assertEquals(1, repository.count(), "the constraint must collapse the race to one row");
        assertEquals(1, recorded.get(), "exactly one caller may believe it recorded the prediction");
    }

    @Test
    @DisplayName("what is stored is enough to audit the prediction later")
    void storesTheFieldsAccuracyDependsOn() {
        orchestrator.persistOfficial(resultFor(7L), KICKOFF, SEASON, WEEK);
        PredictionRecord record = repository.findFirstByGameIdOrderByPredictedAtAsc(7L).orElseThrow();

        assertEquals(7L, record.getGameId());
        assertEquals(SEASON, record.getSeason());
        assertEquals(WEEK, record.getWeek());
        assertEquals(KICKOFF, record.getKickoffAt());
        assertNotNull(record.getPredictedAt());
        assertTrue(record.getPredictedAt().isBefore(record.getKickoffAt()),
                "an official prediction is by definition pre-kickoff");
        assertEquals(Boolean.FALSE, record.getSettled());
        assertEquals(null, record.getWasCorrect());
    }

    @Test
    @DisplayName("accuracy reports totals, settled, pending and correct")
    void accuracyPayloadIsComplete() {
        recordWeek();
        orchestrator.settle(1L, "Home 1");      // right
        orchestrator.settle(2L, "Away 2");      // wrong

        Map<String, Object> accuracy = orchestrator.liveAccuracy();

        assertEquals(16L, accuracy.get("total_predictions"));
        assertEquals(2L, accuracy.get("settled_predictions"));
        assertEquals(14L, accuracy.get("pending_predictions"));
        assertEquals(1L, accuracy.get("correct"));
        assertEquals(0.5, (Double) accuracy.get("accuracy"), 1e-9);
    }

    @Test
    @DisplayName("the database refuses a duplicate even when the guard is bypassed")
    void constraintRejectsADirectDuplicate() {
        orchestrator.persistOfficial(resultFor(1L), KICKOFF, SEASON, WEEK);

        // Bypass persistOfficial entirely and write straight to the repository,
        // the way a re-run used to. The constraint is the last line of defence
        // and it has to hold on its own.
        PredictionRecord duplicate = new PredictionRecord(
                1L, SEASON, WEEK, "Home 1", "Away 1", "Away 1", 0.8,
                "weighted", "[]", KICKOFF, KICKOFF.minusHours(1));

        assertThrows(DataIntegrityViolationException.class,
                () -> repository.saveAndFlush(duplicate));
    }

    @Test
    @DisplayName("settlement scores exactly one prediction per game")
    void settlementScoresOnePerGame() {
        recordWeek();
        SettlementService settlement = new SettlementService(
                repository, "http://localhost:1", true, 1000L);

        Map<Long, String> winners = new HashMap<>();
        for (long gameId = 1; gameId <= 16; gameId++) {
            winners.put(gameId, "Home " + gameId);      // every home side won
        }

        SettlementService.SettleCounts counts = settlement.settlePending(winners);

        assertEquals(16, counts.settled());
        assertEquals(0, counts.duplicatesSkipped());
        assertEquals(16L, repository.countSettled());
        assertEquals(16L, repository.countCorrect());
        assertEquals(0L, repository.countBySettledFalse());

        // A second pass has nothing left to score - settlement is repeatable
        SettlementService.SettleCounts again = settlement.settlePending(winners);
        assertEquals(0, again.settled());
        assertEquals(16L, repository.countSettled());
    }

    @Test
    @DisplayName("settling twice does not rewrite an already-scored prediction")
    void settlingIsNotRepeatable() {
        orchestrator.persistOfficial(resultFor(1L), KICKOFF, SEASON, WEEK);
        orchestrator.settle(1L, "Home 1");
        orchestrator.settle(1L, "Away 1");   // a later pass with a different answer

        PredictionRecord record = repository.findFirstByGameIdOrderByPredictedAtAsc(1L).orElseThrow();
        assertEquals("Home 1", record.getActualWinner());
        assertEquals(Boolean.TRUE, record.getWasCorrect());
    }
}

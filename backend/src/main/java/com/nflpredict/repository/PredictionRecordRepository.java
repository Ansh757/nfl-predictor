package com.nflpredict.repository;

import com.nflpredict.model.PredictionRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface PredictionRecordRepository extends JpaRepository<PredictionRecord, Long> {

    /**
     * The official prediction for a game: the earliest one recorded.
     *
     * <p>Ordering ascending is the point. The previous version took the newest
     * record, so once a game had duplicates the settlement scored whichever
     * copy had been written last - which for a re-run of the weekly endpoint
     * meant scoring a prediction made after the original, and potentially after
     * kickoff. The unique constraint now makes duplicates impossible, but
     * ordering by predictedAt keeps this correct for rows written before it
     * existed.
     */
    Optional<PredictionRecord> findFirstByGameIdOrderByPredictedAtAsc(Long gameId);

    /**
     * Cheap pre-check before writing. Not sufficient on its own - see
     * PredictionOrchestrator.persistOfficial - because the week fans out across
     * a thread pool and two callers can both pass it before either inserts. The
     * unique constraint is what actually enforces uniqueness; this only avoids
     * the common case.
     */
    boolean existsByGameId(Long gameId);

    List<PredictionRecord> findBySettledFalse();

    /** Unsettled records oldest-first, so settlement scores originals first. */
    List<PredictionRecord> findBySettledFalseOrderByPredictedAtAsc();

    /** Live accuracy across every settled prediction. */
    @Query("SELECT COUNT(p) FROM PredictionRecord p WHERE p.settled = true")
    long countSettled();

    @Query("SELECT COUNT(p) FROM PredictionRecord p WHERE p.settled = true AND p.wasCorrect = true")
    long countCorrect();

    long countBySettledFalse();
}

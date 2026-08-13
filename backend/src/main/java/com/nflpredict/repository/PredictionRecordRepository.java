package com.nflpredict.repository;

import com.nflpredict.model.PredictionRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface PredictionRecordRepository extends JpaRepository<PredictionRecord, Long> {

    Optional<PredictionRecord> findFirstByGameIdOrderByCreatedAtDesc(Long gameId);

    List<PredictionRecord> findBySettledFalse();

    /** Live accuracy across every settled prediction. */
    @Query("SELECT COUNT(p) FROM PredictionRecord p WHERE p.settled = true")
    long countSettled();

    @Query("SELECT COUNT(p) FROM PredictionRecord p WHERE p.settled = true AND p.wasCorrect = true")
    long countCorrect();
}

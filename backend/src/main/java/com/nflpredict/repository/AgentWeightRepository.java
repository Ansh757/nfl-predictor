package com.nflpredict.repository;

import com.nflpredict.model.AgentWeight;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface AgentWeightRepository extends JpaRepository<AgentWeight, String> {

    List<AgentWeight> findByCalibrated(Boolean calibrated);
}

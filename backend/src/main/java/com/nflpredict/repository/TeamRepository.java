package com.nflpredict.repository;

import com.nflpredict.model.Team;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface TeamRepository extends JpaRepository<Team, Long> {

    // Find team by abbreviation (e.g., "KC", "BUF")
    Optional<Team> findByAbbreviation(String abbreviation);

    // Find teams by conference
    List<Team> findByConference(String conference);

    // Find teams by division
    List<Team> findByConferenceAndDivision(String conference, String division);

    // Custom query to find teams by city or name
    @Query("SELECT t FROM Team t WHERE t.city LIKE %:search% OR t.name LIKE %:search%")
    List<Team> findBySearch(String search);
}
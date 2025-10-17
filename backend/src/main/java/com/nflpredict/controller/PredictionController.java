package com.nflpredict.controller;

import com.nflpredict.service.AgentService;
import com.nflpredict.model.Team;
import com.nflpredict.repository.TeamRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/predictions")
@CrossOrigin(origins = "*")
public class PredictionController {

    @Autowired
    private AgentService agentService;

    @Autowired
    private TeamRepository teamRepository;

    @PostMapping("/teams/{homeTeamId}/vs/{awayTeamId}")
    public ResponseEntity<Map<String, Object>> predictGame(@PathVariable Long homeTeamId,
            @PathVariable Long awayTeamId) {

        // Get team names from database
        Optional<Team> homeTeam = teamRepository.findById(homeTeamId);
        Optional<Team> awayTeam = teamRepository.findById(awayTeamId);

        if (homeTeam.isEmpty() || awayTeam.isEmpty()) {
            return ResponseEntity.notFound().build();
        }

        // Call AI agents for prediction
        Map<String, Object> prediction = agentService.getPrediction(1L, // gameId (we'll enhance
                                                                        // this later)
                homeTeam.get().getName(), awayTeam.get().getName());

        return ResponseEntity.ok(prediction);
    }

    @GetMapping("/test")
    public ResponseEntity<Map<String, Object>> testPrediction() {
        // Quick test endpoint
        Map<String, Object> prediction = agentService.getPrediction(1L, "Chiefs", "Bills");
        return ResponseEntity.ok(prediction);
    }
}

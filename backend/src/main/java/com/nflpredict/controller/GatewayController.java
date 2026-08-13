package com.nflpredict.controller;

import com.nflpredict.dto.ConsensusResult;
import com.nflpredict.service.ConsensusService;
import com.nflpredict.service.PredictionOrchestrator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Gateway endpoints: the orchestrated, weighted-vote view of the agents.
 *
 * <p>Distinct from AgentProxyController, which forwards requests to the Python
 * service untouched. These endpoints apply the consensus here.
 */
@RestController
@RequestMapping("/api/gateway")
@CrossOrigin(origins = "*")
public class GatewayController {

    private final PredictionOrchestrator orchestrator;
    private final ConsensusService consensusService;

    public GatewayController(PredictionOrchestrator orchestrator, ConsensusService consensusService) {
        this.orchestrator = orchestrator;
        this.consensusService = consensusService;
    }

    /**
     * Predict every game in a week, fanned out concurrently.
     *
     * <p>Season defaults to the agent service's current year; pass it
     * explicitly to predict a past season.
     */
    @GetMapping("/predictions/week/{week}")
    public ResponseEntity<Map<String, Object>> predictWeek(
            @PathVariable int week,
            @RequestParam(required = false) Integer season) {
        List<ConsensusResult> results = orchestrator.predictWeek(week, season);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("week", week);
        body.put("season", season);
        body.put("count", results.size());
        body.put("predictions", results);
        return ResponseEntity.ok(body);
    }

    /** Predict a single matchup. */
    @GetMapping("/predictions/game/{gameId}")
    public ResponseEntity<ConsensusResult> predictGame(
            @PathVariable Long gameId,
            @RequestParam String homeTeam,
            @RequestParam String awayTeam) {
        ConsensusResult result = orchestrator.predictGame(gameId, homeTeam, awayTeam, null);
        return result == null ? ResponseEntity.status(503).build() : ResponseEntity.ok(result);
    }

    /** Record a finished game's winner so live accuracy can be tracked. */
    @PostMapping("/predictions/{gameId}/settle")
    public ResponseEntity<Map<String, Object>> settle(
            @PathVariable Long gameId,
            @RequestParam String actualWinner) {
        boolean settled = orchestrator.settle(gameId, actualWinner);
        return settled
                ? ResponseEntity.ok(Map.of("gameId", gameId, "settled", true))
                : ResponseEntity.notFound().build();
    }

    /** Accuracy across every settled prediction this gateway has served. */
    @GetMapping("/accuracy")
    public ResponseEntity<Map<String, Object>> accuracy() {
        return ResponseEntity.ok(orchestrator.liveAccuracy());
    }

    /** The weights currently driving the vote. */
    @GetMapping("/weights")
    public ResponseEntity<Map<String, Double>> weights() {
        return ResponseEntity.ok(consensusService.getWeights());
    }

    /** Drop the cached weights after recalibration. */
    @PostMapping("/weights/refresh")
    public ResponseEntity<Map<String, String>> refreshWeights() {
        consensusService.invalidateWeights();
        return ResponseEntity.ok(Map.of("status", "weights cache cleared"));
    }
}

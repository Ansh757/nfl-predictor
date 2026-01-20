package com.nflpredict.controller;

import com.nflpredict.dto.GamesWeekResponse;
import com.nflpredict.dto.PredictionRequest;
import com.nflpredict.dto.PredictionResponse;
import com.nflpredict.service.AgentGatewayService;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@CrossOrigin(origins = "*")
public class AgentProxyController {

    private final AgentGatewayService agentGatewayService;

    public AgentProxyController(AgentGatewayService agentGatewayService) {
        this.agentGatewayService = agentGatewayService;
    }

    @GetMapping("/games/week/{week}")
    public GamesWeekResponse getGamesByWeek(@PathVariable int week) {
        return agentGatewayService.getGamesByWeek(week);
    }

    @PostMapping("/predict")
    public PredictionResponse predict(@RequestBody PredictionRequest request) {
        return agentGatewayService.getPrediction(request);
    }
}

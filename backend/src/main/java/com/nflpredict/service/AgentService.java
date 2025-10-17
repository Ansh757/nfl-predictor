package com.nflpredict.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.HashMap;
import java.util.List;
import java.util.logging.Logger;

@Service
public class AgentService {

    private static final Logger logger = Logger.getLogger(AgentService.class.getName());

    private final WebClient webClient;
    private final int timeout;
    private final int maxRetries;

    public AgentService(
            @Value("${agent.service.url:http://agent-service:8001}") String agentServiceUrl,
            @Value("${agent.service.timeout:30000}") int timeout,
            @Value("${agent.service.retry.max-attempts:3}") int maxRetries) {
        this.timeout = timeout;
        this.maxRetries = maxRetries;
        this.webClient = WebClient.builder().baseUrl(agentServiceUrl).build();

        logger.info("AgentService initialized with URL: " + agentServiceUrl);
    }
    @SuppressWarnings("unchecked")
    public Map<String, Object> getPrediction(Long gameId, String homeTeam, String awayTeam) {
        try {
            // Create the request payload that matches Python API expectations
            Map<String, Object> gameData = createGameData(gameId, homeTeam, awayTeam);
            Map<String, Object> request = createPredictionRequest(gameData);

            logger.info("Calling agent service for prediction: " + homeTeam + " vs " + awayTeam);

            // Make the HTTP call with proper error handling
            Map<String, Object> response = webClient.post().uri("/predict").bodyValue(request)
                    .retrieve().bodyToMono(Map.class).timeout(Duration.ofMillis(timeout))
                    .retryWhen(Retry.fixedDelay(maxRetries, Duration.ofSeconds(1))).block();

            logger.info("Received prediction from agent service");
            return response;

        } catch (WebClientResponseException e) {
            logger.warning("Agent service HTTP error: " + e.getStatusCode() + " - "
                    + e.getResponseBodyAsString());
            return createFallbackPrediction(homeTeam, awayTeam, "Agent service HTTP error: "
                    + e.getStatusCode() + " - " + e.getResponseBodyAsString());

        } catch (Exception e) {
            logger.warning("Agent service error: " + e.getMessage());
            return createFallbackPrediction(homeTeam, awayTeam,
                    "Agent service error: " + e.getMessage());
        }
    }

    private Map<String, Object> createGameData(Long gameId, String homeTeam, String awayTeam) {
        Map<String, Object> gameData = new HashMap<>();
        gameData.put("game_id", gameId.intValue());
        gameData.put("home_team_name", homeTeam);
        gameData.put("away_team_name", awayTeam);
        gameData.put("game_time", LocalDateTime.now().toString());
        gameData.put("venue", homeTeam + " Stadium");
        gameData.put("is_dome", false);
        return gameData;
    }

    private Map<String, Object> createPredictionRequest(Map<String, Object> gameData) {
        Map<String, Object> request = new HashMap<>();
        request.put("game_data", gameData);
        request.put("include_reasoning", true);
        request.put("confidence_threshold", 0.0);
        return request;
    }

    private Map<String, Object> createFallbackPrediction(String homeTeam, String awayTeam,
            String error) {
        Map<String, Object> fallback = new HashMap<>();
        fallback.put("overall_winner", homeTeam);
        fallback.put("overall_confidence", 0.5);
        fallback.put("consensus_reasoning",
                "Agent service unavailable - using fallback prediction");
        fallback.put("error", error);
        fallback.put("prediction_time", LocalDateTime.now().toString());
        return fallback;
    }

    public Map<String, Object> getAgentStatus() {
        try {
            logger.info("Checking agent service status");

            List<Map<String, Object>> response = webClient.get().uri("/agents/status").retrieve()
                    .bodyToMono(List.class).timeout(Duration.ofMillis(5000)).block();

            Map<String, Object> result = new HashMap<>();
            result.put("status", "healthy");
            result.put("agents", response);
            return result;

        } catch (Exception e) {
            logger.warning("Agent status check failed: " + e.getMessage());
            Map<String, Object> result = new HashMap<>();
            result.put("status", "unhealthy");
            result.put("error", e.getMessage());
            return result;
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getHealth() {
        try {
            Map<String, Object> response = webClient.get().uri("/health").retrieve()
                    .bodyToMono(Map.class).timeout(Duration.ofMillis(5000)).block();

            return response;

        } catch (Exception e) {
            Map<String, Object> result = new HashMap<>();
            result.put("status", "unhealthy");
            result.put("error", e.getMessage());
            return result;
        }
    }
}

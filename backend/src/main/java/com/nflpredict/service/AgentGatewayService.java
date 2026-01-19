package com.nflpredict.service;

import com.nflpredict.dto.GamesWeekResponse;
import com.nflpredict.dto.PredictionRequest;
import com.nflpredict.dto.PredictionResponse;
import java.time.Duration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

@Service
public class AgentGatewayService {

    private final WebClient webClient;
    private final Duration timeout;
    private final int maxRetries;
    private final Duration retryDelay;
    private final String predictEndpoint;

    public AgentGatewayService(
            @Value("${agent.service.url:http://agent-service:8001}") String agentServiceUrl,
            @Value("${agent.service.timeout:30000}") int timeoutMillis,
            @Value("${agent.service.retry.max-attempts:3}") int maxRetries,
            @Value("${agent.service.retry.delay:1000}") long retryDelayMillis,
            @Value("${agent.service.endpoints.predict:/predict}") String predictEndpoint) {
        this.webClient = WebClient.builder().baseUrl(agentServiceUrl).build();
        this.timeout = Duration.ofMillis(timeoutMillis);
        this.maxRetries = maxRetries;
        this.retryDelay = Duration.ofMillis(retryDelayMillis);
        this.predictEndpoint = predictEndpoint;
    }

    public GamesWeekResponse getGamesByWeek(int week) {
        Mono<GamesWeekResponse> request = webClient.get()
                .uri("/games/week/{week}", week)
                .retrieve()
                .bodyToMono(GamesWeekResponse.class);

        return applyTimeoutAndRetry(request).block();
    }

    public PredictionResponse getPrediction(PredictionRequest predictionRequest) {
        Mono<PredictionResponse> request = webClient.post()
                .uri(predictEndpoint)
                .bodyValue(predictionRequest)
                .retrieve()
                .bodyToMono(PredictionResponse.class);

        return applyTimeoutAndRetry(request).block();
    }

    private <T> Mono<T> applyTimeoutAndRetry(Mono<T> request) {
        return request
                .timeout(timeout)
                .retryWhen(Retry.fixedDelay(maxRetries, retryDelay));
    }
}

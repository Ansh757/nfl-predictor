package com.nflpredict.config;

import java.util.concurrent.Executor;
import java.util.concurrent.ThreadPoolExecutor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

/**
 * Thread pool for fanning out across a week's games.
 *
 * <p>These tasks are almost entirely blocked on the agent service, so the pool
 * is sized well above the core count. On Java 21 this whole bean can be
 * replaced with {@code Executors.newVirtualThreadPerTaskExecutor()} and the
 * sizing stops mattering - the project targets Java 17 for now so that the
 * build works on the JDKs already installed.
 */
@Configuration
@EnableAsync
@EnableScheduling
public class AsyncConfig {

    @Bean(name = "fanOutExecutor")
    public Executor fanOutExecutor(
            @Value("${prediction.fanout.core-pool-size:8}") int corePoolSize,
            @Value("${prediction.fanout.max-pool-size:16}") int maxPoolSize,
            @Value("${prediction.fanout.queue-capacity:64}") int queueCapacity) {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(corePoolSize);
        executor.setMaxPoolSize(maxPoolSize);
        executor.setQueueCapacity(queueCapacity);
        executor.setThreadNamePrefix("fanout-");
        // Run on the caller's thread rather than dropping work when saturated
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();
        return executor;
    }
}

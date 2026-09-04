package com.nflpredict.config;

import com.nflpredict.model.AgentWeight;
import com.nflpredict.repository.AgentWeightRepository;
import java.util.List;
import java.util.logging.Logger;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Seeds the agent weights measured by the Python backtest harness.
 *
 * <p>Values come from a walk-forward backtest over the 2021-2024 seasons (market
 * weights use free historical closing lines from nflverse); a
 * weight is the agent's accuracy minus 0.5, floored at zero. Only inserted when
 * the table is empty, so recalibrated weights written at runtime survive a
 * restart.
 */
@Configuration
public class AgentWeightSeeder {

    private static final Logger logger = Logger.getLogger(AgentWeightSeeder.class.getName());

    @Bean
    public CommandLineRunner seedAgentWeights(AgentWeightRepository repository) {
        return args -> {
            if (repository.count() > 0) {
                return;
            }

            List<AgentWeight> seeds = List.of(
                    // Re-derived after the neutral-site correction to historical
                    // Elo. Must stay in step with agents/consensus.py.
                    new AgentWeight("Market Odds", 0.164, 0.664, "2021-2024", true),
                    new AgentWeight("Basic Predictor", 0.111, 0.612, "2021-2024", true),
                    new AgentWeight("Elo Ratings", 0.116, 0.616, "2021-2024", true),
                    new AgentWeight("Rest & Travel", 0.021, 0.521, "2021-2024", true),
                    // Weather Impact (51.1%) and News Sentiment (49.7%) were retired from
                    // the ensemble: both measured at coin-flip level, and removing them
                    // made the ensemble marginally better.
                    // Measured at last. ESPN has no historical injury archive,
                    // which is why this sat at the default weight - but nflverse
                    // publishes the official weekly reports, the same route that
                    // calibrated Market Odds. 55.5% over 2021-2024, z = 3.6 on
                    // 1,088 games, 57.4% on the held-out 2025 season.
                    new AgentWeight("Injury Impact", 0.055, 0.555, "2021-2024", true));

            repository.saveAll(seeds);
            logger.info("Seeded " + seeds.size() + " agent weights");
        };
    }
}

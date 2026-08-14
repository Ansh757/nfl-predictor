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
                    new AgentWeight("Market Odds", 0.164, 0.664, "2021-2024", true),
                    new AgentWeight("Basic Predictor", 0.121, 0.621, "2021-2024", true),
                    new AgentWeight("Elo Ratings", 0.115, 0.615, "2021-2024", true),
                    new AgentWeight("Rest & Travel", 0.022, 0.522, "2021-2024", true),
                    new AgentWeight("Weather Impact", 0.011, 0.511, "2021-2024", true),
                    new AgentWeight("News Sentiment", 0.0, 0.497, "2021-2024", true),
                    // Still not backtestable: ESPN publishes no historical injury
                    // archive. Held at the default weight until a season of settled
                    // live predictions can calibrate it.
                    new AgentWeight("Injury Impact", 0.02, null, null, false));

            repository.saveAll(seeds);
            logger.info("Seeded " + seeds.size() + " agent weights");
        };
    }
}

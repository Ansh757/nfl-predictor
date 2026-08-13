package com.nflpredict.config;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cache.concurrent.ConcurrentMapCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.StringRedisSerializer;

/**
 * Redis-backed caching for predictions and agent weights.
 *
 * <p>Predictions expire quickly because agent output drifts as injury reports
 * and betting lines move. Agent weights are effectively static between
 * recalibrations, so they get a long TTL.
 *
 * <p>Falls back to an in-memory cache when Redis is switched off, so the
 * service still runs locally without a Redis container.
 */
@Configuration
@EnableCaching
public class CacheConfig {

    @Bean
    @ConditionalOnProperty(name = "spring.cache.type", havingValue = "redis", matchIfMissing = true)
    public CacheManager redisCacheManager(
            RedisConnectionFactory connectionFactory,
            @Value("${prediction.cache.game-ttl-minutes:30}") int gameTtlMinutes,
            @Value("${prediction.cache.weight-ttl-hours:24}") int weightTtlHours) {

        ObjectMapper mapper = new ObjectMapper();
        mapper.registerModule(new JavaTimeModule());
        mapper.setVisibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.ANY);
        mapper.activateDefaultTyping(
                mapper.getPolymorphicTypeValidator(),
                ObjectMapper.DefaultTyping.NON_FINAL);

        RedisCacheConfiguration base = RedisCacheConfiguration.defaultCacheConfig()
                .serializeKeysWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(new GenericJackson2JsonRedisSerializer(mapper)))
                .disableCachingNullValues();

        Map<String, RedisCacheConfiguration> caches = new HashMap<>();
        caches.put("gamePredictions", base.entryTtl(Duration.ofMinutes(gameTtlMinutes)));
        caches.put("agentWeights", base.entryTtl(Duration.ofHours(weightTtlHours)));

        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(base.entryTtl(Duration.ofMinutes(gameTtlMinutes)))
                .withInitialCacheConfigurations(caches)
                .build();
    }

    @Bean
    @ConditionalOnProperty(name = "spring.cache.type", havingValue = "simple")
    public CacheManager simpleCacheManager() {
        return new ConcurrentMapCacheManager("gamePredictions", "agentWeights");
    }
}

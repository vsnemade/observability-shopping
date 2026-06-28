package com.shop.common;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;
import java.util.List;

/**
 * Auto-configuration that every service inherits simply by depending on the {@code common} module.
 *
 * <p>It contributes:
 * <ul>
 *   <li>the {@link CorrelationIdFilter} (picked up via component scan of this package below), and</li>
 *   <li>a {@link RestTemplate} pre-wired with {@link CorrelationIdRestInterceptor} and sane timeouts.</li>
 * </ul>
 *
 * <p>Registered through {@code META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports}
 * so it activates without the services having to component-scan {@code com.shop.common}.
 */
@AutoConfiguration
public class ObservabilityAutoConfiguration {

    @Bean
    public CorrelationIdFilter correlationIdFilter() {
        return new CorrelationIdFilter();
    }

    @Bean
    public RestTemplate restTemplate(RestTemplateBuilder builder) {
        return builder
                .setConnectTimeout(Duration.ofSeconds(2))
                .setReadTimeout(Duration.ofSeconds(5))
                .additionalInterceptors(List.of(new CorrelationIdRestInterceptor()))
                .build();
    }
}

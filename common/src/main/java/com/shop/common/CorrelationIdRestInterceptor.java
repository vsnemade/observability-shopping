package com.shop.common;

import org.slf4j.MDC;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.util.StringUtils;

import java.io.IOException;

/**
 * Copies the current correlation id from the MDC onto every outbound HTTP call so the same id flows
 * through the whole call chain (gateway → order → product/payment).
 *
 * <p>Trace-context (traceparent header) is propagated automatically by the OpenTelemetry agent;
 * this interceptor only handles our extra business correlation id.
 */
public class CorrelationIdRestInterceptor implements ClientHttpRequestInterceptor {

    @Override
    public ClientHttpResponse intercept(HttpRequest request,
                                        byte[] body,
                                        ClientHttpRequestExecution execution) throws IOException {
        String correlationId = MDC.get(CorrelationId.MDC_KEY);
        if (StringUtils.hasText(correlationId) && !request.getHeaders().containsKey(CorrelationId.HEADER)) {
            request.getHeaders().add(CorrelationId.HEADER, correlationId);
        }
        return execution.execute(request, body);
    }
}

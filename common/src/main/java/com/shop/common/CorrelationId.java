package com.shop.common;

/**
 * Constants for correlation-id propagation.
 *
 * <p>Note on the three identifiers you will see in logs/traces:
 * <ul>
 *   <li><b>traceId</b> / <b>spanId</b> — injected automatically into the SLF4J MDC by the
 *       OpenTelemetry Java agent (keys {@code trace_id} / {@code span_id}). They identify the
 *       distributed trace and the individual unit of work within it.</li>
 *   <li><b>correlationId</b> — a business/request id that <i>we</i> manage in
 *       {@link CorrelationIdFilter} and forward downstream via the
 *       {@value #HEADER} header. Useful when you want a human-friendly id that survives even
 *       across systems that do not speak W3C trace-context.</li>
 * </ul>
 */
public final class CorrelationId {

    private CorrelationId() {
    }

    /** HTTP header used to carry the correlation id between services. */
    public static final String HEADER = "X-Correlation-ID";

    /** MDC key under which the correlation id is stored for logging. */
    public static final String MDC_KEY = "correlationId";
}

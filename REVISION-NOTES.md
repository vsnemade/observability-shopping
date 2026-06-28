# Observability Revision Notes

Quick-reference for the concepts practiced in this lab. Read top to bottom for a full
revision pass, or jump to a section.

---

## 1. The three pillars — what goes where

| Pillar | Produced by | Shipped via | Stored in | Viewed in |
|---|---|---|---|---|
| **Metrics** | Micrometer (Spring Boot Actuator) | Prometheus **scrapes** `/actuator/prometheus` (pull model) | Prometheus | Prometheus UI, Grafana dashboards |
| **Traces** | OpenTelemetry Java agent (auto-instrumentation) | App **pushes** OTLP/gRPC to Collector (push model) | Tempo *and* Jaeger (same data, two backends) | Jaeger UI, Grafana Explore → Tempo |
| **Logs** | SLF4J/Logback + OTel logback appender | App **pushes** OTLP to Collector → Collector pushes to Loki | Loki | Grafana Explore → Loki |

**Key asymmetry to remember**: metrics are *pulled* (Prometheus scrapes us), traces/logs are *pushed*
(we send to the Collector). That's why Prometheus has a `scrape_configs` list of targets, while traces
and logs flow through `OTEL_EXPORTER_OTLP_ENDPOINT`.

---

## 2. The three identifiers

| Id | Who generates it | Where it lives | Purpose |
|---|---|---|---|
| **traceId** | OTel Java agent, on the first request into the system | W3C `traceparent` HTTP header + SLF4J MDC key `trace_id` | Identifies the *entire* end-to-end request across all services |
| **spanId** | OTel Java agent, one per unit of work (each HTTP handler, each outbound call) | Same `traceparent` header (current span); MDC key `span_id` | Identifies *one hop* — the tree of spans under one traceId is the trace |
| **correlationId** | **Us** — [`CorrelationIdFilter`](common/src/main/java/com/shop/common/CorrelationIdFilter.java) | `X-Correlation-ID` HTTP header + MDC key `correlationId` | A business-level id we fully control; useful for systems that don't speak trace-context, or for a human-friendly id to hand to a customer/support ticket |

**Propagation mechanics:**
- `traceId`/`spanId`: the OTel agent **automatically** instruments `RestTemplate` and Spring MVC — it
  injects/reads `traceparent` on every hop. We wrote zero code for this.
- `correlationId`: **we** wrote the propagation. [`CorrelationIdFilter`](common/src/main/java/com/shop/common/CorrelationIdFilter.java)
  reads/mints it on the way in; [`CorrelationIdRestInterceptor`](common/src/main/java/com/shop/common/CorrelationIdRestInterceptor.java)
  copies it from MDC onto every outbound `RestTemplate` call on the way out.

Both end up in the MDC, so [`logback-spring.xml`](common/src/main/resources/logback-spring.xml) can
print all three on every line:
```
%d{HH:mm:ss.SSS} %-5level [${appName}] [trace=%X{trace_id} span=%X{span_id} corr=%X{correlationId}] %logger - %msg
```

---

## 3. Metrics — Micrometer → Prometheus → Grafana

**How it's wired:**
1. `spring-boot-starter-actuator` + `micrometer-registry-prometheus` (in [common/pom.xml](common/pom.xml)) auto-expose `/actuator/prometheus`.
2. Auto-generated metric: **`http_server_requests_seconds`** — a histogram per `(service, uri, method, status)`. This is the RED-method (Rate/Errors/Duration) backbone.
3. Custom business counters, written by hand with `MeterRegistry`:
   - `shop_order_created_total`, `shop_order_failed_total` ([OrderController.java](services/order-service/src/main/java/com/shop/order/OrderController.java))
   - `shop_payment_result_total{status=approved|declined}` ([PaymentController.java](services/payment-service/src/main/java/com/shop/payment/PaymentController.java))
   - `shop_product_reserved_total`, `shop_product_reserve_failures_total` ([ProductController.java](services/product-service/src/main/java/com/shop/product/ProductController.java))
4. [k8s/observability/prometheus.yaml](k8s/observability/prometheus.yaml) lists all 4 services as static scrape targets, `scrape_interval: 10s`.
5. Percentile histogram buckets enabled in each `application.yml`:
   ```yaml
   management.metrics.distribution.percentiles-histogram.http.server.requests: true
   ```
   This is what makes `histogram_quantile()` queries possible.

**Where to look:** Prometheus UI `http://localhost:9090` → Graph tab. Or Grafana → Dashboards → Shop → "Shop API Metrics (RED)".

**PromQL cheat-sheet:**
```promql
# Request rate per service
sum by (service) (rate(http_server_requests_seconds_count[1m]))

# p95 latency per service
histogram_quantile(0.95, sum by (le, service) (rate(http_server_requests_seconds_bucket[5m])))

# Error rate (4xx/5xx)
sum by (service) (rate(http_server_requests_seconds_count{status=~"4..|5.."}[1m]))

# Business metric: orders/min
rate(shop_order_created_total[1m]) * 60

# Top endpoints by traffic
topk(10, sum by (service, uri, method) (rate(http_server_requests_seconds_count[1m])))
```

---

## 4. Traces — OTel agent → Collector → Tempo + Jaeger

**How it's wired:**
1. Every image bakes in the **OpenTelemetry Java agent** via `-javaagent:/app/opentelemetry-javaagent.jar` ([Dockerfile](Dockerfile)). Zero code changes — it instruments Spring MVC, `RestTemplate`, JDBC, logback, etc. at class-load time.
2. Each Deployment sets agent config via env vars ([k8s/services/*.yaml](k8s/services)):
   ```yaml
   OTEL_SERVICE_NAME: order-service
   OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
   OTEL_EXPORTER_OTLP_PROTOCOL: grpc
   OTEL_TRACES_EXPORTER: otlp
   OTEL_METRICS_EXPORTER: none   # we use Micrometer/Prometheus for metrics, not the agent
   OTEL_PROPAGATORS: tracecontext,baggage
   ```
3. The **OTel Collector** ([otel-collector.yaml](k8s/observability/otel-collector.yaml)) receives OTLP on `:4317`/`:4318` and fans traces out to **two** exporters: `otlp/tempo` and `otlp/jaeger`. That's why the same trace appears in both UIs.
4. **Tempo** ([tempo.yaml](k8s/observability/tempo.yaml)) stores traces on local disk and also runs a `metrics_generator` (service-graph + span-metrics) — this is what powers Grafana's service map.
5. **Jaeger** ([jaeger.yaml](k8s/observability/jaeger.yaml)) is all-in-one, in-memory, OTLP ingestion enabled via `COLLECTOR_OTLP_ENABLED=true`.

**The trace shape in this lab:**
```
gateway-service  POST /api/checkout
  └─ order-service  POST /orders
       ├─ product-service  GET  /products/{id}      (price lookup)
       ├─ product-service  POST /products/{id}/reserve
       └─ payment-service  POST /payments            (~8% simulated decline)
```

**Where to look:**
- Jaeger UI `http://localhost:16686` → pick service `gateway-service` → Find Traces → click one → see the span waterfall.
- Grafana → Explore → datasource **Tempo** → search by service/trace ID, or use **TraceQL**:
  ```
  { resource.service.name = "payment-service" && status = error }
  ```
- Grafana → Explore → Tempo → **Service Graph** tab → visual call topology generated from spans.

---

## 5. Logs — OTel agent → Collector → Loki

**How it's wired:**
1. The same OTel Java agent has a **logback appender** that intercepts every log event, attaches `trace_id`/`span_id`/MDC attributes as structured metadata, and ships it via OTLP — no separate logging library needed.
   ```yaml
   OTEL_LOGS_EXPORTER: otlp
   OTEL_INSTRUMENTATION_LOGBACK_APPENDER_EXPERIMENTAL_CAPTURE_MDC_ATTRIBUTES: "*"
   ```
2. Collector receives logs on the same OTLP endpoint and exports to **Loki** via `otlphttp/loki` → `http://loki:3100/otlp` ([otel-collector.yaml](k8s/observability/otel-collector.yaml)).
3. **Loki** ([loki.yaml](k8s/observability/loki.yaml)) has `allow_structured_metadata: true` so fields like `trace_id`, `service_name`, `severity_text` become queryable labels without manual parsing.

**Where to look:** Grafana → Explore → datasource **Loki**.

**LogQL cheat-sheet:**
```logql
# One service
{service_name="order-service"}

# All services
{service_name=~".+"}

# Text filter
{service_name="payment-service"} |= "DECLINED"

# By severity
{service_name=~".+"} | severity_text="WARN"

# Every service's logs for ONE request (the "aha" moment of correlation)
{service_name=~".+"} | trace_id="<paste-trace-id>"

# By our own business id
{service_name=~".+"} | correlationId="<paste-correlation-id>"
```
> No `| json` needed — these are plain-text log lines; `trace_id`/`correlationId` are already
> structured metadata, not embedded JSON.

**Raw alternative (no aggregation, no correlation):**
```powershell
kubectl -n shop logs deploy/order-service -f
```

---

## 6. The correlation workflow (why all this is worth it)

This is the payoff of wiring traces+logs+metrics through one pipeline instead of three silos:

- **Trace → logs**: Tempo span → click **"Logs for this span"** → Grafana auto-runs a Loki query
  filtered by that span's `trace_id`. You instantly see every service's log lines for that one request.
- **Logs → trace**: any Loki log line → expand → click **"View trace"** (a *derived field*, configured
  in [grafana.yaml](k8s/observability/grafana.yaml) under `Loki.jsonData.derivedFields`) → jumps to that trace in Tempo.
- **Trace → metrics (exemplars)**: Prometheus has `exemplarTraceIdDestinations` configured, so a single
  slow request on a latency graph can link to its exact trace.
- **Metrics → traces (service graph)**: Tempo's `metrics_generator` derives RED metrics + a service
  topology graph purely from span data — no separate instrumentation.

All of this cross-linking is configured once, declaratively, in
[k8s/observability/grafana.yaml](k8s/observability/grafana.yaml) (`datasources.yaml` ConfigMap) — that
file is worth re-reading slowly, it's the glue.

---

## 7. Tempo vs Jaeger (why both are in this lab)

| | Jaeger | Tempo |
|---|---|---|
| Needs an index to search | Yes (Elasticsearch/Cassandra in prod) | No — finds traces by ID or via exemplars/derived fields |
| Has its own UI | Yes, dedicated (`:16686`) | No — viewed through Grafana Explore |
| Cross-pillar correlation | Not natively | Built-in (logs/metrics pivoting, service graph) |
| Enterprise usage today | Mature, CNCF-graduated, long track record (Uber-born); common where teams have Elasticsearch/Jaeger already, or want a standalone tracing tool | Fast-growing with the "LGTM stack" (Loki+Grafana+Tempo+Mimir) trend; cheap to run (object storage, no index cluster) |

In this lab, the Collector fans the **same trace data to both** purely so you can compare the two UIs
side by side. In a real deployment you'd pick one (Tempo if Grafana is your single pane of glass;
Jaeger if you want a dedicated, vendor-independent tracing tool) — or send OTLP to a commercial APM
backend (Datadog, Honeycomb, Dynatrace, Grafana Cloud) instead of self-hosting either.

---

## 8. One-page mental model

```
                    ┌─────────────────────────────────────────┐
 customer ──HTTP──▶ │ gateway → order → product (×2), payment  │   4 Spring Boot services
                    └─────────────────────────────────────────┘
                       │              │                │
                metrics│        traces│            logs│
              (pulled) │        (pushed, OTLP)   (pushed, OTLP)
                       │              │                │
                       ▼              ▼                ▼
                 ┌──────────┐  ┌──────────────┐
                 │Prometheus│  │ OTel Collector│
                 └────┬─────┘  └──┬────────┬──┘
                      │       traces│       │logs
                      │           ┌─┴──┐  ┌─▼──┐
                      │           │Tempo│ │Loki│
                      │           └─┬──┘  └─┬──┘
                      │         ┌───┘       │
                      │         ▼           │
                      │      Jaeger         │
                      │  (separate fan-out) │
                      ▼         ▼           ▼
                 ┌─────────────────────────────┐
                 │           Grafana            │   <- single pane of glass,
                 │  (datasources cross-linked)  │      all pivoting happens here
                 └─────────────────────────────┘
```

**Remember the rule of thumb:** *metrics tell you something is wrong, traces tell you where, logs tell
you why.* Practice the flow in that order: dashboard spike → drill into a trace → pivot to logs for the
root cause.

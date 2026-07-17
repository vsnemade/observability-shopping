# Shopping Platform — Observability Hands-On Lab

A complete, runnable lab for practicing the **three pillars of observability** — metrics, traces, and
logs — plus request **correlation** across services, topped with a hand-built **AIOps** layer. Four
Spring Boot microservices for a shopping platform run on a local **KIND** Kubernetes cluster and emit
telemetry through **OpenTelemetry** into **Prometheus, Grafana, Jaeger, Tempo, and Loki**. A fifth
service, **aiops-service**, watches that telemetry, detects anomalies, correlates them into incidents,
and produces an LLM-generated root-cause report — with a React dashboard to view it all.

---

## What you'll practice

| Concept | Where it shows up |
|---|---|
| **traceId** | One id per end-to-end request, spanning all 4 services. Injected into logs by the OTel agent; viewable in Jaeger/Tempo. |
| **spanId** | One per unit of work (each HTTP server handler + each outbound call). The tree of spans = the trace. |
| **correlationId** | A business id *we* manage (`X-Correlation-ID` header + MDC), propagated downstream and logged on every line. |
| **API metrics** | `http.server.requests` (rate / latency p95 / errors) from Micrometer, plus custom counters like `shop.order.created`. |
| **Log aggregation** | App logs → OTel agent → OTel Collector → Loki, queryable in Grafana and linkable to traces. |
| **AIOps** | `aiops-service` polls Prometheus/Loki/Tempo, detects anomalies (z-score, log-pattern, TraceQL), correlates them into incidents, and generates a root-cause report — view it at http://localhost:8090. |

---

## Architecture

```
                       ┌──────────────────────────────────────────────────────────┐
  customer ──HTTP──▶   │  gateway-service (8080)                                   │
                       │     └─▶ order-service (8081)                              │
                       │            ├─▶ product-service (8082)  GET /products/{id} │
                       │            ├─▶ product-service (8082)  POST .../reserve   │
                       │            └─▶ payment-service (8083)  POST /payments     │
                       └──────────────────────────────────────────────────────────┘
                                   │ traces (OTLP)      │ logs (OTLP)     │ metrics (scrape)
                                   ▼                    ▼                 ▼
                          ┌──────────────────┐   ┌───────────┐   /actuator/prometheus
                          │  OTel Collector  │   │           │           │
                          └───────┬─────┬────┘   └───────────┘           ▼
                          traces  │     │ logs                     ┌────────────┐
                            ┌─────┘     └─────┐                    │ Prometheus │
                            ▼                 ▼                    └─────┬──────┘
                      ┌─────────┐  ┌──────┐  ┌──────┐                    │
                      │  Tempo  │  │Jaeger│  │ Loki │ ◀──────────────────┘
                      └────┬────┘  └──┬───┘  └──┬───┘   (all visualized in)
                           └──────────┴─────────┴──────────▶  ┌──────────┐
                                                              │ Grafana  │◀──┐
                                                              └──────────┘   │ annotations
                           ┌─────────────────────────────────────────────────┘
                           │  polls every 30s
                 ┌─────────┴─────────┐
                 │   aiops-service   │  detectors → correlation engine → incidents
                 │ (FastAPI + React) │  → Grafana annotation, remediation, Claude RCA
                 └───────────────────┘  UI: http://localhost:8090
```

**Telemetry routing (deliberate, so each pillar is learnable on its own):**
- **Traces**: OTel Java agent → Collector → **Tempo** *and* **Jaeger** (same traces in both, so you can compare UIs).
- **Logs**: OTel Java agent (logback appender) → Collector → **Loki**.
- **Metrics**: Micrometer `/actuator/prometheus` ← scraped by **Prometheus** (the agent's metric export is turned off on purpose).

---

## Prerequisites

- Docker Desktop
- [`kind`](https://kind.sigs.k8s.io/) and `kubectl` on your `PATH`
- (For local non-Docker builds only) JDK 17 + Maven — not required if you build images via Docker

No local Maven/JDK is needed: the `Dockerfile` builds everything inside a Maven container.

---

## Quickstart

From PowerShell, in the repo root:

```powershell
# 1. Build the four service images (multi-stage Docker build, no local JDK needed)
./scripts/build-images.ps1

# 2. Create the KIND cluster, load images, deploy the stack, wait for readiness
./scripts/deploy.ps1

# 3. Open all the UIs (runs port-forwards as background jobs)
./scripts/port-forward.ps1

# 4. Generate traffic (checkouts + catalog browsing)
./scripts/generate-traffic.ps1 -Iterations 300
```

Then open:

| UI | URL | Try this |
|---|---|---|
| **Grafana** | http://localhost:3000 | Explore → Tempo / Loki / Prometheus. Anonymous admin access. |
| **Prometheus** | http://localhost:9090 | Query `rate(http_server_requests_seconds_count[1m])` |
| **Jaeger** | http://localhost:16686 | Service = `gateway-service`, Find Traces |
| **Gateway** | http://localhost:8080/api/products | Hit the API directly |
| **AIOps** | http://localhost:8090 | Incident list, findings feed, RCA reports, suggested actions |

Tear down with `./scripts/teardown.ps1` (add `-KeepCluster` to only delete the `shop` namespace).

---

## The guided tour (do these in order)

### 1. Metrics — the RED method
Open Grafana → **Dashboards → Shop → "Shop API Metrics (RED)"**. You'll see request **R**ate,
**E**rrors, and **D**uration per service, plus business metrics (orders created/failed, payments
approved/declined). In Prometheus, try:
```promql
histogram_quantile(0.95, sum by (le, service) (rate(http_server_requests_seconds_bucket[5m])))
```

### 2. Traces — follow one request across 4 services
In **Jaeger** (or Grafana → Explore → Tempo), open a `gateway-service` trace. You'll see the span
tree: gateway → order → product (×2) → payment. Each box is a **span** with its own **spanId**; they
all share one **traceId**. Notice the ~8% of payment spans marked with an error — those are the
simulated card declines.

### 3. Logs — and correlation
In Grafana → Explore → **Loki**, run `{service_name="order-service"}`. Every line shows
`trace=… span=… corr=…`. Pick a failed checkout, copy its **traceId**, and either:
- click **"View trace"** (derived field) to jump straight to the trace in Tempo, or
- in Loki query `{service_name=~".+"} | trace_id="<that id>"` to see **every service's logs for that one
  request** — that's distributed log correlation.

### 4. Trace ⇄ logs ⇄ metrics, all linked
From a Tempo trace, use **"Logs for this span"** to pivot to Loki. From the service-graph (Grafana →
Explore → Tempo → Service Graph) you can see the live call topology generated from spans.

### 5. AIOps — anomaly detection, correlation, and LLM root-cause analysis
Open **http://localhost:8090**. Every 30s, `aiops-service` re-runs three detectors against Prometheus,
Loki, and Tempo (z-score anomaly detection, log-pattern/burst detection, TraceQL error/slow-trace
search), then a correlation engine dedups and groups the results into per-service **incidents**. Click
an incident to see its findings, suggested remediation (with an **Execute** button for known-safe
actions), and a markdown **root-cause report** — LLM-generated via Claude if `ANTHROPIC_API_KEY` is
set, otherwise a heuristic fallback. Try breaking something and watching an incident form:
```powershell
kubectl -n shop scale deployment/payment-service --replicas=0
./scripts/generate-traffic.ps1
# watch http://localhost:8090 — an incident opens, RCA fills in, Grafana gets an annotation
kubectl -n shop scale deployment/payment-service --replicas=1   # heal
```
See [REVISION-NOTES.md § 9](REVISION-NOTES.md#9-aiops--the-layer-on-top-of-the-three-pillars) for the
full architecture (detectors, correlation, remediation, RCA) and how to enable Claude-powered RCA.

---

## How correlation is implemented

- **traceId / spanId**: produced entirely by the **OpenTelemetry Java agent** (`-javaagent`, baked into
  each image). It auto-instruments Spring MVC and `RestTemplate`, propagates W3C `traceparent` headers
  between services, and injects `trace_id`/`span_id` into the SLF4J MDC.
- **correlationId**: ours. [`CorrelationIdFilter`](common/src/main/java/com/shop/common/CorrelationIdFilter.java)
  reads or mints `X-Correlation-ID` and puts it in the MDC;
  [`CorrelationIdRestInterceptor`](common/src/main/java/com/shop/common/CorrelationIdRestInterceptor.java)
  forwards it on every outbound call. The shared
  [`logback-spring.xml`](common/src/main/resources/logback-spring.xml) prints all three on every line.

The `common` module is auto-applied to every service via Spring Boot auto-configuration, so each
service stays tiny.

---

## Project layout

```
pom.xml                      Parent (multi-module) Maven build
common/                      Shared: correlation filter, RestTemplate, logback config
services/
  gateway-service/           Public edge (8080)
  order-service/             Orchestrator -> product + payment (8081)
  product-service/           Catalog + stock (8082)
  payment-service/           Simulated payment gateway (8083)
  aiops-service/             Python/FastAPI + React — detectors, correlation, remediation, RCA (8090)
    app/                     FastAPI backend (detectors/, correlation.py, remediation.py, rca.py, main.py)
    frontend/                React (Vite) dashboard — built at Docker build time, served by FastAPI
Dockerfile                   One parameterized image build for the 4 Java services (+ OTel agent)
Dockerfile.aiops             Two-stage build: node builds the React frontend, python runs the backend
kind/kind-config.yaml        KIND cluster definition
k8s/
  00-namespace.yaml
  observability/             otel-collector, prometheus, tempo, jaeger, loki, grafana
  services/                  Deployment + Service per microservice, incl. aiops-service (+ RBAC)
scripts/                     build-images / deploy / port-forward / generate-traffic / teardown
```

---

## Notes & next experiments

- **Why both Jaeger and Tempo?** The Collector fans traces to both so you can compare a dedicated
  tracing UI (Jaeger) with Grafana's integrated Tempo (service graphs, trace→logs jumps).
- **Make it fail on purpose**: `kubectl -n shop scale deploy/payment-service --replicas=0`, send
  traffic, and watch error metrics spike, error spans appear, and error logs correlate — and now also
  watch `aiops-service` (http://localhost:8090) turn that into a correlated incident with a root-cause
  report.
- **Enable Claude-powered RCA**: without an API key, `aiops-service` produces a heuristic RCA report.
  To get an LLM-generated one, `kubectl -n shop create secret generic aiops-secrets
  --from-literal=anthropic-api-key=<your-key>` then `kubectl -n shop rollout restart
  deployment/aiops-service`.
- **Add latency**: payment-service already injects a slow tail ~10% of the time — find it with the p95
  panel, then drill into a slow trace.
- **Storage is ephemeral** (`emptyDir`): restarting Tempo/Loki/Jaeger clears their data. Fine for a lab.
- **Resource usage**: the whole stack fits comfortably in Docker Desktop's defaults; if pods are
  `Pending`, give Docker a bit more memory.

"""LLM-powered root-cause analysis.

Gathers cross-pillar evidence for an incident — the findings themselves, a
fresh metrics snapshot, recent error logs, and the full span tree of one
example error trace — and asks Claude to synthesise a root-cause report.

If no ANTHROPIC_API_KEY is configured the engine falls back to a heuristic
report (evidence dump + rule-based guess), so the lab still works offline.
"""
from __future__ import annotations

import json
import logging
import time

import httpx

from . import config
from .detectors.trace_analyser import fetch_trace
from .models import Incident

log = logging.getLogger("aiops.rca")

SYSTEM_PROMPT = """You are an SRE assistant embedded in a Kubernetes observability lab.
The system is a shopping platform with four Spring Boot services:
gateway-service (public edge, :8080) -> order-service (orchestrator, :8081)
-> product-service (catalog/stock, :8082) and payment-service (simulated gateway, :8083).
Telemetry: Micrometer/Prometheus metrics, OTel traces (Tempo), OTel logs (Loki).

You receive machine-collected evidence for one incident. Write a concise
root-cause analysis in markdown with exactly these sections:
## Summary  (2-3 sentences: what happened, blast radius)
## Root cause  (the most likely cause, and how the evidence supports it)
## Evidence trail  (bullet list connecting metrics -> traces -> logs)
## Recommended actions  (ordered, most impactful first; name exact kubectl/Grafana steps)
## Confidence  (high/medium/low + what extra data would raise it)

Ground every claim in the supplied evidence. If evidence is thin, say so."""


async def _collect_evidence(client: httpx.AsyncClient, incident: Incident) -> dict:
    """Pull fresh context from the three pillars for the incident's service."""
    evidence: dict = {
        "incident": incident.to_dict(include_rca=False),
        "collected_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

    # Metrics snapshot for the affected service
    try:
        queries = {
            "request_rate_per_sec": f'sum(rate(http_server_requests_seconds_count{{service="{incident.service}"}}[2m]))',
            "error_rate_5xx_per_sec": f'sum(rate(http_server_requests_seconds_count{{service="{incident.service}",status=~"5.."}}[2m]))',
            "p95_latency_sec": f'histogram_quantile(0.95, sum by (le) (rate(http_server_requests_seconds_bucket{{service="{incident.service}"}}[5m])))',
        }
        snapshot = {}
        for name, q in queries.items():
            r = await client.get(f"{config.PROMETHEUS_URL}/api/v1/query",
                                 params={"query": q}, timeout=10)
            result = r.json()["data"]["result"]
            snapshot[name] = result[0]["value"][1] if result else "no data"
        evidence["metrics_snapshot"] = snapshot
    except Exception as exc:
        evidence["metrics_snapshot"] = f"unavailable: {exc}"

    # Recent error logs for the service
    try:
        end_ns = int(time.time() * 1e9)
        r = await client.get(
            f"{config.LOKI_URL}/loki/api/v1/query_range",
            params={"query": f'{{service_name="{incident.service}"}} | severity_text=~"ERROR|WARN"',
                    "start": end_ns - int(600e9), "end": end_ns, "limit": 30},
            timeout=10)
        lines = [line for stream in r.json()["data"]["result"]
                 for _, line in stream["values"]]
        evidence["recent_error_logs"] = lines[-30:]
    except Exception as exc:
        evidence["recent_error_logs"] = f"unavailable: {exc}"

    # One example trace (span tree) from a traces finding, if any
    trace_ids = [tid for f in incident.findings
                 for tid in f.evidence.get("trace_ids", [])]
    if trace_ids:
        trace = await fetch_trace(client, trace_ids[0])
        if trace:
            evidence["example_trace"] = _summarise_trace(trace, trace_ids[0])

    return evidence


def _summarise_trace(trace: dict, trace_id: str) -> dict:
    """Flatten Tempo's OTLP-shaped trace JSON into (service, span, duration, status) rows."""
    rows = []
    for batch in trace.get("batches", []):
        service = next((a["value"].get("stringValue") for a in
                        batch.get("resource", {}).get("attributes", [])
                        if a["key"] == "service.name"), "unknown")
        for scope in batch.get("scopeSpans", []):
            for span in scope.get("spans", []):
                start = int(span.get("startTimeUnixNano", 0))
                end = int(span.get("endTimeUnixNano", 0))
                status = span.get("status", {})
                rows.append({
                    "service": service,
                    "span": span.get("name"),
                    "duration_ms": round((end - start) / 1e6, 1),
                    "status": status.get("code", "OK"),
                    "status_message": status.get("message", ""),
                })
    return {"trace_id": trace_id, "spans": rows[:40]}


def _heuristic_report(evidence: dict) -> str:
    """Offline fallback: no LLM, just organise the evidence and apply the rule table."""
    inc = evidence["incident"]
    sources = {f["source"] for f in inc["findings"]}
    lines = [
        "## Summary",
        f"Incident on **{inc['service']}** ({inc['severity']}) with "
        f"{len(inc['findings'])} findings across pillars: {', '.join(sorted(sources))}.",
        "",
        "## Evidence trail",
    ]
    lines += [f"- [{f['source']}] {f['detail']}" for f in inc["findings"]]
    lines += [
        "",
        "## Recommended actions",
        "1. Open Grafana Explore -> Tempo and inspect one of the error trace ids above.",
        "2. Pivot to Loki with that trace_id to read the failing service's logs.",
        "3. Check `kubectl -n shop get pods` / `kubectl -n shop describe deploy/"
        + inc["service"] + "`.",
        "",
        "_Heuristic report — set ANTHROPIC_API_KEY on the aiops-service to get "
        "Claude-generated root-cause analysis._",
    ]
    return "\n".join(lines)


async def run_rca(client: httpx.AsyncClient, incident: Incident) -> None:
    """Fill in incident.rca_report (and rca_engine) in place."""
    evidence = await _collect_evidence(client, incident)

    if not config.ANTHROPIC_API_KEY:
        incident.rca_report = _heuristic_report(evidence)
        incident.rca_engine = "heuristic"
        return

    try:
        from anthropic import AsyncAnthropic
        anthropic_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        # Streaming keeps the request alive for long generations; adaptive
        # thinking lets the model reason over the span tree before answering.
        async with anthropic_client.messages.stream(
            model=config.ANTHROPIC_MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": "Analyse this incident evidence and produce the RCA report:\n\n"
                           + json.dumps(evidence, indent=2, default=str),
            }],
        ) as stream:
            message = await stream.get_final_message()
        incident.rca_report = next(
            (b.text for b in message.content if b.type == "text"), "")
        incident.rca_engine = "claude"
        log.info("Claude RCA completed for incident #%d (%d output tokens)",
                 incident.id, message.usage.output_tokens)
    except Exception as exc:
        log.warning("Claude RCA failed for incident #%d (%s) — using heuristic", incident.id, exc)
        incident.rca_report = _heuristic_report(evidence) + f"\n\n_(Claude call failed: {exc})_"
        incident.rca_engine = "heuristic"

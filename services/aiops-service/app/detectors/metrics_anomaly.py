"""Metrics anomaly detection against Prometheus.

Technique: statistical baseline + z-score.
For each signal we pull the last 30 minutes at 30s resolution from
/api/v1/query_range, treat everything except the newest few points as the
"baseline", and flag when the current value sits more than ZSCORE_THRESHOLD
standard deviations above the baseline mean. Absolute floors stop the z-score
from firing on statistically-significant-but-tiny wiggles (0.001 -> 0.004 rps).
"""
from __future__ import annotations

import logging
import statistics
import time

import httpx

from .. import config
from ..models import Finding

log = logging.getLogger("aiops.metrics")

# (title, promql, unit, absolute floor the current value must exceed, severity)
SIGNALS = [
    (
        "Request-rate spike",
        'sum by (service) (rate(http_server_requests_seconds_count[1m]))',
        "req/s",
        1.0,
        "warning",
    ),
    (
        "5xx error-rate spike",
        'sum by (service) (rate(http_server_requests_seconds_count{status=~"5.."}[1m]))',
        "err/s",
        config.ERROR_RATE_FLOOR_PER_SEC,
        "critical",
    ),
    (
        "p95 latency spike",
        'histogram_quantile(0.95, sum by (le, service) (rate(http_server_requests_seconds_bucket[2m])))',
        "s",
        config.LATENCY_P95_FLOOR_SECONDS,
        "warning",
    ),
]


async def _query_range(client: httpx.AsyncClient, promql: str) -> list[dict]:
    end = time.time()
    resp = await client.get(
        f"{config.PROMETHEUS_URL}/api/v1/query_range",
        params={"query": promql, "start": end - 1800, "end": end, "step": 30},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["data"]["result"]


def _zscore(values: list[float]) -> tuple[float, float, float] | None:
    """Return (z, current, baseline_mean) or None if there isn't enough history."""
    if len(values) < 12:                       # need ~6 min of history minimum
        return None
    baseline, recent = values[:-3], values[-3:]
    current = statistics.fmean(recent)
    mean = statistics.fmean(baseline)
    stdev = statistics.pstdev(baseline)
    if stdev < 1e-9:
        stdev = max(mean * 0.1, 1e-9)          # flat baseline: allow 10% wiggle
    return (current - mean) / stdev, current, mean


async def detect(client: httpx.AsyncClient) -> list[Finding]:
    findings: list[Finding] = []
    for title, promql, unit, floor, severity in SIGNALS:
        try:
            series = await _query_range(client, promql)
        except Exception as exc:
            log.warning("Prometheus query failed (%s): %s", title, exc)
            continue

        for s in series:
            service = s["metric"].get("service", "unknown")
            values = [float(v) for _, v in s["values"] if v != "NaN"]
            scored = _zscore(values)
            if scored is None:
                continue
            z, current, mean = scored
            if z >= config.ZSCORE_THRESHOLD and current >= floor:
                findings.append(Finding(
                    source="metrics",
                    service=service,
                    title=title,
                    severity=severity,
                    detail=(
                        f"{title} on {service}: current {current:.3f} {unit} vs "
                        f"30-min baseline {mean:.3f} {unit} (z-score {z:.1f})"
                    ),
                    evidence={"promql": promql, "current": current,
                              "baseline_mean": mean, "zscore": round(z, 2)},
                ))

    # Rule-based check on top of the statistics: a scrape target going away
    # means the service itself is down — no baseline math needed for that.
    try:
        resp = await client.get(f"{config.PROMETHEUS_URL}/api/v1/query",
                                params={"query": 'up{job="shop-services"} == 0'}, timeout=10)
        for s in resp.json()["data"]["result"]:
            service = s["metric"].get("service", "unknown")
            findings.append(Finding(
                source="metrics",
                service=service,
                title="Scrape target down",
                severity="critical",
                detail=f"Prometheus can no longer scrape {service} — the pod is likely down or not ready.",
                evidence={"promql": 'up{job="shop-services"} == 0'},
            ))
    except Exception as exc:
        log.warning("Prometheus 'up' query failed: %s", exc)

    return findings

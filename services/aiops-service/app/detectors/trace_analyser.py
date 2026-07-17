"""Trace analysis against Tempo.

Uses Tempo's TraceQL search API to find, in the last couple of minutes:
  1. traces containing error spans  ({ status = error })
  2. abnormally slow traces         ({ duration > threshold })

Trace ids from these findings are the bridge for root-cause analysis: the RCA
engine fetches the full span tree for one example trace so Claude can see
exactly which hop failed or was slow.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict

import httpx

from .. import config
from ..models import Finding

log = logging.getLogger("aiops.traces")

WINDOW_SECONDS = 120
ERROR_TRACE_THRESHOLD = 3     # this many error traces for one service in the window


async def _search(client: httpx.AsyncClient, traceql: str) -> list[dict]:
    end = int(time.time())
    resp = await client.get(
        f"{config.TEMPO_URL}/api/search",
        params={"q": traceql, "start": end - WINDOW_SECONDS, "end": end, "limit": 50},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("traces") or []


async def fetch_trace(client: httpx.AsyncClient, trace_id: str) -> dict | None:
    """Full span tree for one trace — used as RCA evidence, not for detection."""
    try:
        resp = await client.get(f"{config.TEMPO_URL}/api/traces/{trace_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.warning("Tempo trace fetch failed for %s: %s", trace_id, exc)
        return None


async def detect(client: httpx.AsyncClient) -> list[Finding]:
    findings: list[Finding] = []

    # 1. Error traces, grouped by the root service that received the request
    try:
        by_service: dict[str, list[dict]] = defaultdict(list)
        for t in await _search(client, "{ status = error }"):
            by_service[t.get("rootServiceName", "unknown")].append(t)
        for service, traces in by_service.items():
            if len(traces) >= ERROR_TRACE_THRESHOLD:
                findings.append(Finding(
                    source="traces", service=service,
                    title="Error traces",
                    severity="critical",
                    detail=f"{len(traces)} traces with error spans rooted at {service} "
                           f"in the last {WINDOW_SECONDS}s",
                    evidence={"trace_ids": [t["traceID"] for t in traces[:5]],
                              "count": len(traces)},
                ))
    except Exception as exc:
        log.warning("Tempo error-trace search failed: %s", exc)

    # 2. Slow traces
    try:
        slow = await _search(client, f"{{ duration > {config.SLOW_TRACE_THRESHOLD_MS}ms }}")
        by_service = defaultdict(list)
        for t in slow:
            by_service[t.get("rootServiceName", "unknown")].append(t)
        for service, traces in by_service.items():
            worst = max(traces, key=lambda t: t.get("durationMs", 0))
            findings.append(Finding(
                source="traces", service=service,
                title="Slow traces",
                severity="warning",
                detail=f"{len(traces)} traces slower than {config.SLOW_TRACE_THRESHOLD_MS}ms "
                       f"rooted at {service} (worst: {worst.get('durationMs', '?')}ms)",
                evidence={"trace_ids": [t["traceID"] for t in traces[:5]],
                          "worst_ms": worst.get("durationMs")},
            ))
    except Exception as exc:
        log.warning("Tempo slow-trace search failed: %s", exc)

    return findings

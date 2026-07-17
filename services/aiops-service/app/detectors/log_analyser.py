"""Log pattern analysis against Loki.

Technique: log templating (a lightweight version of what the Drain algorithm does).
Every WARN/ERROR line is normalised into a *template* by masking the variable
parts — numbers, UUIDs, hex ids — so "Payment DECLINED for order 4711" and
"Payment DECLINED for order 9302" collapse into one pattern:
"Payment DECLINED for order <NUM>".

Two things then become detectable:
  1. NEW patterns   — an error template we have never seen before (a fresh bug).
  2. Pattern bursts — a known template suddenly occurring far more than usual.
"""
from __future__ import annotations

import logging
import re
import time
from collections import Counter

import httpx

from .. import config
from ..models import Finding

log = logging.getLogger("aiops.logs")

_MASKS = [
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I), "<UUID>"),
    (re.compile(r"\b[0-9a-f]{16,32}\b", re.I), "<HEX>"),
    (re.compile(r"\b\d+(\.\d+)?\b"), "<NUM>"),
    (re.compile(r"p-<NUM>"), "p-<NUM>"),  # keep product ids readable after number masking
]

BURST_THRESHOLD = 15          # occurrences of one template in a single window
WINDOW_SECONDS = 120


def _template(line: str) -> str:
    # Drop the log-line prefix (timestamp/level/ids) so only the message templatises.
    msg = line.split(" - ", 1)[-1].strip()
    for pattern, mask in _MASKS:
        msg = pattern.sub(mask, msg)
    return msg[:200]


class LogAnalyser:
    def __init__(self) -> None:
        # Templates seen at least once, per service — the "known patterns" memory.
        self._known: dict[str, set[str]] = {}
        self._warmed_up = False   # first pass just learns, doesn't alert

    async def _fetch(self, client: httpx.AsyncClient) -> list[tuple[str, str]]:
        """Return (service, line) pairs for WARN/ERROR logs in the last window."""
        end_ns = int(time.time() * 1e9)
        start_ns = end_ns - WINDOW_SECONDS * int(1e9)
        resp = await client.get(
            f"{config.LOKI_URL}/loki/api/v1/query_range",
            params={
                "query": '{service_name=~".+"} | severity_text=~"ERROR|WARN"',
                "start": start_ns, "end": end_ns, "limit": 1000,
            },
            timeout=10,
        )
        resp.raise_for_status()
        out = []
        for stream in resp.json()["data"]["result"]:
            service = stream["stream"].get("service_name", "unknown")
            for _, line in stream["values"]:
                out.append((service, line))
        return out

    async def detect(self, client: httpx.AsyncClient) -> list[Finding]:
        try:
            entries = await self._fetch(client)
        except Exception as exc:
            log.warning("Loki query failed: %s", exc)
            return []

        counts: Counter[tuple[str, str]] = Counter()
        samples: dict[tuple[str, str], str] = {}
        for service, line in entries:
            key = (service, _template(line))
            counts[key] += 1
            samples.setdefault(key, line)

        findings: list[Finding] = []
        for (service, template), count in counts.items():
            known = self._known.setdefault(service, set())
            is_new = template not in known
            known.add(template)

            if not self._warmed_up:
                continue  # first pass: learn the normal error vocabulary silently

            if is_new:
                findings.append(Finding(
                    source="logs", service=service,
                    title="New error pattern",
                    severity="warning",
                    detail=f"Never-seen-before WARN/ERROR pattern on {service} "
                           f"({count}x in {WINDOW_SECONDS}s): \"{template}\"",
                    evidence={"template": template, "count": count,
                              "sample": samples[(service, template)][:500]},
                ))
            elif count >= BURST_THRESHOLD:
                findings.append(Finding(
                    source="logs", service=service,
                    title="Error pattern burst",
                    severity="critical",
                    detail=f"Known pattern bursting on {service}: {count}x in "
                           f"{WINDOW_SECONDS}s — \"{template}\"",
                    evidence={"template": template, "count": count,
                              "sample": samples[(service, template)][:500]},
                ))

        self._warmed_up = True
        return findings

"""Posts incident markers to Grafana's Annotations API.

Annotations show up as vertical dashed lines on every dashboard whose time
range covers them — so when someone looks at the RED dashboard, the moment the
AIOps engine detected the incident is drawn right on the latency/error graphs.
The lab's Grafana runs with anonymous admin, so no auth header is needed.
"""
from __future__ import annotations

import logging

import httpx

from . import config
from .models import Incident

log = logging.getLogger("aiops.grafana")


async def annotate_incident(client: httpx.AsyncClient, incident: Incident) -> None:
    text = (f"AIOps incident #{incident.id} [{incident.severity}] on {incident.service}: "
            + "; ".join(f.title for f in incident.findings[:3]))
    try:
        resp = await client.post(
            f"{config.GRAFANA_URL}/api/annotations",
            json={
                "time": int(incident.started_at * 1000),
                "tags": ["aiops", incident.service, incident.severity],
                "text": text,
            },
            timeout=10,
        )
        resp.raise_for_status()
        log.info("Grafana annotation created for incident #%d", incident.id)
    except Exception as exc:
        log.warning("Grafana annotation failed for incident #%d: %s", incident.id, exc)

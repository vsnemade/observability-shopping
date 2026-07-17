"""Correlation engine: dedups findings and groups them into per-service incidents.

Why: a single root cause (say, payment-service crash-looping) produces alerts
from all three pillars at once — a metrics spike, a log burst, error traces.
Without correlation an operator sees 9 alerts; with it they see 1 incident with
9 pieces of evidence attached.

Rules:
  * a finding with the same (source, service, title) key is suppressed while a
    recent identical one is still "hot" (FINDING_COOLDOWN_SECONDS)
  * a new finding joins an open incident for the same service if that incident
    was updated within INCIDENT_WINDOW_SECONDS; otherwise a new incident opens
  * an incident with no new findings for 2x the window auto-resolves
"""
from __future__ import annotations

import logging
import time

from . import config
from .models import Finding, Incident

log = logging.getLogger("aiops.correlation")


class CorrelationEngine:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.incidents: list[Incident] = []
        self._last_seen: dict[tuple, float] = {}   # finding.key -> timestamp

    def ingest(self, new_findings: list[Finding]) -> list[Incident]:
        """Feed one detection cycle's findings in; returns incidents that are new."""
        now = time.time()
        created: list[Incident] = []

        for f in new_findings:
            last = self._last_seen.get(f.key, 0)
            if now - last < config.FINDING_COOLDOWN_SECONDS:
                continue                       # same problem, already reported
            self._last_seen[f.key] = now
            self.findings.append(f)

            incident = self._open_incident_for(f.service)
            if incident is None:
                incident = Incident(service=f.service)
                self.incidents.append(incident)
                created.append(incident)
                log.info("incident #%d opened for %s", incident.id, f.service)
            incident.add(f)
            log.info("incident #%d <- [%s] %s", incident.id, f.source, f.detail)

        self._auto_resolve(now)
        self.findings = self.findings[-500:]   # keep memory bounded
        return created

    def _open_incident_for(self, service: str) -> Incident | None:
        for inc in reversed(self.incidents):
            if (inc.service == service and inc.status == "open"
                    and time.time() - inc.updated_at < config.INCIDENT_WINDOW_SECONDS):
                return inc
        return None

    def _auto_resolve(self, now: float) -> None:
        for inc in self.incidents:
            if inc.status == "open" and now - inc.updated_at > 2 * config.INCIDENT_WINDOW_SECONDS:
                inc.status = "resolved"
                log.info("incident #%d auto-resolved (quiet for %ds)",
                         inc.id, 2 * config.INCIDENT_WINDOW_SECONDS)

    def get(self, incident_id: int) -> Incident | None:
        return next((i for i in self.incidents if i.id == incident_id), None)

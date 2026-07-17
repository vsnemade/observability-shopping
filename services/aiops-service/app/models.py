"""Data model: detectors emit Findings, the correlation engine groups them into Incidents."""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field, asdict

_finding_seq = itertools.count(1)
_incident_seq = itertools.count(1)


@dataclass
class Finding:
    """One anomalous observation from one pillar (metrics, logs, or traces)."""
    source: str            # "metrics" | "logs" | "traces"
    service: str
    title: str             # short, stable name — also the dedup key
    detail: str            # human-readable explanation with numbers
    severity: str          # "warning" | "critical"
    evidence: dict = field(default_factory=dict)   # raw numbers / trace ids / log samples
    timestamp: float = field(default_factory=time.time)
    id: int = field(default_factory=lambda: next(_finding_seq))

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.source, self.service, self.title)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Incident:
    """Findings for one service that occurred close together in time."""
    service: str
    findings: list[Finding] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: str = "open"                    # "open" | "resolved"
    rca_report: str | None = None           # markdown, filled in by the RCA engine
    rca_engine: str | None = None           # "claude" | "heuristic"
    suggested_actions: list[dict] = field(default_factory=list)
    remediation_log: list[str] = field(default_factory=list)
    id: int = field(default_factory=lambda: next(_incident_seq))

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)
        self.updated_at = finding.timestamp

    @property
    def severity(self) -> str:
        return "critical" if any(f.severity == "critical" for f in self.findings) else "warning"

    def to_dict(self, include_rca: bool = True) -> dict:
        d = {
            "id": self.id,
            "service": self.service,
            "status": self.status,
            "severity": self.severity,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "findings": [f.to_dict() for f in self.findings],
            "suggested_actions": self.suggested_actions,
            "remediation_log": self.remediation_log,
            "rca_engine": self.rca_engine,
        }
        if include_rca:
            d["rca_report"] = self.rca_report
        return d

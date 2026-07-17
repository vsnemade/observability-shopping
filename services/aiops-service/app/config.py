"""Central configuration — everything comes from env vars set in the k8s manifest."""
import os

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
TEMPO_URL = os.getenv("TEMPO_URL", "http://tempo:3200")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")

# How often the detection loop runs.
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

# Anthropic / Claude — RCA works without a key too (heuristic fallback).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

# Auto-remediation is OFF by default: the service only *suggests* actions.
# Set AUTO_REMEDIATE=true to let it restart a crash-looping deployment itself.
AUTO_REMEDIATE = os.getenv("AUTO_REMEDIATE", "false").lower() == "true"
NAMESPACE = os.getenv("NAMESPACE", "shop")

# Detection tuning
ZSCORE_THRESHOLD = float(os.getenv("ZSCORE_THRESHOLD", "3.0"))
LATENCY_P95_FLOOR_SECONDS = float(os.getenv("LATENCY_P95_FLOOR_SECONDS", "0.5"))
ERROR_RATE_FLOOR_PER_SEC = float(os.getenv("ERROR_RATE_FLOOR_PER_SEC", "0.05"))
SLOW_TRACE_THRESHOLD_MS = int(os.getenv("SLOW_TRACE_THRESHOLD_MS", "1000"))

# A finding with the same (source, service, title) is suppressed for this long
# after it first fires, so one ongoing problem doesn't spam hundreds of findings.
FINDING_COOLDOWN_SECONDS = int(os.getenv("FINDING_COOLDOWN_SECONDS", "300"))

# Findings for the same service within this window join the same incident.
INCIDENT_WINDOW_SECONDS = int(os.getenv("INCIDENT_WINDOW_SECONDS", "180"))

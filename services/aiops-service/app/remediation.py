"""Auto-remediation hooks.

Maps known failure signatures to a concrete action. By default the service
only *suggests* the action (visible on the incident); with AUTO_REMEDIATE=true
it executes the safe ones itself against the Kubernetes API using its own
service account (RBAC: get/list/patch on deployments in the shop namespace).

The one action implemented is a rolling restart — the same thing
`kubectl rollout restart deployment/<name>` does: PATCH the pod template with
a fresh `restartedAt` annotation so k8s replaces the pods.
"""
from __future__ import annotations

import datetime
import logging
import ssl
from pathlib import Path

import httpx

from . import config
from .models import Incident

log = logging.getLogger("aiops.remediation")

SA_DIR = Path("/var/run/secrets/kubernetes.io/serviceaccount")
KNOWN_SERVICES = {"gateway-service", "order-service", "product-service", "payment-service"}


def suggest_actions(incident: Incident) -> list[dict]:
    """Rule table: failure signature -> suggested action."""
    titles = {f.title for f in incident.findings}
    actions: list[dict] = []

    if "Scrape target down" in titles:
        actions.append({
            "action": "rollout_restart",
            "target": incident.service,
            "reason": "Service unreachable by Prometheus — a rolling restart often clears "
                      "a wedged pod. Equivalent: kubectl -n shop rollout restart "
                      f"deployment/{incident.service}",
            "auto_executable": True,
        })
    if "5xx error-rate spike" in titles or "Error traces" in titles:
        actions.append({
            "action": "investigate_downstream",
            "target": incident.service,
            "reason": "5xx/error spans usually mean a downstream dependency is failing — "
                      "check the RCA report and the example trace before restarting anything.",
            "auto_executable": False,
        })
    if "p95 latency spike" in titles or "Slow traces" in titles:
        actions.append({
            "action": "check_resources",
            "target": incident.service,
            "reason": "Latency spikes under load are often CPU throttling — compare "
                      "container_cpu usage with the 100m request. Consider raising limits "
                      "or replicas.",
            "auto_executable": False,
        })
    if not actions:
        actions.append({
            "action": "manual_review",
            "target": incident.service,
            "reason": "No known remediation pattern matched — review the RCA report.",
            "auto_executable": False,
        })
    return actions


async def rollout_restart(deployment: str) -> str:
    """Perform the restart via the in-cluster Kubernetes API."""
    if deployment not in KNOWN_SERVICES:
        return f"refused: {deployment} is not one of the shop services"

    token = (SA_DIR / "token").read_text()
    ctx = ssl.create_default_context(cafile=str(SA_DIR / "ca.crt"))
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    patch = {"spec": {"template": {"metadata": {"annotations": {
        "kubectl.kubernetes.io/restartedAt": now}}}}}

    async with httpx.AsyncClient(verify=ctx) as k8s:
        resp = await k8s.patch(
            f"https://kubernetes.default.svc/apis/apps/v1/namespaces/{config.NAMESPACE}"
            f"/deployments/{deployment}",
            json=patch,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/strategic-merge-patch+json"},
            timeout=15,
        )
        resp.raise_for_status()
    msg = f"rolling restart of deployment/{deployment} triggered at {now}"
    log.info(msg)
    return msg


async def maybe_auto_remediate(incident: Incident) -> None:
    """Execute auto-executable actions when AUTO_REMEDIATE=true."""
    incident.suggested_actions = suggest_actions(incident)
    if not config.AUTO_REMEDIATE:
        return
    for action in incident.suggested_actions:
        if action["action"] == "rollout_restart" and action["auto_executable"]:
            try:
                result = await rollout_restart(action["target"])
            except Exception as exc:
                result = f"rollout_restart failed: {exc}"
                log.warning(result)
            incident.remediation_log.append(result)

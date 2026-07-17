"""AIOps service — ties the pieces together.

Background loop (every POLL_INTERVAL_SECONDS):
    detectors (Prometheus / Loki / Tempo)  ->  findings
    correlation engine                     ->  incidents (dedup + grouping)
    on new incident: Grafana annotation, remediation suggestions (+ optional
    auto-remediation), and an automatic RCA run.

REST API:
    GET  /                       React dashboard (served from app/static, built by
                                 services/aiops-service/frontend)
    GET  /health                 liveness/readiness
    GET  /findings               recent raw findings
    GET  /incidents              all incidents (findings + actions, no RCA body)
    GET  /incidents/{id}         one incident including the RCA report
    POST /incidents/{id}/rca     (re-)run root-cause analysis on demand
    POST /incidents/{id}/remediate  execute the auto-executable suggested action
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import pathlib
import time

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, rca, remediation
from .correlation import CorrelationEngine
from .detectors import log_analyser, metrics_anomaly, trace_analyser
from .grafana_annotations import annotate_incident

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s")
log = logging.getLogger("aiops")

engine = CorrelationEngine()
logs_detector = log_analyser.LogAnalyser()
http_client: httpx.AsyncClient | None = None
loop_stats = {"cycles": 0, "last_cycle_at": None, "last_error": None}


async def detection_cycle() -> None:
    assert http_client is not None
    findings = []
    findings += await metrics_anomaly.detect(http_client)
    findings += await logs_detector.detect(http_client)
    findings += await trace_analyser.detect(http_client)

    new_incidents = engine.ingest(findings)
    for incident in new_incidents:
        await annotate_incident(http_client, incident)
        await remediation.maybe_auto_remediate(incident)
        # RCA runs in the background so a slow LLM call never blocks detection.
        asyncio.create_task(rca.run_rca(http_client, incident))


async def detection_loop() -> None:
    log.info("detection loop starting (interval %ss, model %s, auto-remediate %s)",
             config.POLL_INTERVAL_SECONDS, config.ANTHROPIC_MODEL, config.AUTO_REMEDIATE)
    while True:
        try:
            await detection_cycle()
            loop_stats["cycles"] += 1
            loop_stats["last_cycle_at"] = time.time()
            loop_stats["last_error"] = None
        except Exception as exc:
            loop_stats["last_error"] = str(exc)
            log.exception("detection cycle failed")
        await asyncio.sleep(config.POLL_INTERVAL_SECONDS)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    global http_client
    http_client = httpx.AsyncClient()
    task = asyncio.create_task(detection_loop())
    yield
    task.cancel()
    await http_client.aclose()


app = FastAPI(title="aiops-service", lifespan=lifespan)

# Lets the Vite dev server (localhost:5173) call the API directly during frontend
# development. Harmless in-cluster since the built dashboard is same-origin there.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "UP", **loop_stats,
            "llm_rca_enabled": bool(config.ANTHROPIC_API_KEY),
            "auto_remediate": config.AUTO_REMEDIATE}


@app.get("/findings")
async def findings() -> list[dict]:
    return [f.to_dict() for f in engine.findings[-100:]]


@app.get("/incidents")
async def incidents() -> list[dict]:
    return [i.to_dict(include_rca=False) for i in engine.incidents]


@app.get("/incidents/{incident_id}")
async def incident(incident_id: int) -> dict:
    inc = engine.get(incident_id)
    if inc is None:
        raise HTTPException(404, f"incident {incident_id} not found")
    return inc.to_dict()


@app.post("/incidents/{incident_id}/rca")
async def rerun_rca(incident_id: int) -> dict:
    inc = engine.get(incident_id)
    if inc is None:
        raise HTTPException(404, f"incident {incident_id} not found")
    assert http_client is not None
    await rca.run_rca(http_client, inc)
    return {"id": inc.id, "rca_engine": inc.rca_engine, "rca_report": inc.rca_report}


@app.post("/incidents/{incident_id}/remediate")
async def remediate(incident_id: int) -> dict:
    inc = engine.get(incident_id)
    if inc is None:
        raise HTTPException(404, f"incident {incident_id} not found")
    executed = []
    for action in inc.suggested_actions:
        if action.get("auto_executable"):
            try:
                result = await remediation.rollout_restart(action["target"])
            except Exception as exc:
                result = f"failed: {exc}"
            inc.remediation_log.append(result)
            executed.append(result)
    if not executed:
        raise HTTPException(409, "no auto-executable action suggested for this incident")
    return {"id": inc.id, "executed": executed}


# Serves the compiled React dashboard (see Dockerfile.aiops — copied into
# app/static during the image build). Mounted LAST so it never shadows the
# API routes above: Starlette matches routes in registration order, and this
# mount's "/" prefix would otherwise swallow every request.
_frontend_dist = pathlib.Path(__file__).parent / "static"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
else:
    log.warning("app/static not found — frontend not built. API-only mode "
                "(run `npm run build` in services/aiops-service/frontend, "
                "or use the full Docker build).")

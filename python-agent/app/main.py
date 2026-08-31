"""FastAPI application: WebSocket ingress that drives the inversion agent.

Node.js streams sanitized field data in; each job is validated with Pydantic,
run through the agentic inversion loop (in a worker thread so the event loop
stays responsive), and the converged model is streamed back.
"""

from __future__ import annotations

import asyncio
import json
import logging

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .agent.chat_agent import ChatUnavailableError, build_chat_agent
from .agent.classification_orchestrator import run_classification_agent
from .agent.data_cleaner import CleaningUnavailableError, build_data_cleaner
from .agent.interpreter import build_interpreter
from .agent.joint_interpreter import build_joint_interpreter
from .agent.lithology_interpreter import build_lithology_interpreter
from .agent.orchestrator import run_inversion_agent
from .agent.report_generator import ReportUnavailableError, build_report_generator
from .config import settings
from .schemas import InversionJob, JointInterpretationRequest, JointInterpretationResult
from .schemas_chat import ChatRequest, ChatResponse
from .schemas_classification import BoreholeClassificationJob
from .schemas_cleaning import CleaningRequest, CleaningResult
from .schemas_report import ReportRequest, ReportResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("python-agent")

app = FastAPI(title="Agentic Field-Data Inversion Engine", version="0.1.0")


async def _safe_send_json(websocket: WebSocket, payload: dict) -> None:
    """Send a result over the WebSocket, tolerating a connection that died
    while the job was running.

    Some methods (a real Nelder-Mead search with ~50-70 real subprocess
    iterations, or a slow LLM turn) legitimately take longer than uvicorn's
    default ~20s ping interval / ~20s ping timeout. If the client's ping
    response is delayed past that window, the server closes the socket and
    Node's AgentClient reconnects on a NEW connection — but this handler is
    still awaiting the ORIGINAL (now-dead) connection's send, which raises a
    bare RuntimeError (Starlette has no dedicated exception for "the
    ASGI server already sent websocket.close"). Left uncaught, that
    RuntimeError propagates out of the whole `inversion_stream` handler
    instead of just this one job's result — silently dropping the result AND
    killing an otherwise-healthy handler coroutine. Documented mitigation:
    raise the ping timeout in deployment (see README/docker-compose) so this
    is rare in practice; this is the correctness backstop for whenever it
    still happens."""
    try:
        await websocket.send_json(payload)
    except (RuntimeError, WebSocketDisconnect) as exc:
        job_id = payload.get("jobId", "?")
        logger.warning(
            "Job %s: result computed but could not be delivered — client reconnected "
            "before the send completed (%r)",
            job_id, exc,
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": settings.gemini_model, "mode": settings.agent_mode}


@app.post("/interpret/joint")
async def interpret_joint(req: JointInterpretationRequest) -> JointInterpretationResult:
    """Synthesizes several methods' results (gathered by Node from
    persistence) into one integrated report — a plain request/response,
    not a WebSocket stream, since it's a single one-shot call."""
    interpreter = build_joint_interpreter()
    logger.info(
        "Joint interpretation requested for site %s (%d methods)", req.siteId, len(req.methodResults)
    )
    result = await asyncio.to_thread(interpreter.interpret, req.siteId, req.methodResults, req.siteNote)
    logger.info(
        "Site %s: joint interpretation confidence=%s corroboration=%s flagged=%s",
        req.siteId, result.confidence, result.corroboration, result.flagged_anomaly,
    )
    return result


@app.post("/clean", response_model=None)
async def clean_raw_data(req: CleaningRequest) -> CleaningResult | JSONResponse:
    """The Data Cleaning Agent: turns genuinely raw/messy uploaded text into
    a validated {timeSteps, amplitudes} pair. A plain request/response, like
    /interpret/joint — one LLM call, no WebSocket needed. Deliberately
    upstream of everything else: the caller (Node's POST /clean/raw-data,
    the dashboard Upload page) still submits the RESULT through the normal
    POST /ingest/field-data path, so nothing downstream of ingestion changes.
    """
    try:
        cleaner = build_data_cleaner()
    except CleaningUnavailableError as exc:
        logger.warning("Cleaning request for %s rejected: %s", req.fileName, exc)
        return JSONResponse(status_code=503, content={"status": "error", "message": str(exc)})

    logger.info("Cleaning requested: %s (%s, %d chars)", req.fileName, req.dataType, len(req.rawText))
    try:
        result = await asyncio.to_thread(cleaner.clean, req.dataType, req.fileName, req.rawText)
        return CleaningResult(**result)
    except Exception as exc:
        # Deliberately NOT degrading to a best-effort result the way
        # LLMInterpreter does on a parse failure: a malformed cleaning reply
        # would otherwise silently feed corrupted/hallucinated numbers into
        # the inversion pipeline. Fail loudly instead.
        logger.exception("Cleaning failed for %s", req.fileName)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Cleaning agent failed: {exc!r}"},
        )


@app.post("/chat/query", response_model=None)
async def chat_query(req: ChatRequest) -> ChatResponse | JSONResponse:
    """The Site Chat Agent: answers a natural-language question about one
    site's own run/interpretation history. A plain request/response, like
    /interpret/joint — one LLM call, no WebSocket needed. Node assembles
    `runHistory` from Postgres (the same repository.listBySite query already
    used for /sites/:siteId/interpret) and persists both the question and
    the answer; this endpoint itself is stateless.
    """
    try:
        agent = build_chat_agent()
    except ChatUnavailableError as exc:
        logger.warning("Chat request for site %s rejected: %s", req.siteId, exc)
        return JSONResponse(status_code=503, content={"status": "error", "message": str(exc)})

    logger.info("Chat requested for site %s (%d runs in context)", req.siteId, len(req.runHistory))
    try:
        result = await asyncio.to_thread(
            agent.answer, req.siteId, req.question, req.history, req.runHistory, req.siteNote
        )
        return result
    except Exception as exc:
        # Deliberately NOT degrading to a placeholder answer, same rationale
        # as /clean: a fabricated-but-plausible chat answer is worse than a
        # loud failure.
        logger.exception("Chat failed for site %s", req.siteId)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Chat agent failed: {exc!r}"},
        )


@app.post("/reports/site", response_model=None)
async def generate_site_report(req: ReportRequest) -> ReportResult | JSONResponse:
    """The Site Report Generator: drafts a markdown report from a site's run
    history and (if available) its joint interpretation. A plain
    request/response, like /interpret/joint. Node persists the result and
    broadcasts it over SSE; this endpoint itself is stateless.
    """
    try:
        generator = build_report_generator()
    except ReportUnavailableError as exc:
        logger.warning("Report request for site %s rejected: %s", req.siteId, exc)
        return JSONResponse(status_code=503, content={"status": "error", "message": str(exc)})

    logger.info("Report requested for site %s (%d runs)", req.siteId, len(req.runHistory))
    try:
        result = await asyncio.to_thread(
            generator.generate, req.siteId, req.runHistory, req.siteNote, req.jointInterpretation
        )
        return result
    except Exception as exc:
        logger.exception("Report generation failed for site %s", req.siteId)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Report generator failed: {exc!r}"},
        )


async def _handle_lithology_job(websocket: WebSocket, raw: str) -> None:
    """The LITHOLOGY method is a classification problem, not a curve fit —
    a different job schema (BoreholeClassificationJob) and a different
    orchestrator (run_classification_agent), but the SAME InversionResult
    wire shape on the way out, so Node's persistence/alerts/dashboard need
    no changes to handle it."""
    try:
        job = BoreholeClassificationJob.model_validate_json(raw)
    except ValidationError as exc:
        logger.warning("Rejected malformed LITHOLOGY payload: %s", exc)
        await _safe_send_json(websocket, {"status": "rejected", "errors": json.loads(exc.json())})
        return

    feature_names = [c.name for c in job.train.curves]
    train_x = [[c.values[i] for c in job.train.curves] for i in range(len(job.train.depth))]
    test_x = [[c.values[i] for c in job.predict.curves] for i in range(len(job.predict.depth))]

    logger.info(
        "Job %s (LITHOLOGY): %d train / %d predict samples — starting classification",
        job.jobId, len(train_x), len(test_x),
    )

    result = await asyncio.to_thread(
        run_classification_agent,
        job.jobId, train_x, job.train.labels, test_x, feature_names, job.classes, job.predictTrueLabels,
    )

    logger.info("Job %s: %s (%s)", result.jobId, result.status, result.message)

    if result.status != "error":
        interpreter = build_lithology_interpreter()
        result.interpretation = await asyncio.to_thread(
            interpreter.interpret, job.sensorId, result, job.siteNote
        )
        logger.info(
            "Job %s: interpretation confidence=%s flagged=%s",
            result.jobId, result.interpretation.confidence, result.interpretation.flagged_anomaly,
        )

    await _safe_send_json(websocket, result.model_dump())


@app.websocket("/ws/inversion-stream")
async def inversion_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("Node.js ingestion client connected")
    try:
        while True:
            raw = await websocket.receive_text()

            try:
                peek = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Rejected non-JSON payload")
                await _safe_send_json(websocket, {"status": "rejected", "errors": "invalid JSON"})
                continue

            if peek.get("dataType") == "LITHOLOGY":
                await _handle_lithology_job(websocket, raw)
                continue

            try:
                job = InversionJob.model_validate_json(raw)
            except ValidationError as exc:
                logger.warning("Rejected malformed payload: %s", exc)
                await _safe_send_json(
                    websocket, {"status": "rejected", "errors": json.loads(exc.json())}
                )
                continue

            t_obs = np.asarray(job.data.time, dtype=float)
            d_obs = np.asarray(job.data.amplitude, dtype=float)
            aux = (
                {k: np.asarray(v, dtype=float) for k, v in job.auxData.items()}
                if job.auxData
                else None
            )
            logger.info(
                "Job %s (%s): %d samples — starting inversion",
                job.jobId,
                job.dataType,
                d_obs.size,
            )

            # Blocking work (LLM calls + subprocesses) off the event loop.
            #
            # Wrapped because this connection is long-lived and shared by every
            # job: an unhandled exception in ONE job's inversion propagates out
            # of the whole `inversion_stream` handler, dropping the socket and
            # silently losing every job queued behind it. (Observed exactly
            # once, under compose: a NaN misfit serialized to JSON `null`,
            # which then hit `np.isclose(x, None)` -> TypeError. Both of those
            # specific causes are fixed at their source; this is the backstop
            # that keeps the NEXT such bug to one failed job.) Same reasoning
            # as _safe_send_json above, on the compute side rather than the
            # send side.
            try:
                result = await asyncio.to_thread(
                    run_inversion_agent, job.jobId, job.dataType, t_obs, d_obs, None, aux
                )
            except Exception as exc:
                logger.exception("Job %s: inversion failed unexpectedly", job.jobId)
                await _safe_send_json(
                    websocket,
                    {
                        "jobId": job.jobId,
                        "status": "error",
                        "final_model": {},
                        "l2_norm_error": None,
                        "iterations": 0,
                        "message": f"Unhandled inversion error: {exc!r}",
                    },
                )
                continue

            logger.info(
                "Job %s: %s (L2=%s, iters=%d)",
                result.jobId,
                result.status,
                result.l2_norm_error,
                result.iterations,
            )

            # Interpretation only makes sense if we have a model to read; a
            # hard "error" status has no final_model worth interpreting.
            if result.status != "error":
                interpreter = build_interpreter()
                result.interpretation = await asyncio.to_thread(
                    interpreter.interpret, job.sensorId, result, job.siteNote
                )
                logger.info(
                    "Job %s: interpretation confidence=%s flagged=%s",
                    result.jobId,
                    result.interpretation.confidence,
                    result.interpretation.flagged_anomaly,
                )

            await _safe_send_json(websocket, result.model_dump())
    except WebSocketDisconnect:
        logger.info("Node.js ingestion client disconnected")

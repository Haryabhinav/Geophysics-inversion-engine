"""HTTP wrapper around the local sandbox runner.

Exposes POST /execute so the agent backend can run model-authored code in a
separate, network-isolated container instead of in its own process.
"""

from __future__ import annotations

import asyncio
import logging

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

from tools.sandbox import run_local, run_local_classifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sandbox-service")

app = FastAPI(title="Sandbox Execution Service", version="0.1.0")


class ExecuteRequest(BaseModel):
    code: str
    t_obs: list[float] = Field(..., min_length=1)
    d_obs: list[float] = Field(..., min_length=1)
    timeout_s: int = 10
    aux: dict[str, list[float]] | None = None


class ExecuteClassifierRequest(BaseModel):
    code: str
    X_train: list[list[float]] = Field(..., min_length=1)
    y_train: list[str] = Field(..., min_length=1)
    X_test: list[list[float]] = Field(..., min_length=1)
    feature_names: list[str]
    classes: list[str]
    timeout_s: int = 10


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/execute")
async def execute(req: ExecuteRequest) -> dict:
    t_obs = np.asarray(req.t_obs, dtype=float)
    d_obs = np.asarray(req.d_obs, dtype=float)
    aux = {k: np.asarray(v, dtype=float) for k, v in req.aux.items()} if req.aux else None
    logger.info("Executing model code (%d samples, timeout %ds)", d_obs.size, req.timeout_s)
    # Run the blocking subprocess off the event loop.
    return await asyncio.to_thread(run_local, req.code, t_obs, d_obs, req.timeout_s, aux)


@app.post("/execute-classifier")
async def execute_classifier(req: ExecuteClassifierRequest) -> dict:
    logger.info(
        "Executing classifier code (%d train, %d test, timeout %ds)",
        len(req.y_train), len(req.X_test), req.timeout_s,
    )
    return await asyncio.to_thread(
        run_local_classifier,
        req.code, req.X_train, req.y_train, req.X_test, req.feature_names, req.classes, req.timeout_s,
    )

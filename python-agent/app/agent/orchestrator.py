"""The agentic inversion loop.

Ties the modeler (code author) to the sandbox (code runner):

  propose code -> run in sandbox -> read L2 norm -> converged? -> else feed back

Returns the best model found. Synchronous by design (the LLM call and the
subprocess are blocking); the WebSocket handler runs it via ``asyncio.to_thread``.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from tools.sandbox import execute_generated_model

from ..config import settings
from ..schemas import InversionResult
from .methods import METHOD_REGISTRY
from .modeler import Modeler, build_modeler

logger = logging.getLogger("python-agent.orchestrator")

# EM inversion is non-unique ("equivalence"): several different resistivity/
# depth models can fit the same curve almost equally well. A model is kept as
# "equivalent" if its L2 is within this additive margin of the best L2 found.
EQUIVALENCE_BAND = 0.05
EQUIVALENCE_TOP_K = 3


def _equivalent_models(
    candidates: list[tuple[float, dict[str, Any]]],
    best_l2: float,
    band: float = EQUIVALENCE_BAND,
    top_k: int = EQUIVALENCE_TOP_K,
) -> list[dict[str, Any]]:
    """Distinct models within `band` of best_l2, best-first, deduplicated.

    Dedup is by exact repr equality — cheap and sufficient here since distinct
    iterations of a modeler essentially never produce bit-identical models
    unless they really are the same candidate proposed twice.
    """
    within_band = sorted((l2, m) for l2, m in candidates if l2 <= best_l2 + band)
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for l2, model in within_band:
        key = repr(model)
        if key in seen:
            continue
        seen.add(key)
        result.append({"model": model, "l2_norm_error": l2})
        if len(result) >= top_k:
            break
    return result


def _recompute_l2(d_obs: np.ndarray, d_pred: np.ndarray) -> float:
    """Independently recompute the relative L2 misfit from d_obs/d_pred.

    The sandbox already computes this misfit in the harness (never the model
    author), but that computation happens inside a subprocess running
    LLM-authored code — a bug there (or a script that fabricates a plausible
    but wrong d_pred) can desync the reported l2_norm from what d_obs/d_pred
    actually says. We have both arrays here, so recheck rather than trust.
    """
    diff = float(np.linalg.norm(d_obs - d_pred))
    den = float(np.linalg.norm(d_obs))
    return diff / den if den > 1e-30 else diff


def _summarize(t_obs: np.ndarray, d_obs: np.ndarray) -> dict[str, Any]:
    preview = 5
    return {
        "n": int(t_obs.size),
        "t_min": float(t_obs.min()),
        "t_max": float(t_obs.max()),
        "d_first": [round(float(x), 6) for x in d_obs[:preview]],
        "d_last": [round(float(x), 6) for x in d_obs[-preview:]],
        "d_abs_max": float(np.abs(d_obs).max()),
    }


def run_inversion_agent(
    job_id: str,
    data_type: str,
    t_obs: np.ndarray,
    d_obs: np.ndarray,
    modeler: Modeler | None = None,
    aux: dict[str, np.ndarray] | None = None,
) -> InversionResult:
    spec = METHOD_REGISTRY.get(data_type)
    summarize = spec.summarize_fn if (spec and spec.summarize_fn) else _summarize
    summary = summarize(t_obs, d_obs)
    # `modeler` is injectable for testing; production callers leave it None.
    if modeler is None:
        modeler = build_modeler(data_type, summary)

    tol = spec.l2_tolerance if (spec and spec.l2_tolerance is not None) else settings.l2_tolerance
    is_offline = getattr(modeler, "IS_OFFLINE", False)
    if is_offline:
        max_iters = (
            spec.offline_max_iterations
            if (spec and spec.offline_max_iterations is not None)
            else settings.offline_max_iterations
        )
    else:
        max_iters = (
            spec.max_iterations if (spec and spec.max_iterations is not None) else settings.max_iterations
        )
    timeout_s = (
        spec.sandbox_timeout_s if (spec and spec.sandbox_timeout_s is not None) else settings.sandbox_timeout_s
    )

    best_l2: float | None = None
    best_model: dict[str, Any] = {}
    best_predicted: list[float] | None = None
    l2_history: list[float] = []
    candidates: list[tuple[float, dict[str, Any]]] = []
    last_error: str | None = None
    feedback: dict[str, Any] | None = None

    for iteration in range(max_iters):
        try:
            code = modeler.propose(iteration, summary, feedback)
        except Exception as exc:  # modeler/LLM failure — abort cleanly
            logger.exception("Modeler failed on iteration %d", iteration)
            return InversionResult(
                jobId=job_id,
                status="error",
                final_model=best_model,
                l2_norm_error=best_l2,
                iterations=iteration,
                message=f"Modeler error: {exc!r}",
                predicted=best_predicted,
                l2_history=l2_history,
            )

        result = execute_generated_model(code, t_obs, d_obs, timeout_s=timeout_s, aux=aux)

        if not result["ok"]:
            last_error = result["error"]
            logger.info("Iter %d: sandbox error: %s", iteration, last_error.splitlines()[-1:])
            feedback = {"l2": None, "error": last_error}
            continue

        l2 = result["l2_norm"]
        model = result["m_current"]
        d_pred_raw = result.get("d_pred")

        # Defensive: an `ok` result whose misfit isn't a usable number is a
        # broken contract, but it must not take the loop down with it.
        # `np.isclose(x, None)` raises TypeError, and that exception escaped
        # run_inversion_agent, asyncio.to_thread and the whole WebSocket
        # handler — killing the connection and silently losing every job
        # queued behind it. Treat it as a failed iteration instead.
        if l2 is None or not np.isfinite(l2):
            last_error = f"sandbox returned a non-numeric misfit ({l2!r})"
            logger.warning("Iter %d: %s", iteration, last_error)
            feedback = {"l2": None, "error": last_error}
            continue

        if d_pred_raw is not None:
            d_pred_arr = np.asarray(d_pred_raw, dtype=float)
            if d_pred_arr.shape != d_obs.shape:
                last_error = (
                    f"sandbox returned d_pred with shape {d_pred_arr.shape}, "
                    f"expected {d_obs.shape}"
                )
                logger.info("Iter %d: %s", iteration, last_error)
                feedback = {"l2": None, "error": last_error}
                continue

            recomputed = _recompute_l2(d_obs, d_pred_arr)
            if not np.isclose(recomputed, l2, rtol=1e-3, atol=1e-6):
                logger.warning(
                    "Iter %d: sandbox-reported L2 %.6g disagrees with "
                    "independently recomputed L2 %.6g from d_pred; trusting "
                    "the recomputed value",
                    iteration,
                    l2,
                    recomputed,
                )
            l2 = recomputed

        last_error = None
        l2_history.append(l2)
        candidates.append((l2, model))
        logger.info("Iter %d: L2 = %.6g", iteration, l2)

        if best_l2 is None or l2 < best_l2:
            best_l2, best_model = l2, model
            best_predicted = result.get("d_pred")

        if l2 <= tol:
            return InversionResult(
                jobId=job_id,
                status="converged",
                final_model=model,
                l2_norm_error=l2,
                iterations=iteration + 1,
                message=f"Converged: L2 {l2:.6g} <= tol {tol}",
                predicted=result.get("d_pred"),
                l2_history=l2_history,
                equivalent_models=_equivalent_models(candidates, l2),
            )

        feedback = {"l2": l2, "error": None}

    # Out of iterations.
    if best_l2 is None:
        return InversionResult(
            jobId=job_id,
            status="error",
            iterations=max_iters,
            message=f"All {max_iters} iterations failed. Last error: {last_error}",
            l2_history=l2_history,
        )

    return InversionResult(
        jobId=job_id,
        status="max_iterations_reached",
        final_model=best_model,
        l2_norm_error=best_l2,
        iterations=max_iters,
        message=f"Best L2 {best_l2:.6g} after {max_iters} iterations (tol {tol})",
        predicted=best_predicted,
        l2_history=l2_history,
        equivalent_models=_equivalent_models(candidates, best_l2),
    )

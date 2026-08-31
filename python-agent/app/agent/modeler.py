"""Modelers: pluggable strategies that propose forward-model code each turn.

Two implementations:

* ``GeminiModeler`` — the real agent. Gemini authors ``empymod`` scripts and
  revises them from the L2-norm feedback (the spec's system prompt).

* ``OfflineHeuristicModeler`` — a deterministic derivative-free optimizer
  (pattern / compass search over a reduced synthetic decay model). It is a
  genuine optimizer, used as a test double so the whole pipeline can run and be
  verified without an API key or network. It emits numpy-only code, so the
  sandbox needs no `empymod` for offline runs.

Both satisfy the ``Modeler`` protocol: ``propose(iteration, data_summary,
feedback) -> str`` returning a Python script.
"""

from __future__ import annotations

import logging
import math
import os
import re
from typing import Any, Protocol

from ..config import settings
from . import prompts
from .llm_client import LLMClient, build_llm_client
from .optimizers import _PENALTY, _nelder_mead

logger = logging.getLogger("python-agent.modeler")

Feedback = dict[str, Any] | None


class Modeler(Protocol):
    def propose(self, iteration: int, data_summary: dict[str, Any], feedback: Feedback) -> str: ...


# --------------------------------------------------------------------------- #
# Real agent: an LLM authors empymod scripts (provider-agnostic via LLMClient).
# --------------------------------------------------------------------------- #

_CODE_FENCE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


def _extract_python(text: str) -> str:
    """Pull the Python out of a model reply, tolerating markdown fences."""
    match = _CODE_FENCE.search(text)
    return (match.group(1) if match else text).strip()


class GeminiModeler:
    def __init__(self, data_type: str, client: LLMClient | None = None) -> None:
        # `client` is injectable for testing; production callers leave it None,
        # in which case it's built lazily so the offline path needs no API key.
        self._client = client or build_llm_client("gemini", settings.gemini_model)
        self._system = prompts.system_prompt(data_type)
        # Conversation history (dict form), appended only on success so a retried
        # call never duplicates a turn.
        self._history: list[dict[str, Any]] = []

    def propose(self, iteration: int, data_summary: dict[str, Any], feedback: Feedback) -> str:
        if iteration == 0:
            user = prompts.initial_user_prompt(data_summary, settings.l2_tolerance)
        else:
            assert feedback is not None
            user = prompts.feedback_prompt(
                l2_norm=feedback.get("l2"),
                error=feedback.get("error"),
                tolerance=settings.l2_tolerance,
            )

        self._history.append({"role": "user", "parts": [{"text": user}]})
        text = self._client.generate(self._system, self._history, settings.gemini_max_tokens)
        self._history.append({"role": "model", "parts": [{"text": text}]})
        return _extract_python(text)


# --------------------------------------------------------------------------- #
# Test double: deterministic pattern-search optimizer.
# --------------------------------------------------------------------------- #

# Reduced synthetic TDEM decay model used ONLY by the offline modeler:
#   d(t) = a1 * exp(-t / tau1) + a2 * exp(-t / tau2)
# Parameters are searched in log10 space: p = [log a1, log tau1, log a2, log tau2].
# `_nelder_mead`/`_PENALTY` now live in optimizers.py, shared with
# methods/offline_generic.py's GenericOfflineModeler (every other method).


class OfflineHeuristicModeler:
    """Nelder–Mead optimizer over a 4-parameter bi-exponential decay.

    A genuine derivative-free optimizer (not a stub) used as a test double so
    the whole pipeline runs without an API key. It emits numpy-only code — each
    proposed point is evaluated by the sandbox, and the returned L2 norm drives
    the simplex.
    """

    IS_OFFLINE = True  # orchestrator's duck-typed marker for the offline iteration cap

    def __init__(self, data_summary: dict[str, Any]) -> None:
        # Initial guess (log10). Offset from a typical truth so there is real
        # work to do; Nelder–Mead handles the parameter coupling from here.
        x0 = [math.log10(5.0), -2.7, math.log10(3.0), -1.5]
        self._search = _nelder_mead(x0, step=0.5)
        self._pending = self._search.send(None)  # prime to the first vertex

    def propose(self, iteration: int, data_summary: dict[str, Any], feedback: Feedback) -> str:
        if iteration > 0:
            value = feedback.get("l2") if feedback else None
            if value is None or not math.isfinite(value):
                value = _PENALTY
            self._pending = self._search.send(value)
        return self._code_for(self._pending)

    @staticmethod
    def _expand(p: list[float]) -> tuple[float, float, float, float]:
        a1, tau1, a2, tau2 = (10.0 ** v for v in p)
        return a1, tau1, a2, tau2

    def _code_for(self, p: list[float]) -> str:
        a1, tau1, a2, tau2 = self._expand(p)
        return (
            "import numpy as np\n"
            f"a1, tau1, a2, tau2 = {a1!r}, {tau1!r}, {a2!r}, {tau2!r}\n"
            "d_pred = a1 * np.exp(-t_obs / tau1) + a2 * np.exp(-t_obs / tau2)\n"
            "m = {\n"
            f"    'res': [{a1!r}, {a2!r}],\n"
            f"    'depth': [{tau1!r}, {tau2!r}],\n"
            f"    'params': {{'a1': {a1!r}, 'tau1': {tau1!r}, 'a2': {a2!r}, 'tau2': {tau2!r}}},\n"
            "}\n"
        )


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #


def _offline_modeler(data_type: str, data_summary: dict[str, Any]) -> Modeler:
    """TDEM keeps its own bi-exponential optimizer; every other registered
    method is solved by the generic Nelder-Mead-over-any-MethodSpec search."""
    if data_type == "TDEM":
        return OfflineHeuristicModeler(data_summary)

    from .methods import METHOD_REGISTRY  # lazy: avoids a cycle at module load
    from .methods.offline_generic import GenericOfflineModeler

    spec = METHOD_REGISTRY.get(data_type)
    if spec is None:
        raise ValueError(f"no MethodSpec registered for dataType {data_type!r}")
    return GenericOfflineModeler(spec, data_summary)


def build_modeler(data_type: str, data_summary: dict[str, Any]) -> Modeler:
    mode = settings.agent_mode.lower()
    has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    if mode == "offline":
        logger.info("Using offline modeler for %s (AGENT_MODE=offline)", data_type)
        return _offline_modeler(data_type, data_summary)

    if mode == "llm" or (mode == "auto" and has_key):
        logger.info("Using GeminiModeler (%s) for %s", settings.gemini_model, data_type)
        return GeminiModeler(data_type)

    logger.warning(
        "GEMINI_API_KEY not set — falling back to the offline modeler. "
        "Set the key (or AGENT_MODE=llm) to use Gemini."
    )
    return _offline_modeler(data_type, data_summary)

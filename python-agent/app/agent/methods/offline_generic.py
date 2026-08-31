"""A single Nelder-Mead-over-any-MethodSpec optimizer.

Replaces the need to hand-write an OfflineHeuristicModeler subclass per
method: every registered method (other than TDEM, which keeps its own
bi-exponential OfflineHeuristicModeler) is solved by the SAME generic
search, parameterized entirely by the MethodSpec's `x0` / `expand` /
`render_code`.
"""

from __future__ import annotations

import math
from typing import Any

from ..optimizers import _PENALTY, _nelder_mead
from .registry import MethodSpec


class GenericOfflineModeler:
    """Real (not-a-stub) derivative-free optimizer, driven by a MethodSpec.

    No API key needed — emits numpy-only code via `spec.render_code`, exactly
    like OfflineHeuristicModeler does for TDEM.
    """

    IS_OFFLINE = True  # orchestrator's duck-typed marker for the offline iteration cap

    def __init__(self, spec: MethodSpec, data_summary: dict[str, Any]) -> None:
        self._spec = spec
        self._search = _nelder_mead(spec.x0, step=0.5)
        self._pending = self._search.send(None)

    def propose(
        self, iteration: int, data_summary: dict[str, Any], feedback: dict[str, Any] | None
    ) -> str:
        if iteration > 0:
            value = feedback.get("l2") if feedback else None
            if value is None or not math.isfinite(value):
                value = _PENALTY
            self._pending = self._search.send(value)
        params = self._spec.expand(self._pending)
        return self._spec.render_code(params)

"""End-to-end offline convergence test (Step 4).

Runs the real Nelder-Mead optimizer through the real sandbox against a known
bi-exponential truth. Subprocess-heavy (~30s) so it is marked `slow`; run with
`pytest -m slow` (or unmarked to include it).

Uses a tight relative-misfit tolerance so parameter recovery is precise (the
default 0.05 tolerance only pins the fit, not the parameters).
"""

from types import SimpleNamespace

import numpy as np
import pytest

import app.agent.orchestrator as orch
from app.agent.modeler import OfflineHeuristicModeler
from app.agent.orchestrator import run_inversion_agent

TRUTH = {"a1": 10.0, "tau1": 2.0e-3, "a2": 2.0, "tau2": 2.0e-2}


@pytest.mark.slow
def test_offline_modeler_converges_to_truth(monkeypatch):
    monkeypatch.setattr(
        orch,
        "settings",
        SimpleNamespace(
            l2_tolerance=0.005,
            max_iterations=30,
            offline_max_iterations=400,
            sandbox_timeout_s=10,
        ),
    )

    t = np.logspace(-4, -1, 40)
    d = (
        TRUTH["a1"] * np.exp(-t / TRUTH["tau1"])
        + TRUTH["a2"] * np.exp(-t / TRUTH["tau2"])
    )

    modeler = OfflineHeuristicModeler({"n": int(t.size)})
    result = run_inversion_agent("slow-test", "TDEM", t, d, modeler=modeler)

    assert result.status == "converged"
    assert result.l2_norm_error is not None
    assert result.l2_norm_error <= 0.005

    # Recovered parameters should be close to the truth.
    params = result.final_model["params"]
    assert params["a1"] == pytest.approx(TRUTH["a1"], rel=0.05)
    assert params["tau1"] == pytest.approx(TRUTH["tau1"], rel=0.10)

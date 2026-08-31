"""Shared contract test for every registered MethodSpec.

For each method: generate the synthetic truth curve from `forward_fn`, render
the SAME truth params through `render_code` into a sandbox-runnable script,
run it through the REAL sandbox subprocess, and confirm the misfit comes back
essentially zero. This proves `forward_fn` (used for truth generation) and
`render_code` (used by the offline solver, and matching what the LLM prompt
asks for) agree, and exercises the real d_pred/m contract for every method —
one parametrized test instead of an 11-file duplicate of test_empymod_contract.py.
"""

import numpy as np
import pytest

from app.agent.methods import METHOD_REGISTRY
from tools.sandbox import execute_generated_model


@pytest.mark.parametrize("method_id", sorted(METHOD_REGISTRY))
def test_truth_params_reproduce_synthetic_curve_through_sandbox(method_id):
    spec = METHOD_REGISTRY[method_id]
    scenario = spec.synthetic
    x_obs = np.asarray(scenario.x_obs, dtype=float)
    truth = scenario.truth_params

    aux = (
        {k: np.asarray(v, dtype=float) for k, v in scenario.aux_arrays.items()}
        if scenario.aux_arrays
        else None
    )
    d_obs = spec.forward_fn(x_obs, truth, aux) if spec.needs_aux else spec.forward_fn(x_obs, truth)
    code = spec.render_code(truth)

    result = execute_generated_model(
        code, x_obs, d_obs, timeout_s=spec.sandbox_timeout_s or 20, aux=aux
    )
    assert result["ok"] is True, result.get("error")
    assert result["l2_norm"] == pytest.approx(0.0, abs=1e-6)

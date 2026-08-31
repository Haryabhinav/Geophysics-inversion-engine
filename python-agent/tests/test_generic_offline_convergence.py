"""End-to-end convergence test for GenericOfflineModeler, parametrized over
every registered method except TDEM (which keeps its own dedicated
test_offline_convergence.py, testing OfflineHeuristicModeler by name).

Real subprocess-per-iteration cost, same as test_offline_convergence.py —
marked slow.
"""

import numpy as np
import pytest

from app.agent.methods import METHOD_REGISTRY
from app.agent.methods.offline_generic import GenericOfflineModeler
from app.agent.orchestrator import run_inversion_agent


@pytest.mark.slow
@pytest.mark.parametrize("method_id", sorted(m for m in METHOD_REGISTRY if m != "TDEM"))
def test_generic_offline_modeler_converges_to_truth(method_id):
    spec = METHOD_REGISTRY[method_id]
    x_obs = np.asarray(spec.synthetic.x_obs, dtype=float)
    aux = (
        {k: np.asarray(v, dtype=float) for k, v in spec.synthetic.aux_arrays.items()}
        if spec.synthetic.aux_arrays
        else None
    )
    d_obs = (
        spec.forward_fn(x_obs, spec.synthetic.truth_params, aux)
        if spec.needs_aux
        else spec.forward_fn(x_obs, spec.synthetic.truth_params)
    )

    modeler = GenericOfflineModeler(spec, {})
    result = run_inversion_agent(
        f"slow-test-{method_id}", method_id, x_obs, d_obs, modeler=modeler, aux=aux
    )

    assert result.status == "converged", (
        f"{method_id} did not converge: status={result.status}, "
        f"l2={result.l2_norm_error}, message={result.message}"
    )

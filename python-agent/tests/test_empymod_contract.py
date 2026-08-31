"""Contract test for the production forward-model path (Step 3/4).

Runs a real `empymod` 1-D layered-earth TDEM forward model through the sandbox
— the same kind of code the Gemini modeler is asked to author. This guards
the `d_pred` / `m` contract the agent depends on, without needing the LLM.

Skipped automatically if `empymod` is not installed.
"""

import numpy as np
import pytest

from tools.sandbox import execute_generated_model

pytest.importorskip("empymod")

# A verified empymod step-on TDEM response over a 3-layer earth.
EMPYMOD_CODE = """
import numpy as np
import empymod

resp = empymod.dipole(
    src=[0, 0, 0],
    rec=[100, 0, 0],
    depth=[0, 30, 100],
    res=[2e14, 100, 10, 100],
    freqtime=t_obs,
    signal=1,
    verb=0,
)
d_pred = np.asarray(resp).reshape(-1)
m = {'res': [100.0, 10.0, 100.0], 'depth': [0.0, 30.0, 100.0]}
"""


@pytest.mark.needs_empymod
def test_empymod_forward_model_through_sandbox():
    t = np.logspace(-5, -2, 20)
    d = np.linspace(1.0, 2.0, 20)  # nonzero observed so the relative misfit is finite

    result = execute_generated_model(EMPYMOD_CODE, t, d, timeout_s=60)

    assert result["ok"] is True, result.get("error")
    assert np.isfinite(result["l2_norm"])
    assert "res" in result["m_current"]
    assert "depth" in result["m_current"]


# The single-script scipy inversion the improved prompt asks Gemini to write:
# fit the earth model to d_obs inside ONE sandbox run (so one LLM call converges).
SCIPY_INVERSION_CODE = """
import numpy as np, empymod
from scipy.optimize import least_squares

def forward(depth, res):
    return np.asarray(empymod.dipole(
        src=[0, 0, 0.001], rec=[100, 0, 0.001],
        depth=depth, res=res, freqtime=t_obs, signal=-1, verb=0)).reshape(-1)

def residual(p):  # p = [log10 res1, log10 res2, log10 depth1]
    res = [2e14, 10 ** p[0], 10 ** p[1]]
    depth = [0.0, 10 ** p[2]]
    return forward(depth, res) - d_obs

x0 = np.array([np.log10(30.0), np.log10(300.0), np.log10(60.0)])
sol = least_squares(residual, x0, method='lm', max_nfev=300)
res = [2e14, 10 ** sol.x[0], 10 ** sol.x[1]]
depth = [0.0, 10 ** sol.x[2]]
d_pred = forward(depth, res)
m = {'res': res, 'depth': depth}
"""


@pytest.mark.needs_empymod
def test_scipy_one_shot_inversion_converges():
    """A single sandbox execution should invert the earth model below tolerance,
    validating that one Gemini call can converge (call-efficiency fix)."""
    t = np.logspace(-5, -2, 25)
    d = np.asarray(
        __import__("empymod").dipole(
            src=[0, 0, 0.001], rec=[100, 0, 0.001], depth=[0, 40],
            res=[2e14, 50, 200], freqtime=t, signal=-1, verb=0,
        )
    ).reshape(-1)

    result = execute_generated_model(SCIPY_INVERSION_CODE, t, d, timeout_s=30)

    assert result["ok"] is True, result.get("error")
    assert result["l2_norm"] <= 0.05  # converged in a single run

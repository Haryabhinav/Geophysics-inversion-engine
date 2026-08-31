"""Registers TDEM as a MethodSpec.

TDEM keeps its existing, dedicated code paths (OfflineHeuristicModeler's
bi-exponential test double, empymod-based GeminiModeler prompt) completely
unchanged — this registration exists only so TDEM participates in the
registry-driven parts of the pipeline (tolerance/iteration-cap lookup, the
Interpretation Agent's glossary, and the shared parametrized contract test),
without duplicating any of its existing behavior.
"""

from __future__ import annotations

import numpy as np

from ... import prompts
from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register

_SRC = [0, 0, 0.001]
_REC = [100, 0, 0.001]


def _forward(t_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    import empymod  # lazy: methods package import must not hard-require empymod

    res = [2e14, p["res1"], p["res2"]]
    depth = [0, p["depth1"]]
    return np.asarray(
        empymod.dipole(src=_SRC, rec=_REC, depth=depth, res=res, freqtime=t_obs, signal=-1, verb=0)
    ).reshape(-1)


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np, empymod\n"
        f"res = [2e14, {p['res1']!r}, {p['res2']!r}]\n"
        f"depth = [0, {p['depth1']!r}]\n"
        f"d_pred = np.asarray(empymod.dipole(src={_SRC!r}, rec={_REC!r}, "
        "depth=depth, res=res, freqtime=t_obs, signal=-1, verb=0)).reshape(-1)\n"
        "m = {'res': res, 'depth': depth}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_res1, log_res2, depth1 = x
    return {"res1": 10.0**log_res1, "res2": 10.0**log_res2, "depth1": depth1}


TDEM_SPEC = register(
    MethodSpec(
        id="TDEM",
        display_name="Time-Domain EM (layered earth)",
        x_label="time (s)",
        d_label="amplitude",
        system_prompt_template=prompts.SYSTEM_PROMPT.format(data_type="TDEM"),
        params=[
            ParamSpec("res1", "Ohm-m", "overburden resistivity", (1.0, 1000.0)),
            ParamSpec("res2", "Ohm-m", "basement resistivity", (1.0, 1000.0)),
            ParamSpec("depth1", "m", "depth to basement", (5.0, 200.0), log_space=False),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(50.0), np.log10(200.0), 40.0],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"res1": 50.0, "res2": 200.0, "depth1": 40.0},
            x_obs=list(np.logspace(-5, -2, 25)),
        ),
    )
)

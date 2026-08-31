"""Seismic refraction — layered velocity model from travel-time curve.

Classic head-wave / crossover-distance refraction formula (Kearey, Brooks &
Hill, *An Introduction to Geophysical Exploration*; Telford, Geldart &
Sheriff 1990 §4.4) for a single interface, V1 < V2:

    t(x) = min(x/V1,  x/V2 + 2*h*cos(theta_c)/V1),   theta_c = asin(V1/V2)

The piecewise min() has a non-smooth kink at the crossover offset — v1 is
scoped to a single 2-layer interface (matching TDEM's own 2-layer scoping)
and synthetic offsets are chosen to clearly straddle the crossover distance
so both the direct-wave and head-wave branches carry real signal.
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register


def _forward(x_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    v1, v2, h = p["v1"], p["v2"], p["h"]
    theta_c = np.arcsin(v1 / v2)
    t_direct = x_obs / v1
    t_head = x_obs / v2 + 2 * h * np.cos(theta_c) / v1
    return np.minimum(t_direct, t_head)


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"v1, v2, h = {p['v1']!r}, {p['v2']!r}, {p['h']!r}\n"
        "theta_c = np.arcsin(v1 / v2)\n"
        "t_direct = t_obs / v1\n"
        "t_head = t_obs / v2 + 2 * h * np.cos(theta_c) / v1\n"
        "d_pred = np.minimum(t_direct, t_head)\n"
        "m = {'params': {'v1': v1, 'v2': v2, 'h': h}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_v1, log_v2, log_h = x
    return {"v1": 10.0**log_v1, "v2": 10.0**log_v2, "h": 10.0**log_h}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given an observed
seismic refraction travel-time curve as two 1-D arrays already defined in
your script as `t_obs` (source-receiver offset, meters) and `d_obs`
(first-arrival travel time, seconds).

The subsurface is a single layer (velocity V1) over a faster half-space
(velocity V2 > V1) at depth h. The forward model is the classic direct-wave /
head-wave refraction formula:

    theta_c = arcsin(V1 / V2)
    t(x) = min(x/V1,  x/V2 + 2*h*cos(theta_c)/V1)

Note: this piecewise min() has a kink at the crossover offset, which can make
gradient-based fitting noisy near that point — a soft-min approximation
(e.g. -logsumexp(-k*t_direct, -k*t_head)/k for a large k) is an available
numpy-only smoothing fallback if least_squares struggles to converge.

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [log10(V1), log10(V2), log10(h)] (keeps all positive).
2. residual(p) = min(t_obs/V1, t_obs/V2 + 2*h*cos(arcsin(V1/V2))/V1) - d_obs.
3. Fit with least_squares(residual, x0_guess, method='lm', max_nfev=300).
4. Set d_pred = best-fit forward response, m = {'params': {'v1':..., 'v2':..., 'h':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- t_obs / d_obs are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="SEISMIC_REFRACTION",
        display_name="Seismic refraction — 2-layer velocity model",
        x_label="source-receiver offset (m)",
        d_label="first-arrival travel time (s)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("v1", "m/s", "upper-layer P-wave velocity", (300.0, 2000.0)),
            ParamSpec("v2", "m/s", "half-space P-wave velocity", (1500.0, 6000.0)),
            ParamSpec("h", "m", "depth to interface", (2.0, 100.0)),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(500.0), np.log10(2500.0), np.log10(25.0)],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"v1": 800.0, "v2": 3000.0, "h": 15.0},
            x_obs=list(np.linspace(2, 100, 25)),
        ),
    )
)

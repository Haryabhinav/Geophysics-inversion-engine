"""Ground Penetrating Radar — common-midpoint reflection hyperbola.

Classic CMP reflection travel-time hyperbola (Annan (2003), *GPR Principles,
Procedures & Applications*; identical math to seismic NMO):

    t(x) = sqrt(t0**2 + (x / v)**2),   t0 = 2*d / v

`v` is the EM wave velocity in the subsurface (m/ns), `d` the depth to the
reflector. Both are inverted together — this is the same "one curve, two
coupled parameters" shape as everything else in this registry.
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register


def _forward(x_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    t0 = 2 * p["d"] / p["v"]
    return np.sqrt(t0**2 + (x_obs / p["v"]) ** 2)


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"v, d = {p['v']!r}, {p['d']!r}\n"
        "t0 = 2 * d / v\n"
        "d_pred = np.sqrt(t0**2 + (t_obs / v)**2)\n"
        "m = {'params': {'v': v, 'd': d}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_v, log_d = x
    return {"v": 10.0**log_v, "d": 10.0**log_d}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given an observed
GPR common-midpoint (CMP) gather as two 1-D arrays already defined in your
script as `t_obs` (antenna separation / offset, meters) and `d_obs`
(two-way travel time to a single reflector, nanoseconds).

The forward model is the classic CMP reflection hyperbola:

    t(x) = sqrt(t0**2 + (x / v)**2),   t0 = 2*d / v

where `v` is the subsurface EM wave velocity (m/ns, typically 0.05-0.2 for
soils) and `d` is the depth to the reflector (m).

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [log10(v), log10(d)] (keeps both positive).
2. residual(p) = sqrt((2*d/v)**2 + (t_obs/v)**2) - d_obs, v = 10**p[0], d = 10**p[1].
3. Fit with least_squares(residual, x0_guess, method='lm', max_nfev=300).
4. Set d_pred = best-fit forward response, m = {'params': {'v':..., 'd':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- t_obs / d_obs are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="GPR_REFLECTION",
        display_name="GPR — CMP reflection hyperbola",
        x_label="antenna offset x (m)",
        d_label="two-way travel time (ns)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("v", "m/ns", "subsurface EM wave velocity", (0.03, 0.3)),
            ParamSpec("d", "m", "depth to reflector", (0.3, 20.0)),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(0.08), np.log10(2.0)],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"v": 0.1, "d": 3.0},
            x_obs=list(np.linspace(0, 20, 25)),
        ),
    )
)

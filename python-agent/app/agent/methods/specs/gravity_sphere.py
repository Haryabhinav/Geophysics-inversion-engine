"""Gravity — buried sphere anomaly.

Classic textbook buried-sphere gravity anomaly (Telford, Geldart & Sheriff,
*Applied Geophysics* 2nd ed., eq. 2.20):

    g_z(x) = G * M * z / ((x - x0)**2 + z**2)**1.5

Mass and depth trade off (you can't separately resolve G*M and z from the
anomaly shape alone without extra constraints) so we lump them into one
amplitude K = G*M, exactly like TDEM's res/depth trade-off.
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register


def _forward(x_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    return p["K"] * p["z"] / ((x_obs - p["x0"]) ** 2 + p["z"] ** 2) ** 1.5


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"K, z, x0 = {p['K']!r}, {p['z']!r}, {p['x0']!r}\n"
        "d_pred = K * z / ((t_obs - x0)**2 + z**2)**1.5\n"
        "m = {'params': {'K': K, 'z': z, 'x0': x0}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_k, z, x0 = x
    return {"K": 10.0**log_k, "z": z, "x0": x0}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given an observed
gravity profile as two 1-D arrays already defined in your script as `t_obs`
(horizontal survey position, meters) and `d_obs` (residual gravity anomaly, mGal).

The anomaly is caused by a single buried compact (spherical) body. The
forward model is the classic buried-sphere gravity anomaly:

    g_z(x) = G * M * z / ((x - x0)**2 + z**2)**1.5

Lump G*M into one amplitude constant K (you cannot separately resolve mass
and depth without extra constraints — this is a well-known gravity
depth/mass trade-off, analogous to the resistivity/depth equivalence in EM).

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [log10(K), z, x0].
2. residual(p) = K*z/((t_obs-x0)**2+z**2)**1.5 - d_obs, with K = 10**p[0].
3. Fit with least_squares(residual, x0_guess, method='lm', max_nfev=300).
4. Set d_pred = best-fit forward response, m = {'params': {'K':..., 'z':..., 'x0':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- t_obs / d_obs are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="GRAVITY_SPHERE",
        display_name="Gravity — buried sphere",
        x_label="survey position x (m)",
        d_label="residual gravity anomaly (mGal)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("K", "mGal*m^2", "lumped G*mass amplitude", (1e0, 1e6)),
            ParamSpec("z", "m", "depth to sphere center", (5.0, 200.0), log_space=False),
            ParamSpec("x0", "m", "horizontal position of sphere", (-100.0, 100.0), log_space=False),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(5000.0), 30.0, 0.0],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"K": 8000.0, "z": 25.0, "x0": 0.0},
            x_obs=list(np.linspace(-100, 100, 41)),
        ),
    )
)

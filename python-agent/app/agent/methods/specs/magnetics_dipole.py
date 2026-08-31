"""Magnetics — buried dipole total-field anomaly.

Vertical-dipole approximation to the total-field magnetic anomaly (valid at
high magnetic latitude, where the inducing field is near-vertical) — Blakely
(1995), *Potential Theory in Gravity and Magnetic Applications*:

    dT(x) = K * (2*z**2 - (x - x0)**2) / ((x - x0)**2 + z**2)**2.5

K lumps mu_0*m/(4*pi) (dipole moment) — same amplitude/depth trade-off as
gravity's buried sphere.
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register


def _forward(x_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    dx = x_obs - p["x0"]
    return p["K"] * (2 * p["z"] ** 2 - dx**2) / (dx**2 + p["z"] ** 2) ** 2.5


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"K, z, x0 = {p['K']!r}, {p['z']!r}, {p['x0']!r}\n"
        "dx = t_obs - x0\n"
        "d_pred = K * (2*z**2 - dx**2) / (dx**2 + z**2)**2.5\n"
        "m = {'params': {'K': K, 'z': z, 'x0': x0}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_k, z, x0 = x
    return {"K": 10.0**log_k, "z": z, "x0": x0}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given an observed
magnetic profile as two 1-D arrays already defined in your script as `t_obs`
(horizontal survey position, meters) and `d_obs` (total-field anomaly, nT).

The anomaly is caused by a single buried compact (dipole-like) body at high
magnetic latitude (near-vertical inducing field). The forward model is the
vertical-dipole total-field anomaly approximation:

    dT(x) = K * (2*z**2 - (x - x0)**2) / ((x - x0)**2 + z**2)**2.5

K lumps the dipole-moment amplitude (mu_0*m/(4*pi)) — you cannot separately
resolve moment and depth without extra constraints, the same amplitude/depth
trade-off gravity has for a buried sphere.

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [log10(K), z, x0].
2. residual(p) = K*(2*z**2-dx**2)/(dx**2+z**2)**2.5 - d_obs, dx = t_obs - x0, K = 10**p[0].
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
        id="MAGNETICS_DIPOLE",
        display_name="Magnetics — buried dipole",
        x_label="survey position x (m)",
        d_label="total-field anomaly (nT)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("K", "nT*m^3", "lumped dipole-moment amplitude", (1e0, 1e8)),
            ParamSpec("z", "m", "depth to body", (5.0, 150.0), log_space=False),
            ParamSpec("x0", "m", "horizontal position of body", (-100.0, 100.0), log_space=False),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(50000.0), 25.0, 0.0],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"K": 50000.0, "z": 20.0, "x0": 0.0},
            x_obs=list(np.linspace(-100, 100, 41)),
        ),
    )
)

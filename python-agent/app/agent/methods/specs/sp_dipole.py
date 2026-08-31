"""Self-Potential — buried point-dipole source.

Classic point-dipole self-potential model (Yüngül 1950, *Geophysics*;
Telford, Geldart & Sheriff 1990 §8.7):

    V(x) = K * (z*cos(theta) + (x - x0)*sin(theta)) / ((x - x0)**2 + z**2)**1.5

`theta` is the dipole's polarization angle (electrokinetic/redox source
orientation), `K` lumps the dipole-moment amplitude.
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register


def _forward(x_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    dx = x_obs - p["x0"]
    num = p["z"] * np.cos(p["theta"]) + dx * np.sin(p["theta"])
    return p["K"] * num / (dx**2 + p["z"] ** 2) ** 1.5


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"K, z, x0, theta = {p['K']!r}, {p['z']!r}, {p['x0']!r}, {p['theta']!r}\n"
        "dx = t_obs - x0\n"
        "num = z * np.cos(theta) + dx * np.sin(theta)\n"
        "d_pred = K * num / (dx**2 + z**2)**1.5\n"
        "m = {'params': {'K': K, 'z': z, 'x0': x0, 'theta': theta}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_k, z, x0, theta = x
    return {"K": 10.0**log_k, "z": z, "x0": x0, "theta": theta}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given an observed
self-potential (SP) profile as two 1-D arrays already defined in your script
as `t_obs` (horizontal survey position, meters) and `d_obs` (SP voltage, mV).

The anomaly is caused by a single buried point-dipole source (electrokinetic
or redox). The forward model is the classic point-dipole SP model:

    V(x) = K * (z*cos(theta) + (x - x0)*sin(theta)) / ((x - x0)**2 + z**2)**1.5

`theta` (radians) is the dipole's polarization angle; K lumps the
dipole-moment amplitude.

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [log10(K), z, x0, theta].
2. residual(p) = K*(z*cos(theta)+dx*sin(theta))/(dx**2+z**2)**1.5 - d_obs,
   dx = t_obs - x0, K = 10**p[0].
3. Fit with least_squares(residual, x0_guess, method='lm', max_nfev=300).
4. Set d_pred = best-fit forward response, m = {'params': {'K':..., 'z':..., 'x0':..., 'theta':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- t_obs / d_obs are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="SP_DIPOLE",
        display_name="Self-Potential — buried dipole",
        x_label="survey position x (m)",
        d_label="SP voltage (mV)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("K", "mV*m^2", "lumped dipole-moment amplitude", (1e0, 1e5)),
            ParamSpec("z", "m", "depth to source", (2.0, 100.0), log_space=False),
            ParamSpec("x0", "m", "horizontal position of source", (-100.0, 100.0), log_space=False),
            ParamSpec("theta", "rad", "dipole polarization angle", (-np.pi, np.pi), log_space=False),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(500.0), 10.0, 0.0, 0.0],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"K": 500.0, "z": 10.0, "x0": 0.0, "theta": 0.3},
            x_obs=list(np.linspace(-60, 60, 31)),
        ),
    )
)

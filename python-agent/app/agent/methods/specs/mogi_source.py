"""Geodetic deformation — Mogi point-source model.

Classic point pressure-source surface deformation model (Mogi 1958, *Bull.
Earthquake Res. Inst.* 36:99-134) — used in volcanology and reservoir
(magma/CO2/oil) monitoring:

    u_z(x) = C * d / ((x - x0)**2 + d**2)**1.5,   C = (1-nu)*dV/pi

`d` is the source depth, `dV` the volume change; `nu` (Poisson's ratio) and
`dV` trade off exactly like every other amplitude/depth pair in this
registry, so we lump them into C.
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register


def _forward(x_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    return p["C"] * p["d"] / ((x_obs - p["x0"]) ** 2 + p["d"] ** 2) ** 1.5


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"C, d, x0 = {p['C']!r}, {p['d']!r}, {p['x0']!r}\n"
        "d_pred = C * d / ((t_obs - x0)**2 + d**2)**1.5\n"
        "m = {'params': {'C': C, 'd': d, 'x0': x0}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_c, log_d, x0 = x
    return {"C": 10.0**log_c, "d": 10.0**log_d, "x0": x0}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given an observed
surface deformation profile (e.g. from InSAR or GPS) as two 1-D arrays
already defined in your script as `t_obs` (horizontal survey position,
meters) and `d_obs` (vertical surface displacement, meters).

The deformation is caused by a single point pressure source at depth (a
magma chamber, or a fluid reservoir undergoing volume change). The forward
model is the classic Mogi (1958) point-source model:

    u_z(x) = C * d / ((x - x0)**2 + d**2)**1.5

C lumps (1-nu)*dV/pi (Poisson's ratio and volume change trade off with
depth) — you cannot separately resolve them without extra constraints.

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [log10(C), log10(d), x0] (log-space keeps C, d positive).
2. residual(p) = C*d/((t_obs-x0)**2+d**2)**1.5 - d_obs, C = 10**p[0], d = 10**p[1].
3. Fit with least_squares(residual, x0_guess, method='lm', max_nfev=300).
4. Set d_pred = best-fit forward response, m = {'params': {'C':..., 'd':..., 'x0':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- t_obs / d_obs are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="MOGI_SOURCE",
        display_name="Geodetic deformation — Mogi source",
        x_label="survey position x (m)",
        d_label="vertical surface displacement (m)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("C", "m^3", "lumped (1-nu)*volume-change amplitude", (1e2, 1e7)),
            ParamSpec("d", "m", "source depth", (500.0, 10000.0)),
            ParamSpec("x0", "m", "horizontal position of source", (-5000.0, 5000.0), log_space=False),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(2e5), np.log10(2500.0), 0.0],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"C": 1e5, "d": 3000.0, "x0": 0.0},
            x_obs=list(np.linspace(-5000, 5000, 41)),
        ),
    )
)

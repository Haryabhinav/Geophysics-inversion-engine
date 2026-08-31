"""Electrical Resistivity Tomography — 2-layer Wenner sounding curve.

Classic 2-layer Wenner apparent-resistivity sounding (Keller & Frischknecht
1966, *Electrical Methods in Geophysical Prospecting*; Telford, Geldart &
Sheriff 1990 §8):

    rho_a(a) / rho1 = 1 + 4 * sum_{n=1..N} k^n * [
        (1 + (2*n*h/a)**2)**-0.5 - (4 + (2*n*h/a)**2)**-0.5
    ],   k = (rho2 - rho1) / (rho2 + rho1)

This is an infinite series, truncated here at 60 terms (`k**n` decays
geometrically for moderate resistivity contrast, so 60 terms is comfortably
converged for the bounded contrast this method's ParamSpec targets — a very
extreme rho2/rho1 ratio would push |k| -> 1 and slow convergence, which is
why the parameter bounds below stay moderate rather than open-ended).
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register

_N_TERMS = 60


def _forward(x_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    rho1, rho2, h = p["rho1"], p["rho2"], p["h"]
    k = (rho2 - rho1) / (rho2 + rho1)
    total = np.zeros_like(x_obs)
    for n in range(1, _N_TERMS + 1):
        ratio = 2 * n * h / x_obs
        total += k**n * ((1 + ratio**2) ** -0.5 - (4 + ratio**2) ** -0.5)
    return rho1 * (1 + 4 * total)


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"rho1, rho2, h = {p['rho1']!r}, {p['rho2']!r}, {p['h']!r}\n"
        "k = (rho2 - rho1) / (rho2 + rho1)\n"
        "total = np.zeros_like(t_obs)\n"
        f"for n in range(1, {_N_TERMS + 1}):\n"
        "    ratio = 2 * n * h / t_obs\n"
        "    total += k**n * ((1 + ratio**2)**-0.5 - (4 + ratio**2)**-0.5)\n"
        "d_pred = rho1 * (1 + 4 * total)\n"
        "m = {'params': {'rho1': rho1, 'rho2': rho2, 'h': h}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_rho1, log_rho2, log_h = x
    return {"rho1": 10.0**log_rho1, "rho2": 10.0**log_rho2, "h": 10.0**log_h}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given an observed
Wenner-array electrical resistivity sounding as two 1-D arrays already
defined in your script as `t_obs` (electrode spacing a, meters) and `d_obs`
(apparent resistivity, Ohm-m).

The subsurface is two layers: resistivity rho1 to depth h, then a half-space
of resistivity rho2. The forward model is the classic 2-layer Wenner
sounding formula (an infinite series, truncate at 60 terms):

    k = (rho2 - rho1) / (rho2 + rho1)
    rho_a(a) = rho1 * (1 + 4 * sum_{n=1}^{60} k**n *
        ((1 + (2*n*h/a)**2)**-0.5 - (4 + (2*n*h/a)**2)**-0.5))

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [log10(rho1), log10(rho2), log10(h)].
2. Implement the series sum above as a vectorized loop over n=1..60.
3. residual(p) = rho_a_model(p) - d_obs.
4. Fit with least_squares(residual, x0_guess, method='lm', max_nfev=300).
5. Set d_pred = best-fit forward response, m = {'params': {'rho1':..., 'rho2':..., 'h':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- t_obs / d_obs are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="ERT_WENNER",
        display_name="Electrical Resistivity (ERT, Wenner sounding)",
        x_label="electrode spacing a (m)",
        d_label="apparent resistivity (Ohm-m)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("rho1", "Ohm-m", "upper-layer resistivity", (10.0, 200.0)),
            ParamSpec("rho2", "Ohm-m", "half-space resistivity", (50.0, 500.0)),
            ParamSpec("h", "m", "depth to interface", (2.0, 100.0)),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(80.0), np.log10(150.0), np.log10(10.0)],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"rho1": 50.0, "rho2": 300.0, "h": 20.0},
            x_obs=list(np.logspace(1, np.log10(250), 30)),
        ),
    )
)

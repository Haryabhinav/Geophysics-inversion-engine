"""Induced Polarization — Cole-Cole chargeability decay (stretched-exponential approximation).

The rigorous Cole-Cole time-domain step response has no elementary closed
form (it needs Mittag-Leffler functions / numerical Laplace inversion —
Pelton et al. 1978). This registers the pragmatic, dependency-free
stretched-exponential (Kohlrausch-Williams-Watts) approximation instead:

    m(t) = m0 * exp(-(t / tau)**c)

This is a genuine physics simplification (not just "fewer layers" like
TDEM/ERT/MT's scoping), documented here rather than silently passed off as
the full Cole-Cole model.
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register


def _forward(t_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    return p["m0"] * np.exp(-((t_obs / p["tau"]) ** p["c"]))


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"m0, tau, c = {p['m0']!r}, {p['tau']!r}, {p['c']!r}\n"
        "d_pred = m0 * np.exp(-(t_obs / tau)**c)\n"
        "m = {'params': {'m0': m0, 'tau': tau, 'c': c}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_m0, log_tau, log_c = x
    return {"m0": 10.0**log_m0, "tau": 10.0**log_tau, "c": 10.0**log_c}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given an observed
induced-polarization (IP) chargeability decay as two 1-D arrays already
defined in your script as `t_obs` (time after current shutoff, seconds) and
`d_obs` (chargeability, mV/V).

The forward model is a stretched-exponential (Kohlrausch-Williams-Watts)
approximation to the Cole-Cole decay:

    m(t) = m0 * exp(-(t / tau)**c)

where m0 is the initial chargeability, tau the decay time constant, and c a
dimensionless stretching exponent (typically 0 < c <= 1).

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [log10(m0), log10(tau), log10(c)] (keeps all positive).
2. residual(p) = m0*exp(-(t_obs/tau)**c) - d_obs.
3. Fit with least_squares(residual, x0_guess, method='lm', max_nfev=300).
4. Set d_pred = best-fit forward response, m = {'params': {'m0':..., 'tau':..., 'c':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- t_obs / d_obs are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="IP_COLE_COLE",
        display_name="Induced Polarization — Cole-Cole decay (stretched-exp. approx.)",
        x_label="time after current shutoff (s)",
        d_label="chargeability (mV/V)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("m0", "mV/V", "initial chargeability", (1.0, 100.0)),
            ParamSpec("tau", "s", "decay time constant", (0.05, 5.0)),
            ParamSpec("c", "dimensionless", "stretching exponent", (0.2, 1.0)),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(15.0), np.log10(0.3), np.log10(0.4)],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"m0": 25.0, "tau": 0.5, "c": 0.6},
            x_obs=list(np.linspace(0.01, 3.0, 25)),
        ),
    )
)

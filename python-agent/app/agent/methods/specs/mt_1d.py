"""Magnetotellurics — 1D, 2-layer apparent resistivity sounding.

Classic Wait (1954) recursive layered-earth impedance, specialized to
exactly 2 layers (Simpson & Bahr 2005, *Practical Magnetotellurics*):

    Z1 = sqrt(i*omega*mu0*rho1)      (layer-1 intrinsic impedance)
    k1 = sqrt(i*omega*mu0/rho1)      (layer-1 wavenumber)
    Z2 = sqrt(i*omega*mu0*rho2)      (half-space intrinsic impedance)
    Z_top = Z1 * (Z2 + Z1*tanh(i*k1*h1)) / (Z1 + Z2*tanh(i*k1*h1))
    rho_a(f) = |Z_top|**2 / (omega*mu0)

**Scope note:** a real MT sounding reports both apparent resistivity AND
phase. Combining two differently-scaled curves into one `d_obs` needs a
normalization scheme so neither dominates the misfit — flagged during
planning as the trickiest packaging problem in this batch. v1 ships with
apparent resistivity only (a real, complete, independently useful MT
deliverable — many textbook MT exercises start exactly here), and phase can
be added as a genuine v2 extension once a two-block weighting scheme is
designed, rather than rushing it into this pass.
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register

_MU0 = 4 * np.pi * 1e-7


def _forward(t_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    rho1, rho2, h1 = p["rho1"], p["rho2"], p["h1"]
    omega = 2 * np.pi * t_obs
    k1 = np.sqrt(1j * omega * _MU0 / rho1)
    z1 = np.sqrt(1j * omega * _MU0 * rho1)
    z_half = np.sqrt(1j * omega * _MU0 * rho2)
    z_top = z1 * (z_half + z1 * np.tanh(1j * k1 * h1)) / (z1 + z_half * np.tanh(1j * k1 * h1))
    return np.abs(z_top) ** 2 / (omega * _MU0)


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        "mu0 = 4 * np.pi * 1e-7\n"
        f"rho1, rho2, h1 = {p['rho1']!r}, {p['rho2']!r}, {p['h1']!r}\n"
        "omega = 2 * np.pi * t_obs\n"
        "k1 = np.sqrt(1j * omega * mu0 / rho1)\n"
        "z1 = np.sqrt(1j * omega * mu0 * rho1)\n"
        "z_half = np.sqrt(1j * omega * mu0 * rho2)\n"
        "z_top = z1 * (z_half + z1 * np.tanh(1j * k1 * h1)) / (z1 + z_half * np.tanh(1j * k1 * h1))\n"
        "d_pred = np.abs(z_top)**2 / (omega * mu0)\n"
        "m = {'params': {'rho1': rho1, 'rho2': rho2, 'h1': h1}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_rho1, log_rho2, log_h1 = x
    return {"rho1": 10.0**log_rho1, "rho2": 10.0**log_rho2, "h1": 10.0**log_h1}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given an observed
magnetotelluric (MT) sounding as two 1-D arrays already defined in your
script as `t_obs` (frequency, Hz) and `d_obs` (apparent resistivity, Ohm-m).

The subsurface is two layers: resistivity rho1 to depth h1, then a
half-space of resistivity rho2. The forward model is the classic 2-layer
recursive MT impedance (Wait 1954):

    mu0 = 4*pi*1e-7
    omega = 2*pi*t_obs
    k1 = sqrt(1j*omega*mu0/rho1)
    Z1 = sqrt(1j*omega*mu0*rho1)
    Z2 = sqrt(1j*omega*mu0*rho2)
    Z_top = Z1 * (Z2 + Z1*tanh(1j*k1*h1)) / (Z1 + Z2*tanh(1j*k1*h1))
    rho_a(f) = |Z_top|**2 / (omega*mu0)

Note: use complex (`1j`) arithmetic throughout — numpy handles complex
sqrt/tanh natively.

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [log10(rho1), log10(rho2), log10(h1)].
2. Because residuals are complex-arithmetic-derived but real-valued
   (rho_a is real), residual(p) = rho_a_model(p) - d_obs works directly with
   least_squares (no special complex handling needed for the residual itself).
3. Fit with least_squares(residual, x0_guess, method='lm', max_nfev=300).
4. Set d_pred = best-fit forward response, m = {'params': {'rho1':..., 'rho2':..., 'h1':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- t_obs / d_obs are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="MT_1D",
        display_name="Magnetotellurics — 1D, 2-layer sounding",
        x_label="frequency (Hz)",
        d_label="apparent resistivity (Ohm-m)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("rho1", "Ohm-m", "upper-layer resistivity", (20.0, 500.0)),
            ParamSpec("rho2", "Ohm-m", "half-space resistivity", (1.0, 100.0)),
            ParamSpec("h1", "m", "depth to conductive half-space", (50.0, 2000.0)),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(50.0), np.log10(5.0), np.log10(150.0)],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"rho1": 100.0, "rho2": 10.0, "h1": 300.0},
            x_obs=list(np.logspace(-3, 3, 25)),
        ),
        l2_tolerance=0.08,  # noisier two-parameter-regime curve than TDEM's default
    )
)

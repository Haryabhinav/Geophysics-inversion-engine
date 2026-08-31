"""Prompt construction for the Gemini inversion modeler.

The system prompt is the one defined in the specification, generalized to carry
the data type. The sandbox owns misfit computation, so the model author is told
explicitly not to compute it or print anything.
"""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given observed \
{data_type} data as two 1-D arrays, already defined in your script as `t_obs` \
(time steps, seconds) and `d_obs` (amplitudes).

The data is a Time-Domain EM step-off transient from a FIXED acquisition \
configuration. The forward model for a layered earth is:

    import numpy as np, empymod
    d = np.asarray(empymod.dipole(
        src=[0, 0, 0.001], rec=[100, 0, 0.001],
        depth=depth, res=res, freqtime=t_obs, signal=-1, verb=0,
    )).reshape(-1)

where `res` (Ohm-m) has exactly one more entry than `depth` (m); the first layer \
is air: `res[0] = 2e14`, `depth[0] = 0`.

INVERT IN A SINGLE SCRIPT — do NOT hand-tune parameters across turns. Instead \
use `scipy.optimize.least_squares` to fit the subsurface model to `d_obs` inside \
your script:
1. Write a `forward(depth, res)` helper using the call above.
2. Parameterize 2 subsurface layers in LOG10 space (values stay positive and \
well-scaled): p = [log10(res_1), log10(res_2), log10(depth_1)].
3. Fit with `least_squares(residual, x0, method="lm", max_nfev=300)` where \
`residual(p) = forward(depth_from_p, res_from_p) - d_obs`.
4. Set `d_pred` = the best-fit forward response, and \
`m = {{'res': [...], 'depth': [...]}}` from the best-fit parameters.

A reasonable start: resistivities ~10-300 Ohm-m, first interface depth ~30-80 m.

Hard rules:
- Output ONLY valid Python code. No prose, no explanation, no markdown outside code.
- End with TOP-LEVEL assignments (never inside a function): \
`d_pred = np.asarray(...).reshape(-1)` and `m = {{'res': [...], 'depth': [...]}}`.
- `t_obs` and `d_obs` are already defined. Do NOT redefine, reload, or fabricate them.
- Do NOT compute the misfit and do NOT call print(). The sandbox computes the \
RELATIVE misfit ||d_obs - d_pred|| / ||d_obs|| and reports it to you.

You should converge in ONE script. If it errors or the misfit is still above \
tolerance, you receive feedback — fix the bug, or improve the initial guess, \
parameterization, or layer count, and output a new single-script inversion.
"""


def system_prompt(data_type: str) -> str:
    # Lazy import: methods/specs/*.py import SYSTEM_PROMPT from this module,
    # so importing the registry at module load time here would cycle.
    from .methods import METHOD_REGISTRY

    spec = METHOD_REGISTRY.get(data_type)
    if spec is not None:
        return spec.system_prompt_template
    return SYSTEM_PROMPT.format(data_type=data_type)


def initial_user_prompt(data_summary: dict[str, Any], tolerance: float) -> str:
    return (
        "Here is a summary of the observed data you must fit:\n"
        f"- samples: {data_summary['n']}\n"
        f"- time range: {data_summary['t_min']:.4g} to {data_summary['t_max']:.4g}\n"
        f"- first amplitudes: {data_summary['d_first']}\n"
        f"- last amplitudes: {data_summary['d_last']}\n"
        f"- max |amplitude|: {data_summary['d_abs_max']:.4g}\n\n"
        f"Target: drive the relative misfit to <= {tolerance}. "
        "Write your single-script scipy inversion now."
    )


def feedback_prompt(*, l2_norm: float | None, error: str | None, tolerance: float) -> str:
    if error is not None:
        return (
            "Your previous script failed to execute. Traceback:\n"
            f"{error}\n\n"
            "Fix the code and output a corrected single-script inversion."
        )
    return (
        f"Your previous script ran. Relative misfit = {l2_norm:.6g} (target <= {tolerance}).\n"
        "Still too high — improve the initial guess, the parameterization, or add a "
        "layer, and output a new single-script scipy inversion."
    )

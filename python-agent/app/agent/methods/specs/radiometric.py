"""Gamma-ray spectrometry — spectral stripping / unmixing.

Classic IAEA TECDOC-1363 (2003) "spectral stripping" approach: measured
count rates in the K/U/Th energy windows are a linear mixture of the true
elemental concentrations (Compton-scatter cross-talk between windows is
captured by the off-diagonal terms of a fixed calibration matrix M):

    counts = M @ concentrations

This is the one registered method that's linear algebra rather than a
nonlinear curve fit — `t_obs` is just the window index [0, 1, 2] (there's no
independent "x-axis" here, just three simultaneous window measurements), and
`d_obs` is the three measured count rates. It still fits the uniform
propose/execute/least-squares pattern (a 3-parameter fit to 3 equations), so
it stays in the same registry rather than needing a special orchestrator
path — it just happens to converge almost immediately since the problem is
exactly solvable.
"""

from __future__ import annotations

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register

# Fixed instrument calibration (window response to K/U/Th) — analogous to
# TDEM's fixed acquisition geometry. Off-diagonal terms are Compton
# scatter-down cross-talk between windows, the reason a naive per-window
# reading isn't already the answer.
_M = np.array(
    [
        [1.00, 0.15, 0.10],  # K window's response to [K, U, Th]
        [0.05, 1.00, 0.30],  # U window
        [0.02, 0.10, 1.00],  # Th window
    ]
)


def _forward(t_obs: np.ndarray, p: dict[str, float]) -> np.ndarray:
    conc = np.array([p["K_conc"], p["U_conc"], p["Th_conc"]])
    return _M @ conc


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"M = np.array({_M.tolist()!r})\n"
        f"K_conc, U_conc, Th_conc = {p['K_conc']!r}, {p['U_conc']!r}, {p['Th_conc']!r}\n"
        "conc = np.array([K_conc, U_conc, Th_conc])\n"
        "d_pred = M @ conc\n"
        "m = {'params': {'K_conc': K_conc, 'U_conc': U_conc, 'Th_conc': Th_conc}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    log_k, log_u, log_th = x
    return {"K_conc": 10.0**log_k, "U_conc": 10.0**log_u, "Th_conc": 10.0**log_th}


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are given observed
gamma-ray spectrometry window counts as two 1-D arrays already defined in
your script as `t_obs` (window index: 0=K, 1=U, 2=Th — not a physical axis)
and `d_obs` (measured count rate per window, arbitrary units).

The forward model is a FIXED, KNOWN 3x3 calibration matrix M mapping true
elemental concentrations to window counts (Compton-scatter cross-talk
between windows is why a raw window reading isn't already the answer):

    M = [[1.00, 0.15, 0.10],
         [0.05, 1.00, 0.30],
         [0.02, 0.10, 1.00]]
    counts = M @ [K_conc, U_conc, Th_conc]

This is a LINEAR system — M is invertible, so you do not need an iterative
optimizer.

INVERT IN A SINGLE SCRIPT:
1. Build M exactly as given above.
2. Solve concentrations = np.linalg.solve(M, d_obs) directly.
3. Set d_pred = M @ concentrations (should reproduce d_obs almost exactly),
   and m = {'params': {'K_conc':..., 'U_conc':..., 'Th_conc':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- t_obs / d_obs are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="RADIOMETRIC",
        display_name="Radiometric — gamma-ray spectral unmixing",
        x_label="window index (0=K, 1=U, 2=Th)",
        d_label="count rate (arb. units)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("K_conc", "%", "potassium concentration", (0.1, 10.0)),
            ParamSpec("U_conc", "ppm", "uranium concentration", (0.5, 30.0)),
            ParamSpec("Th_conc", "ppm", "thorium concentration", (1.0, 100.0)),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[np.log10(1.0), np.log10(1.0), np.log10(5.0)],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={"K_conc": 2.0, "U_conc": 3.0, "Th_conc": 10.0},
            x_obs=[0.0, 1.0, 2.0],
            n_corrupt=0,  # only 3 real measurements exist; none are corruptible
        ),
    )
)

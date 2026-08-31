"""Seismology — earthquake hypocenter location (Geiger's method).

Classic straight-ray, constant-velocity hypocenter location (Geiger 1912):
given P-wave arrival times at several fixed-position stations, invert for
the source location and origin time.

    t_i = t0 + sqrt((x_i - src_x)**2 + (y_i - src_y)**2 + (z_i - src_z)**2) / V

Station coordinates are fixed geometry, not a curve's x-axis, so they don't
fit t_obs/d_obs (whose lengths must match 1:1) — this is the one method that
uses the `aux` side-channel (see tools/sandbox.py): `t_obs` is just the
station index [0..N-1], `d_obs` is the observed arrival times, and
`aux['station_x'/'y'/'z']` carries the fixed station coordinates.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..registry import MethodSpec, ParamSpec, SyntheticScenario, register

# 6 stations spread around the epicenter, all at the surface (z=0).
_STATION_X = [500.0, 8000.0, 14000.0, 2000.0, 12000.0, 6000.0]
_STATION_Y = [1000.0, 500.0, 4000.0, 13000.0, 12000.0, 7000.0]
_STATION_Z = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def _forward(t_obs: np.ndarray, p: dict[str, float], aux: dict[str, Any]) -> np.ndarray:
    dx = np.asarray(aux["station_x"]) - p["src_x"]
    dy = np.asarray(aux["station_y"]) - p["src_y"]
    dz = np.asarray(aux["station_z"]) - p["src_z"]
    dist = np.sqrt(dx**2 + dy**2 + dz**2)
    return p["origin_t"] + dist / p["velocity"]


def _render_code(p: dict[str, float]) -> str:
    return (
        "import numpy as np\n"
        f"src_x, src_y, src_z = {p['src_x']!r}, {p['src_y']!r}, {p['src_z']!r}\n"
        f"origin_t, velocity = {p['origin_t']!r}, {p['velocity']!r}\n"
        "dx = aux['station_x'] - src_x\n"
        "dy = aux['station_y'] - src_y\n"
        "dz = aux['station_z'] - src_z\n"
        "dist = np.sqrt(dx**2 + dy**2 + dz**2)\n"
        "d_pred = origin_t + dist / velocity\n"
        "m = {'params': {'src_x': src_x, 'src_y': src_y, 'src_z': src_z, "
        "'origin_t': origin_t, 'velocity': velocity}}\n"
    )


def _expand(x: list[float]) -> dict[str, float]:
    src_x, src_y, src_z, origin_t, log_v = x
    return {
        "src_x": src_x,
        "src_y": src_y,
        "src_z": src_z,
        "origin_t": origin_t,
        "velocity": 10.0**log_v,
    }


def _summarize(t_obs: np.ndarray, d_obs: np.ndarray) -> dict[str, Any]:
    """Override the generic curve-summary — t_obs here is a station index,
    not a time axis, so the default "time range" framing would be nonsense."""
    preview = 5
    return {
        "n": int(t_obs.size),
        "t_min": float(d_obs.min()),
        "t_max": float(d_obs.max()),
        "d_first": [round(float(x), 6) for x in d_obs[:preview]],
        "d_last": [round(float(x), 6) for x in d_obs[-preview:]],
        "d_abs_max": float(np.abs(d_obs).max()),
    }


SYSTEM_PROMPT = """\
You are an autonomous geophysical inversion agent. You are locating an
earthquake hypocenter from P-wave arrival times at several fixed stations.

Already defined in your script:
- `t_obs` — station index (0..N-1), not a physical axis.
- `d_obs` — observed P-wave arrival time at each station (seconds).
- `aux['station_x']`, `aux['station_y']`, `aux['station_z']` — each station's
  fixed surface coordinates (meters), same length and order as `t_obs`/`d_obs`.

The forward model is Geiger's classic straight-ray, constant-velocity
travel-time formula:

    t_i = origin_t + sqrt((station_x_i - src_x)**2 + (station_y_i - src_y)**2
                           + (station_z_i - src_z)**2) / velocity

INVERT IN A SINGLE SCRIPT using scipy.optimize.least_squares:
1. Parameterize p = [src_x, src_y, src_z, origin_t, log10(velocity)].
2. residual(p) = origin_t + dist(p)/velocity - d_obs, velocity = 10**p[4].
3. Fit with least_squares(residual, x0_guess, method='lm', max_nfev=300).
4. Set d_pred = best-fit forward response, and
   m = {'params': {'src_x':..., 'src_y':..., 'src_z':..., 'origin_t':..., 'velocity':...}}.

Hard rules:
- Output ONLY valid Python code. No prose, no markdown outside code.
- End with TOP-LEVEL assignments: d_pred = ... and m = {...}.
- `t_obs`, `d_obs`, and `aux` are already defined; do not redefine or reload them.
- Do NOT compute misfit or call print(); the sandbox reports relative L2 to you.
"""

SPEC = register(
    MethodSpec(
        id="EARTHQUAKE_LOCATION",
        display_name="Seismology — earthquake hypocenter location",
        x_label="station index",
        d_label="P-wave arrival time (s)",
        system_prompt_template=SYSTEM_PROMPT,
        params=[
            ParamSpec("src_x", "m", "epicenter x-coordinate", (0.0, 15000.0), log_space=False),
            ParamSpec("src_y", "m", "epicenter y-coordinate", (0.0, 15000.0), log_space=False),
            ParamSpec("src_z", "m", "hypocenter depth", (500.0, 20000.0), log_space=False),
            ParamSpec("origin_t", "s", "earthquake origin time offset", (-5.0, 5.0), log_space=False),
            ParamSpec("velocity", "m/s", "seismic P-wave velocity", (3000.0, 8000.0)),
        ],
        forward_fn=_forward,
        render_code=_render_code,
        x0=[4000.0, 2000.0, 6000.0, 0.0, np.log10(5500.0)],
        expand=_expand,
        synthetic=SyntheticScenario(
            truth_params={
                "src_x": 5000.0,
                "src_y": 3000.0,
                "src_z": 8000.0,
                "origin_t": 0.0,
                "velocity": 6000.0,
            },
            x_obs=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            n_corrupt=0,  # only 6 stations exist; none are corruptible
            aux_arrays={"station_x": _STATION_X, "station_y": _STATION_Y, "station_z": _STATION_Z},
        ),
        needs_aux=True,
        aux_keys=("station_x", "station_y", "station_z"),
        summarize_fn=_summarize,
    )
)

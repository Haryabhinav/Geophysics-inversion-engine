"""Isolated execution of LLM-generated forward-model code.

The model author writes a script that defines two names:
  * ``d_pred`` — the predicted response (array, same length as ``d_obs``)
  * ``m``      — the earth-model parameter dict

This harness supplies ``t_obs`` / ``d_obs``, runs the script in a separate
process, and computes the L2 norm itself so the misfit cannot be faked by the
model author. It returns a plain dict: either the exact L2 norm + model, or the
captured stderr traceback.

SECURITY: this executes untrusted, model-authored code. It is hardened for a
local/dev deployment (separate process, wall-clock timeout, per-job temp dir,
secrets stripped from the child env). It is NOT a true security boundary — a
production deployment must run this inside a locked-down container / gVisor /
nsjail with no network and enforced CPU/memory limits.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from typing import Any

import numpy as np

RESULT_MARKER = "__INVERSION_RESULT__"
_MAX_CAPTURE = 4000  # chars of stdout/stderr retained in error reports

_WRAPPER_HEADER = """\
import json, os, sys
import numpy as np


def _to_jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.integer):
        return int(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


# Observed data supplied by the harness (argv paths). Do not redefine these.
t_obs = np.load(sys.argv[1])
d_obs = np.load(sys.argv[2])

# Fixed, non-curve metadata (e.g. station coordinates for earthquake
# location) — only present when the method needs it (`spec.needs_aux`).
# Empty dict when not applicable; zero overhead/behavior change otherwise.
aux = {}
_aux_manifest_path = os.path.join(os.path.dirname(sys.argv[1]), "aux_manifest.json")
if os.path.exists(_aux_manifest_path):
    with open(_aux_manifest_path) as _f:
        for _name, _fname in json.load(_f).items():
            aux[_name] = np.load(os.path.join(os.path.dirname(sys.argv[1]), _fname))

# ===================== MODEL-AUTHORED CODE START =====================
"""

_WRAPPER_FOOTER = """
# ====================== MODEL-AUTHORED CODE END ======================

# Misfit is computed by the harness, never by the model author.
_d_pred = np.asarray(d_pred, dtype=float).reshape(-1)
_d_obs = np.asarray(d_obs, dtype=float).reshape(-1)
if _d_pred.shape != _d_obs.shape:
    raise ValueError(
        f"d_pred has {_d_pred.size} points but d_obs has {_d_obs.size}; "
        "they must be the same length"
    )

# Relative L2 misfit (scale-invariant): ||d_obs - d_pred|| / ||d_obs||.
_den = float(np.linalg.norm(_d_obs))
_l2 = float(np.linalg.norm(_d_obs - _d_pred) / _den) if _den > 1e-30 else float(np.linalg.norm(_d_obs - _d_pred))

# A non-finite misfit means the model evaluated to NaN/inf somewhere (an
# optimizer step wandering outside the model's valid domain — e.g. seismic
# refraction's head-wave branch with v2 < v1). That is an execution FAILURE,
# not a very bad fit, and saying so here keeps the two sandbox transports
# honest with each other: `run_local` returns the raw float, but the remote
# service serializes its dict through FastAPI, where NaN becomes JSON `null`
# — so the same run yielded `nan` locally and `None` over HTTP. Raising makes
# both paths return {"ok": False, "error": ...}, which the orchestrator
# already knows how to feed back and retry.
if not np.isfinite(_l2):
    raise ValueError(
        "model produced a non-finite misfit (d_pred contains NaN or inf) - "
        "the parameters are outside this forward model's valid domain"
    )
try:
    _m = m
except NameError as exc:  # noqa: F821 - `m` is defined by model-authored code
    raise NameError("model code must define a dict named `m`") from exc

print("__INVERSION_RESULT__" + json.dumps(
    {"l2_norm": _l2, "m_current": _m, "d_pred": _d_pred.tolist()},
    default=_to_jsonable,
))
"""


def _safe_env() -> dict[str, str]:
    """Child environment with secrets removed but runtime intact.

    numpy/scipy need PATH (and SYSTEMROOT on Windows) to load native libs, so we
    copy the environment and strip anything that looks like a credential rather
    than starting from empty.
    """
    blocked = ("KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD", "CREDENTIAL")
    return {
        k: v
        for k, v in os.environ.items()
        if not any(marker in k.upper() for marker in blocked)
    }


def _tail(text: str, limit: int = _MAX_CAPTURE) -> str:
    text = text.strip()
    return text if len(text) <= limit else "...(truncated)...\n" + text[-limit:]


def _parse_result(stdout: str) -> dict[str, Any] | None:
    import json

    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_MARKER):
            return json.loads(line[len(RESULT_MARKER):])
    return None


def build_script(code: str) -> str:
    """Assemble the full sandbox script from model-authored code."""
    return _WRAPPER_HEADER + code + "\n" + _WRAPPER_FOOTER


def run_local(
    code: str,
    t_obs: np.ndarray,
    d_obs: np.ndarray,
    timeout_s: int = 10,
    aux: dict[str, np.ndarray] | None = None,
) -> dict[str, Any]:
    """Run model-authored code in a local subprocess. Returns:
      {"ok": True,  "l2_norm": float, "m_current": dict}
      {"ok": False, "error": str}
    """
    workdir = tempfile.mkdtemp(prefix="inv_")
    try:
        t_path = os.path.join(workdir, "t_obs.npy")
        d_path = os.path.join(workdir, "d_obs.npy")
        np.save(t_path, np.asarray(t_obs, dtype=float))
        np.save(d_path, np.asarray(d_obs, dtype=float))

        if aux:
            manifest = {}
            for name, arr in aux.items():
                fname = f"aux_{name}.npy"
                np.save(os.path.join(workdir, fname), np.asarray(arr, dtype=float))
                manifest[name] = fname
            with open(os.path.join(workdir, "aux_manifest.json"), "w") as f:
                json.dump(manifest, f)

        script_path = os.path.join(workdir, "sandbox_run.py")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(build_script(code))

        try:
            proc = subprocess.run(
                [sys.executable, script_path, t_path, d_path],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=workdir,
                env=_safe_env(),
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Execution timed out after {timeout_s}s"}

        if proc.returncode != 0:
            return {"ok": False, "error": _tail(proc.stderr) or "non-zero exit, no stderr"}

        parsed = _parse_result(proc.stdout)
        if parsed is None:
            return {
                "ok": False,
                "error": "no result marker in stdout; tail:\n" + _tail(proc.stdout),
            }

        return {
            "ok": True,
            "l2_norm": float(parsed["l2_norm"]),
            "m_current": parsed["m_current"],
            "d_pred": parsed.get("d_pred"),
        }

    except Exception as exc:  # harness-level failure (I/O, serialization, ...)
        return {"ok": False, "error": f"sandbox harness error: {exc!r}"}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _run_remote(
    code: str,
    t_obs: np.ndarray,
    d_obs: np.ndarray,
    timeout_s: int,
    url: str,
    aux: dict[str, np.ndarray] | None = None,
) -> dict[str, Any]:
    """Delegate execution to a remote sandbox service (see sandbox_service/)."""
    payload = json.dumps(
        {
            "code": code,
            "t_obs": np.asarray(t_obs, dtype=float).tolist(),
            "d_obs": np.asarray(d_obs, dtype=float).tolist(),
            "timeout_s": timeout_s,
            "aux": {k: np.asarray(v, dtype=float).tolist() for k, v in aux.items()} if aux else None,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url.rstrip("/") + "/execute",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # Allow generous slack over the model timeout for transport + startup.
        with urllib.request.urlopen(request, timeout=timeout_s + 20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"sandbox service unreachable: {exc!r}"}


def execute_generated_model(
    code: str,
    t_obs: np.ndarray,
    d_obs: np.ndarray,
    timeout_s: int = 10,
    aux: dict[str, np.ndarray] | None = None,
) -> dict[str, Any]:
    """Execute model-authored code and return the L2 norm or an error.

    Dispatches to a remote sandbox service when ``SANDBOX_URL`` is set (the
    docker-compose deployment), otherwise runs locally in a subprocess.

    `aux` carries fixed, non-curve metadata a method may need (e.g. station
    coordinates for earthquake location) — most methods leave it None.
    """
    url = os.getenv("SANDBOX_URL", "").strip()
    if url:
        return _run_remote(code, t_obs, d_obs, timeout_s, url, aux=aux)
    return run_local(code, t_obs, d_obs, timeout_s, aux=aux)


# --------------------------------------------------------------------------- #
# Classification sandbox (borehole lithology) — a parallel, not-shared,
# wrapper: the data shapes (a 2D feature matrix + string labels vs. two 1-D
# float arrays) and result contract differ enough from the curve-fit path
# above that reusing one function's header/footer would be harder to read
# than two small parallel ones. Same security posture throughout: separate
# subprocess, per-job temp dir, secret-stripped env, wall-clock timeout,
# stdout result marker.
# --------------------------------------------------------------------------- #

CLASSIFIER_RESULT_MARKER = "__CLASSIFICATION_RESULT__"

_CLASSIFIER_WRAPPER_HEADER = """\
import json, sys
import numpy as np


def _to_jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.integer):
        return int(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


# Harness-supplied (argv path). Do not redefine these. Note there is no
# variable holding true labels for X_test — only the harness (never this
# subprocess) ever sees them, so a script cannot "cheat" by reading them.
_data = json.load(open(sys.argv[1]))
X_train = np.array(_data["X_train"], dtype=float)
y_train = np.array(_data["y_train"], dtype=object)
X_test = np.array(_data["X_test"], dtype=float)
feature_names = _data["feature_names"]
classes = _data["classes"]

# ===================== MODEL-AUTHORED CODE START =====================
"""

_CLASSIFIER_WRAPPER_FOOTER = """
# ====================== MODEL-AUTHORED CODE END ======================

# Scoring is computed by the harness (never the model author) from ground
# truth ONLY the harness holds — this subprocess never received it.
_y_pred = list(y_pred)
if len(_y_pred) != X_test.shape[0]:
    raise ValueError(
        f"y_pred has {len(_y_pred)} entries but X_test has {X_test.shape[0]} rows"
    )
try:
    _m = m
except NameError as exc:  # noqa: F821 - `m` is defined by model-authored code
    raise NameError("model code must define a dict named `m`") from exc

print("__CLASSIFICATION_RESULT__" + json.dumps(
    {"y_pred": _y_pred, "m_current": _m},
    default=_to_jsonable,
))
"""


def build_classifier_script(code: str) -> str:
    return _CLASSIFIER_WRAPPER_HEADER + code + "\n" + _CLASSIFIER_WRAPPER_FOOTER


def _parse_classifier_result(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith(CLASSIFIER_RESULT_MARKER):
            return json.loads(line[len(CLASSIFIER_RESULT_MARKER):])
    return None


def run_local_classifier(
    code: str,
    X_train: list[list[float]],
    y_train: list[str],
    X_test: list[list[float]],
    feature_names: list[str],
    classes: list[str],
    timeout_s: int = 10,
) -> dict[str, Any]:
    """Run model-authored classification code in a local subprocess. Returns:
      {"ok": True,  "y_pred": [...], "m_current": dict}
      {"ok": False, "error": str}
    """
    workdir = tempfile.mkdtemp(prefix="clf_")
    try:
        data_path = os.path.join(workdir, "data.json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "X_train": X_train,
                    "y_train": y_train,
                    "X_test": X_test,
                    "feature_names": feature_names,
                    "classes": classes,
                },
                f,
            )

        script_path = os.path.join(workdir, "sandbox_run.py")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(build_classifier_script(code))

        try:
            proc = subprocess.run(
                [sys.executable, script_path, data_path],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=workdir,
                env=_safe_env(),
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Execution timed out after {timeout_s}s"}

        if proc.returncode != 0:
            return {"ok": False, "error": _tail(proc.stderr) or "non-zero exit, no stderr"}

        parsed = _parse_classifier_result(proc.stdout)
        if parsed is None:
            return {
                "ok": False,
                "error": "no result marker in stdout; tail:\n" + _tail(proc.stdout),
            }

        return {"ok": True, "y_pred": parsed["y_pred"], "m_current": parsed["m_current"]}

    except Exception as exc:
        return {"ok": False, "error": f"sandbox harness error: {exc!r}"}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _run_remote_classifier(
    code: str,
    X_train: list[list[float]],
    y_train: list[str],
    X_test: list[list[float]],
    feature_names: list[str],
    classes: list[str],
    timeout_s: int,
    url: str,
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "code": code,
            "X_train": X_train,
            "y_train": y_train,
            "X_test": X_test,
            "feature_names": feature_names,
            "classes": classes,
            "timeout_s": timeout_s,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url.rstrip("/") + "/execute-classifier",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s + 20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"sandbox service unreachable: {exc!r}"}


def execute_generated_classifier(
    code: str,
    X_train: list[list[float]],
    y_train: list[str],
    X_test: list[list[float]],
    feature_names: list[str],
    classes: list[str],
    timeout_s: int = 10,
) -> dict[str, Any]:
    """Execute model-authored classification code and return predicted
    labels or an error. Dispatches to a remote sandbox service when
    SANDBOX_URL is set, otherwise runs locally in a subprocess."""
    url = os.getenv("SANDBOX_URL", "").strip()
    if url:
        return _run_remote_classifier(code, X_train, y_train, X_test, feature_names, classes, timeout_s, url)
    return run_local_classifier(code, X_train, y_train, X_test, feature_names, classes, timeout_s)

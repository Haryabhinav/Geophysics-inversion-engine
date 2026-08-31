"""Tests for the sandboxed execution tool (Step 3)."""

import numpy as np
import pytest

import tools.sandbox as sandbox
from tools.sandbox import execute_generated_model

T = np.array([1e-4, 1e-3, 1e-2])
D = np.array([3.0, 2.0, 1.0])


def test_success_zero_residual():
    code = "d_pred = d_obs.copy()\nm = {'res': [1.0], 'depth': [0.0]}"
    result = execute_generated_model(code, T, D, timeout_s=10)
    assert result["ok"] is True
    assert result["l2_norm"] == pytest.approx(0.0)
    assert result["m_current"]["res"] == [1.0]


def test_relative_misfit_of_zero_prediction_is_one():
    # d_pred = 0 -> relative misfit ||d_obs - 0|| / ||d_obs|| == 1.0
    code = "import numpy as np\nd_pred = np.zeros_like(d_obs)\nm = {}"
    result = execute_generated_model(code, T, D, timeout_s=10)
    assert result["ok"] is True
    assert result["l2_norm"] == pytest.approx(1.0)


def test_bad_code_returns_traceback():
    result = execute_generated_model("d_pred = does_not_exist\nm = {}", T, D, timeout_s=10)
    assert result["ok"] is False
    assert "NameError" in result["error"]


def test_shape_mismatch_is_reported():
    code = "import numpy as np\nd_pred = np.zeros(2)\nm = {}"
    result = execute_generated_model(code, T, D, timeout_s=10)
    assert result["ok"] is False
    assert "same length" in result["error"]


def test_missing_m_is_reported():
    code = "d_pred = d_obs.copy()"  # never defines `m`
    result = execute_generated_model(code, T, D, timeout_s=10)
    assert result["ok"] is False
    assert "define a dict named" in result["error"]


def test_no_result_marker_on_early_exit():
    result = execute_generated_model("import os\nos._exit(0)", T, D, timeout_s=10)
    assert result["ok"] is False
    assert "no result marker" in result["error"]


def test_timeout_is_enforced():
    result = execute_generated_model("while True:\n    pass", T, D, timeout_s=1)
    assert result["ok"] is False
    assert "timed out" in result["error"]


def test_secrets_stripped_from_child_env(monkeypatch):
    monkeypatch.setenv("MYSECRETTOKEN", "leaked")   # blocked (SECRET, TOKEN)
    monkeypatch.setenv("MYPUBLICCONF", "ok")        # allowed
    code = (
        "import os\n"
        "d_pred = d_obs.copy()\n"
        "m = {\n"
        "    'secret': os.environ.get('MYSECRETTOKEN', 'ABSENT'),\n"
        "    'public': os.environ.get('MYPUBLICCONF', 'ABSENT'),\n"
        "}\n"
    )
    result = execute_generated_model(code, T, D, timeout_s=10)
    assert result["ok"] is True
    assert result["m_current"]["secret"] == "ABSENT"  # stripped
    assert result["m_current"]["public"] == "ok"      # passed through


def test_dispatch_uses_remote_when_sandbox_url_set(monkeypatch):
    monkeypatch.setenv("SANDBOX_URL", "http://sandbox:8001")
    monkeypatch.setattr(sandbox, "_run_remote", lambda *a, **k: {"via": "remote"})
    monkeypatch.setattr(sandbox, "run_local", lambda *a, **k: {"via": "local"})
    assert execute_generated_model("code", T, D)["via"] == "remote"


def test_dispatch_uses_local_by_default(monkeypatch):
    monkeypatch.delenv("SANDBOX_URL", raising=False)
    monkeypatch.setattr(sandbox, "_run_remote", lambda *a, **k: {"via": "remote"})
    monkeypatch.setattr(sandbox, "run_local", lambda *a, **k: {"via": "local"})
    assert execute_generated_model("code", T, D)["via"] == "local"


def test_non_finite_misfit_is_reported_as_an_execution_error():
    """A model whose d_pred is NaN must fail, not report a NaN misfit.

    This one crossed a transport boundary to become a crash: `run_local`
    returned a real `float('nan')`, but the remote sandbox service serializes
    its result dict through FastAPI, where NaN is encoded as JSON `null`. The
    orchestrator then did `np.isclose(recomputed, None)` -> TypeError, which
    escaped the entire WebSocket handler and took every queued job with it.
    Failing here keeps both transports on the same contract: l2_norm is
    always a usable float, or ok is False.
    """
    code = "import numpy as np\nd_pred = np.full_like(t_obs, np.nan)\nm = {'a': 1.0}\n"
    result = execute_generated_model(code, np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]), timeout_s=20)

    assert result["ok"] is False
    assert "non-finite misfit" in result["error"]


def test_infinite_prediction_is_also_an_execution_error():
    code = "import numpy as np\nd_pred = np.full_like(t_obs, np.inf)\nm = {'a': 1.0}\n"
    result = execute_generated_model(code, np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]), timeout_s=20)

    assert result["ok"] is False
    assert "non-finite misfit" in result["error"]

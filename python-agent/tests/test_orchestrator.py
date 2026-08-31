"""Tests for the agentic loop's control flow (Step 4).

The sandbox executor is stubbed so these run instantly and exercise only the
orchestrator's branching: converged / max_iterations_reached / error.
"""

from types import SimpleNamespace

import numpy as np

import app.agent.orchestrator as orch

T = np.array([1.0, 2.0, 3.0])
D = np.array([1.0, 1.0, 1.0])


class DummyModeler:
    """A modeler whose code is never actually run (executor is stubbed)."""

    def propose(self, iteration, summary, feedback):
        return "PLACEHOLDER"


def _settings(**overrides):
    base = dict(l2_tolerance=0.1, max_iterations=5, offline_max_iterations=5, sandbox_timeout_s=5)
    base.update(overrides)
    return SimpleNamespace(**base)


def _stub_executor(results):
    """Return an execute_generated_model stub that yields `results` in order,
    repeating the last entry once exhausted."""
    seq = list(results)
    calls = {"i": 0}

    def _exec(code, t_obs, d_obs, timeout_s=10, aux=None):
        entry = seq[min(calls["i"], len(seq) - 1)]
        calls["i"] += 1
        return entry

    return _exec


def test_converges(monkeypatch):
    monkeypatch.setattr(orch, "settings", _settings())
    monkeypatch.setattr(orch, "execute_generated_model", _stub_executor([
        {"ok": True, "l2_norm": 5.0, "m_current": {"step": 1}},
        {"ok": True, "l2_norm": 0.05, "m_current": {"step": 2}},
    ]))
    result = orch.run_inversion_agent("job", "TDEM", T, D, modeler=DummyModeler())
    assert result.status == "converged"
    assert result.iterations == 2
    assert result.l2_norm_error == 0.05
    assert result.final_model == {"step": 2}


def test_equivalent_models_surfaces_near_tied_candidates(monkeypatch):
    """EM inversion is non-unique: multiple distinct models can fit almost
    equally well. The orchestrator should surface the near-tied candidates
    (within EQUIVALENCE_BAND of the best L2) for a downstream step to
    disambiguate using context the misfit number alone can't capture."""
    monkeypatch.setattr(orch, "settings", _settings(max_iterations=4, l2_tolerance=0.02))
    monkeypatch.setattr(orch, "execute_generated_model", _stub_executor([
        {"ok": True, "l2_norm": 0.30, "m_current": {"res": [30, 300]}},
        {"ok": True, "l2_norm": 0.06, "m_current": {"res": [45, 200]}},  # near-tied w/ below
        {"ok": True, "l2_norm": 0.05, "m_current": {"res": [50, 180]}},  # best
        {"ok": True, "l2_norm": 0.90, "m_current": {"res": [10, 900]}},  # far off, excluded
    ]))
    result = orch.run_inversion_agent("job", "TDEM", T, D, modeler=DummyModeler())
    assert result.status == "max_iterations_reached"
    assert result.l2_norm_error == 0.05
    l2s = {m["l2_norm_error"] for m in result.equivalent_models}
    assert l2s == {0.05, 0.06}
    assert result.equivalent_models[0]["l2_norm_error"] == 0.05  # best-first


def test_max_iterations_reached_keeps_best(monkeypatch):
    monkeypatch.setattr(orch, "settings", _settings(max_iterations=4))
    monkeypatch.setattr(orch, "execute_generated_model", _stub_executor([
        {"ok": True, "l2_norm": 9.0, "m_current": {"which": "first"}},
        {"ok": True, "l2_norm": 3.0, "m_current": {"which": "best"}},
        {"ok": True, "l2_norm": 7.0, "m_current": {"which": "worse"}},
    ]))
    result = orch.run_inversion_agent("job", "TDEM", T, D, modeler=DummyModeler())
    assert result.status == "max_iterations_reached"
    assert result.iterations == 4
    assert result.l2_norm_error == 3.0
    assert result.final_model == {"which": "best"}


def test_all_iterations_error(monkeypatch):
    monkeypatch.setattr(orch, "settings", _settings(max_iterations=3))
    monkeypatch.setattr(orch, "execute_generated_model", _stub_executor([
        {"ok": False, "error": "boom"},
    ]))
    result = orch.run_inversion_agent("job", "TDEM", T, D, modeler=DummyModeler())
    assert result.status == "error"
    assert result.iterations == 3
    assert result.final_model == {}


def test_rejects_fake_convergence_from_degenerate_d_pred(monkeypatch):
    """A sandbox run can self-report l2_norm=0 with a degenerate d_pred (e.g. a
    buggy LLM script whose model predicts all-zeros while d_obs is real
    signal). The orchestrator must recompute L2 from d_obs/d_pred itself
    rather than trust the sandbox's self-reported number, so this must NOT be
    treated as convergence."""
    monkeypatch.setattr(orch, "settings", _settings(max_iterations=2))
    monkeypatch.setattr(orch, "execute_generated_model", _stub_executor([
        {
            "ok": True,
            "l2_norm": 0.0,  # falsely reports a perfect fit
            "m_current": {"res": [1e14, 30, 80], "depth": [0, 50]},
            "d_pred": [0.0, 0.0, 0.0],  # but the predicted curve is degenerate
        },
    ]))
    result = orch.run_inversion_agent("job", "TDEM", T, D, modeler=DummyModeler())
    assert result.status != "converged"
    assert result.l2_norm_error > 0.1


def test_modeler_exception_is_caught(monkeypatch):
    monkeypatch.setattr(orch, "settings", _settings())

    class Boom:
        def propose(self, *args, **kwargs):
            raise RuntimeError("modeler died")

    result = orch.run_inversion_agent("job", "TDEM", T, D, modeler=Boom())
    assert result.status == "error"
    assert "modeler died" in result.message


def test_null_misfit_from_the_sandbox_does_not_crash_the_loop(monkeypatch):
    """An `ok` sandbox result carrying a null misfit must be a failed
    iteration, not a TypeError out of the whole handler.

    Reproduces a crash seen only under docker-compose. `run_local` returns a
    real `float('nan')` for a NaN misfit, but the REMOTE sandbox service
    serializes its result through FastAPI, where NaN encodes as JSON `null` —
    so the identical run yielded `nan` locally and `None` over HTTP. The
    orchestrator fed that straight into `np.isclose(recomputed, None)`, whose
    TypeError escaped run_inversion_agent, asyncio.to_thread AND the
    WebSocket handler, dropping the connection and silently losing all seven
    jobs queued behind it.
    """
    monkeypatch.setattr(orch, "settings", _settings())
    monkeypatch.setattr(
        orch,
        "execute_generated_model",
        _stub_executor([
            # exactly what the remote sandbox returned for a NaN misfit
            {"ok": True, "l2_norm": None, "m_current": {"a": 1.0}, "d_pred": [None, None, None]},
            # d_pred None so the reported misfit stands (the orchestrator
            # otherwise recomputes it from d_pred - see _recompute_l2).
            {"ok": True, "l2_norm": 0.01, "m_current": {"a": 2.0}, "d_pred": None},
        ]),
    )

    result = orch.run_inversion_agent("job-null-l2", "TDEM", T, D, modeler=DummyModeler())

    # Survived the bad iteration and converged on the next one.
    assert result.status == "converged"
    assert result.l2_norm_error == 0.01
    assert result.final_model == {"a": 2.0}


def test_non_finite_misfit_from_the_sandbox_does_not_crash_the_loop(monkeypatch):
    """Same guard, for the local transport's shape of the same failure."""
    monkeypatch.setattr(orch, "settings", _settings())
    monkeypatch.setattr(
        orch,
        "execute_generated_model",
        _stub_executor([
            {"ok": True, "l2_norm": float("nan"), "m_current": {"a": 1.0}, "d_pred": None},
            {"ok": True, "l2_norm": 0.02, "m_current": {"a": 3.0}, "d_pred": None},
        ]),
    )

    result = orch.run_inversion_agent("job-nan-l2", "TDEM", T, D, modeler=DummyModeler())

    assert result.status == "converged"
    assert result.l2_norm_error == 0.02

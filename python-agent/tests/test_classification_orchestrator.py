"""Tests for the classification loop's control flow (borehole lithology).

The sandbox executor is stubbed so these run instantly and exercise only the
orchestrator's branching — mirrors test_orchestrator.py's style exactly.
"""

import app.agent.classification_orchestrator as clf_orch

TRAIN_X = [[1.0, 2.0], [2.0, 1.0]]
TRAIN_Y = ["A", "B"]
TEST_X = [[1.5, 1.5], [8.0, 8.0]]
FEATURES = ["f1", "f2"]
CLASSES = ["A", "B"]


class DummyClassifierModeler:
    def propose(self, iteration, data_summary, feedback):
        return "PLACEHOLDER"


def _stub_executor(results):
    seq = list(results)
    calls = {"i": 0}

    def _exec(code, train_x, train_y, test_x, feature_names, classes, timeout_s=10):
        entry = seq[min(calls["i"], len(seq) - 1)]
        calls["i"] += 1
        return entry

    return _exec


def test_converges_and_scores_when_true_labels_given(monkeypatch):
    monkeypatch.setattr(
        clf_orch,
        "execute_generated_classifier",
        _stub_executor([{"ok": True, "y_pred": ["A", "B"], "m_current": {"algorithm": "stub"}}]),
    )
    result = clf_orch.run_classification_agent(
        "job", TRAIN_X, TRAIN_Y, TEST_X, FEATURES, CLASSES,
        test_y_true=["A", "B"], modeler=DummyClassifierModeler(),
    )
    assert result.status == "converged"
    assert result.final_model["predicted_labels"] == ["A", "B"]
    assert result.final_model["accuracy"] == 1.0
    assert result.iterations == 1


def test_converges_without_scoring_when_no_true_labels(monkeypatch):
    monkeypatch.setattr(
        clf_orch,
        "execute_generated_classifier",
        _stub_executor([{"ok": True, "y_pred": ["A", "A"], "m_current": {"algorithm": "stub"}}]),
    )
    result = clf_orch.run_classification_agent(
        "job", TRAIN_X, TRAIN_Y, TEST_X, FEATURES, CLASSES,
        test_y_true=None, modeler=DummyClassifierModeler(),
    )
    assert result.status == "converged"
    assert "accuracy" not in result.final_model


def test_retries_on_execution_error_then_succeeds(monkeypatch):
    monkeypatch.setattr(
        clf_orch,
        "execute_generated_classifier",
        _stub_executor([
            {"ok": False, "error": "SyntaxError: boom"},
            {"ok": True, "y_pred": ["A", "B"], "m_current": {"algorithm": "fallback"}},
        ]),
    )
    result = clf_orch.run_classification_agent(
        "job", TRAIN_X, TRAIN_Y, TEST_X, FEATURES, CLASSES, modeler=DummyClassifierModeler()
    )
    assert result.status == "converged"
    assert result.iterations == 2


def test_exhausts_retries_and_reports_error(monkeypatch):
    monkeypatch.setattr(
        clf_orch,
        "execute_generated_classifier",
        _stub_executor([{"ok": False, "error": "boom"}]),
    )
    result = clf_orch.run_classification_agent(
        "job", TRAIN_X, TRAIN_Y, TEST_X, FEATURES, CLASSES, modeler=DummyClassifierModeler()
    )
    assert result.status == "error"
    assert result.iterations == clf_orch.MAX_EXECUTION_ATTEMPTS


def test_modeler_exception_is_caught():
    class Boom:
        def propose(self, *args, **kwargs):
            raise RuntimeError("modeler died")

    result = clf_orch.run_classification_agent("job", TRAIN_X, TRAIN_Y, TEST_X, FEATURES, CLASSES, modeler=Boom())
    assert result.status == "error"
    assert "modeler died" in result.message

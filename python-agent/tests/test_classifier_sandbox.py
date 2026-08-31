"""Tests for the classification sandbox (tools/sandbox.py's
execute_generated_classifier / run_local_classifier).

Mirrors test_sandbox.py's style for the curve-fit sandbox: success, bad
code, timeout, and — the one genuinely new risk this data shape introduces
— confirming true test labels never reach the subprocess at all.
"""

from tools.sandbox import execute_generated_classifier

X_TRAIN = [[1.0, 2.0], [2.0, 1.0], [8.0, 9.0], [9.0, 8.0]]
Y_TRAIN = ["A", "A", "B", "B"]
X_TEST = [[1.5, 1.5], [8.5, 8.5]]
FEATURES = ["f1", "f2"]
CLASSES = ["A", "B"]


def test_success_returns_predictions_and_model_info():
    code = (
        "y_pred = ['A', 'B']\n"
        "m = {'algorithm': 'stub', 'hyperparams': {}}\n"
    )
    result = execute_generated_classifier(code, X_TRAIN, Y_TRAIN, X_TEST, FEATURES, CLASSES, timeout_s=10)
    assert result["ok"] is True
    assert result["y_pred"] == ["A", "B"]
    assert result["m_current"]["algorithm"] == "stub"


def test_real_random_forest_classifies_a_trivially_separable_set():
    # A generous timeout: this subprocess's FIRST import of sklearn (its own
    # C-extension load, on top of numpy/scipy's) is measurably slower than
    # later ones under full-suite disk/CPU contention — seen flaking at
    # timeout_s=10 only when run alongside many other tests, never in
    # isolation. This test checks correctness, not speed, so give it room.
    code = (
        "from sklearn.ensemble import RandomForestClassifier\n"
        "clf = RandomForestClassifier(n_estimators=50, random_state=0)\n"
        "clf.fit(X_train, y_train)\n"
        "y_pred = clf.predict(X_test).tolist()\n"
        "m = {'algorithm': 'RandomForestClassifier', 'hyperparams': {}}\n"
    )
    result = execute_generated_classifier(code, X_TRAIN, Y_TRAIN, X_TEST, FEATURES, CLASSES, timeout_s=25)
    assert result["ok"] is True
    assert result["y_pred"] == ["A", "B"]  # (1.5,1.5) nearer the A cluster, (8.5,8.5) nearer B


def test_bad_code_returns_traceback():
    result = execute_generated_classifier(
        "y_pred = undefined_name\nm = {}", X_TRAIN, Y_TRAIN, X_TEST, FEATURES, CLASSES, timeout_s=10
    )
    assert result["ok"] is False
    assert "NameError" in result["error"]


def test_shape_mismatch_is_reported():
    code = "y_pred = ['A']\nm = {}"  # only 1 label for 2 test rows
    result = execute_generated_classifier(code, X_TRAIN, Y_TRAIN, X_TEST, FEATURES, CLASSES, timeout_s=10)
    assert result["ok"] is False
    assert "y_pred has 1 entries but X_test has 2 rows" in result["error"]


def test_missing_m_is_reported():
    result = execute_generated_classifier(
        "y_pred = ['A', 'B']\n", X_TRAIN, Y_TRAIN, X_TEST, FEATURES, CLASSES, timeout_s=10
    )
    assert result["ok"] is False
    assert "must define a dict named `m`" in result["error"]


def test_timeout_is_enforced():
    result = execute_generated_classifier(
        "while True:\n    pass", X_TRAIN, Y_TRAIN, X_TEST, FEATURES, CLASSES, timeout_s=1
    )
    assert result["ok"] is False
    assert "timed out" in result["error"]


def test_true_test_labels_are_never_available_to_the_sandboxed_script():
    """The one genuinely new leakage risk this data shape introduces: if the
    harness ever accidentally passed true labels for X_test into the
    subprocess, a script could read them and "cheat" by echoing them back.
    Confirm the variable simply does not exist."""
    code = "y_pred = list(y_test)\nm = {}"  # y_test is never defined by the harness
    result = execute_generated_classifier(code, X_TRAIN, Y_TRAIN, X_TEST, FEATURES, CLASSES, timeout_s=10)
    assert result["ok"] is False
    assert "NameError" in result["error"]
    assert "y_test" in result["error"]

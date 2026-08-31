"""End-to-end test of the LITHOLOGY method's offline path: the real
OfflineClassifier, through the real sandbox subprocess, against the
synthetic demo well-log scenario — mirrors test_offline_convergence.py's
role for TDEM (a real, not-mocked, run of the whole classification path).
"""

from app.agent.classifier_modeler import OfflineClassifier
from app.agent.classification_orchestrator import run_classification_agent
from app.agent.lithology_demo import build_demo_well_log


def test_offline_classifier_achieves_high_accuracy_on_demo_column():
    demo = build_demo_well_log()
    curve_names = list(demo["curves"].keys())

    def rows(indices):
        return [[demo["curves"][name][i] for name in curve_names] for i in indices]

    train_x = rows(demo["train_idx"])
    train_y = [demo["true_labels"][i] for i in demo["train_idx"]]
    test_x = rows(demo["predict_idx"])
    test_y_true = [demo["true_labels"][i] for i in demo["predict_idx"]]

    result = run_classification_agent(
        "demo-job",
        train_x,
        train_y,
        test_x,
        curve_names,
        demo["classes"],
        test_y_true=test_y_true,
        modeler=OfflineClassifier(),
    )

    assert result.status == "converged"
    # The demo curves are noise-free and class-separable by construction —
    # a correctly-configured Random Forest should get this essentially exactly.
    assert result.final_model["accuracy"] >= 0.95

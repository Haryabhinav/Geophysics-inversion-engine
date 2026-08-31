"""The classification loop for the LITHOLOGY method.

Unlike run_inversion_agent's iterate-to-tolerance loop, this is
single-shot: the classifier modeler gets ONE real attempt (plus a bounded
retry purely for sandbox EXECUTION errors — syntax/shape bugs — never for a
mediocre score). Repeatedly re-scoring against a small held-out set and
asking the model to "try again" is textbook validation-set leakage, not a
legitimate optimization loop, and in production there is usually no ground
truth for `predict` to score against anyway (see schemas_classification.py's
docstring) — so there is nothing legitimate to iterate on beyond fixing
crashes.

Returns an InversionResult (not a new result schema) so every downstream
piece of Node infrastructure — persistence, alerts, dashboard, SSE — works
unchanged; lithology-specific detail lives inside `final_model`.
"""

from __future__ import annotations

import logging
from typing import Any

from tools.sandbox import execute_generated_classifier

from ..schemas import InversionResult
from .classifier_modeler import ClassifierModeler, build_classifier_modeler

logger = logging.getLogger("python-agent.classification_orchestrator")

MAX_EXECUTION_ATTEMPTS = 3


def _score(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    """Independently scored by the harness from ground truth the sandboxed
    script never saw — mirrors orchestrator.py's _recompute_l2 lesson:
    never trust a subprocess's self-reported result."""
    n = len(y_true)
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / n if n else 0.0

    classes = sorted(set(y_true) | set(y_pred))
    f1s = []
    for c in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        f1s.append(f1)
    f1_macro = sum(f1s) / len(f1s) if f1s else 0.0
    return {"accuracy": accuracy, "f1_macro": f1_macro}


def run_classification_agent(
    job_id: str,
    train_x: list[list[float]],
    train_y: list[str],
    test_x: list[list[float]],
    feature_names: list[str],
    classes: list[str],
    test_y_true: list[str] | None = None,
    modeler: ClassifierModeler | None = None,
    timeout_s: int = 20,
) -> InversionResult:
    # `modeler` is injectable for testing; production callers leave it None.
    if modeler is None:
        modeler = build_classifier_modeler()

    data_summary = {
        "n_train": len(train_y),
        "n_test": len(test_x),
        "feature_names": feature_names,
        "classes": classes,
    }

    feedback: dict[str, Any] | None = None
    last_error: str | None = None

    for attempt in range(MAX_EXECUTION_ATTEMPTS):
        try:
            code = modeler.propose(attempt, data_summary, feedback)
        except Exception as exc:  # modeler/LLM failure — abort cleanly
            logger.exception("Classifier modeler failed on attempt %d", attempt)
            return InversionResult(
                jobId=job_id,
                status="error",
                iterations=attempt,
                message=f"Modeler error: {exc!r}",
            )

        result = execute_generated_classifier(
            code, train_x, train_y, test_x, feature_names, classes, timeout_s=timeout_s
        )

        if not result["ok"]:
            last_error = result["error"]
            logger.info("Attempt %d: sandbox error: %s", attempt, last_error.splitlines()[-1:])
            feedback = {"error": last_error}
            continue

        y_pred = result["y_pred"]
        model_info = result["m_current"]

        final_model: dict[str, Any] = {
            "predicted_labels": y_pred,
            "algorithm": model_info.get("algorithm"),
            "hyperparams": model_info.get("hyperparams"),
        }
        score = None
        if test_y_true is not None:
            score = _score(test_y_true, y_pred)
            final_model["accuracy"] = score["accuracy"]
            final_model["f1_macro"] = score["f1_macro"]

        message = "Classification completed"
        if score is not None:
            message += f" (accuracy={score['accuracy']:.3f}, f1_macro={score['f1_macro']:.3f})"
        logger.info("Job %s: %s", job_id, message)

        return InversionResult(
            jobId=job_id,
            status="converged",
            final_model=final_model,
            l2_norm_error=None,
            iterations=attempt + 1,
            message=message,
        )

    return InversionResult(
        jobId=job_id,
        status="error",
        iterations=MAX_EXECUTION_ATTEMPTS,
        message=f"All {MAX_EXECUTION_ATTEMPTS} attempts failed to execute. Last error: {last_error}",
    )

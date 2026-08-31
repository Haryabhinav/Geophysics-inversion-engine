"""Classifier modelers for the LITHOLOGY method — sibling to modeler.py's
regression/curve-fit modelers, but for a fundamentally different problem
shape: discrete labels from a small labeled training set, not a continuous
curve. See classification_orchestrator.py for why this is single-shot
rather than an iterate-to-tolerance loop.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol

from ..config import settings
from .llm_client import LLMClient, build_llm_client
from .modeler import _extract_python

logger = logging.getLogger("python-agent.classifier_modeler")

ClassifierFeedback = dict[str, Any] | None


class ClassifierModeler(Protocol):
    def propose(self, iteration: int, data_summary: dict[str, Any], feedback: ClassifierFeedback) -> str: ...


# --------------------------------------------------------------------------- #
# Real agent: an LLM authors a single-shot classification script.
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
You are an autonomous lithology-classification agent. You are given a small
LABELED training set of well-log measurements (`X_train`, `y_train` —
feature matrix and lithology-class labels) and an UNLABELED set to classify
(`X_test`), plus `feature_names` (the log curve names, in column order) and
`classes` (the canonical lithology labels).

CLASSIFY IN A SINGLE SCRIPT — do not hand-tune parameters across turns.
Instead, do your own internal cross-validation on X_train/y_train to pick a
reasonable model and hyperparameters, then fit on all of X_train and predict
X_test.

Hard rules:
- Output ONLY valid Python code. No prose, no explanation, no markdown outside code.
- End with TOP-LEVEL assignments (never inside a function):
  `y_pred = [...]` (one label per row of X_test, using exactly the strings
  in `classes`) and `m = {'algorithm': str, 'hyperparams': {...}}`.
- `X_train`, `y_train`, `X_test`, `feature_names`, `classes` are already
  defined. Do NOT redefine or reload them.
- Do NOT compute accuracy/F1 yourself and do NOT call print(); the harness
  scores your predictions independently against ground truth you never see.

If your script errors, you receive the traceback — fix the bug and output a
corrected single-script classifier.
"""


class LLMClassifierModeler:
    def __init__(self, client: LLMClient | None = None) -> None:
        # `client` is injectable for testing; production callers leave it None.
        self._client = client or build_llm_client("gemini", settings.gemini_model)

    def propose(self, iteration: int, data_summary: dict[str, Any], feedback: ClassifierFeedback) -> str:
        if iteration == 0:
            user = (
                "Training set summary:\n"
                f"- training samples: {data_summary['n_train']}\n"
                f"- feature_names (column order): {data_summary['feature_names']}\n"
                f"- classes: {data_summary['classes']}\n"
                f"- test samples to classify: {data_summary['n_test']}\n\n"
                "Write your single-script classifier now."
            )
        else:
            assert feedback is not None
            user = (
                "Your previous script failed to execute. Traceback:\n"
                f"{feedback['error']}\n\n"
                "Fix the code and output a corrected single-script classifier."
            )
        history = [{"role": "user", "parts": [{"text": user}]}]
        text = self._client.generate(SYSTEM_PROMPT, history, settings.gemini_max_tokens)
        return _extract_python(text)


# --------------------------------------------------------------------------- #
# Test double AND recommended production default: a fixed classical
# baseline. Lithology-from-logs is a well-benchmarked supervised problem the
# GR/resistivity/density/sonic crossplot rules petrophysicists already use
# by hand are exactly what a Random Forest captures — the same lesson TDEM's
# live testing taught (classical beats LLM-authored one-shot code for a
# well-posed problem), so this is deliberately the CLASSIFIER_MODE=offline
# default rather than just a fallback.
# --------------------------------------------------------------------------- #


class OfflineClassifier:
    """Real (not-a-stub) RandomForest baseline — emits code that still runs
    through the sandbox, so the execution/security path stays uniform
    regardless of which modeler authored it."""

    def propose(self, iteration: int, data_summary: dict[str, Any], feedback: ClassifierFeedback) -> str:
        if iteration == 0:
            return (
                "from sklearn.ensemble import RandomForestClassifier\n"
                "clf = RandomForestClassifier(n_estimators=200, max_depth=8, "
                "random_state=42, class_weight='balanced')\n"
                "clf.fit(X_train, y_train)\n"
                "y_pred = clf.predict(X_test).tolist()\n"
                "m = {'algorithm': 'RandomForestClassifier', "
                "'hyperparams': {'n_estimators': 200, 'max_depth': 8}}\n"
            )
        # A previous attempt raised a sandbox execution error — retreat to a
        # simpler, harder-to-break classifier rather than repeating the same code.
        return (
            "from sklearn.tree import DecisionTreeClassifier\n"
            "clf = DecisionTreeClassifier(max_depth=4, random_state=42)\n"
            "clf.fit(X_train, y_train)\n"
            "y_pred = clf.predict(X_test).tolist()\n"
            "m = {'algorithm': 'DecisionTreeClassifier (fallback)', 'hyperparams': {'max_depth': 4}}\n"
        )


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #


def build_classifier_modeler() -> ClassifierModeler:
    mode = settings.classifier_mode.lower()
    has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    if mode == "offline":
        logger.info("Using OfflineClassifier (CLASSIFIER_MODE=offline)")
        return OfflineClassifier()

    if mode == "llm" or (mode == "auto" and has_key):
        logger.info("Using LLMClassifierModeler (%s)", settings.gemini_model)
        return LLMClassifierModeler()

    logger.warning(
        "GEMINI_API_KEY not set — falling back to OfflineClassifier. "
        "Set the key (or CLASSIFIER_MODE=llm) to use Gemini."
    )
    return OfflineClassifier()

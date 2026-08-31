"""Interpretation for the LITHOLOGY method.

Reuses the same InterpretationResult shape as interpreter.py, but reads
predicted lithology labels (final_model['predicted_labels']) instead of a
resistivity/depth model — interpreter.py's RuleBasedInterpreter heuristic
is meaningless for a discrete label sequence, so this is a dedicated
sibling rather than a branch bolted onto that file.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from typing import Any, Protocol

from ..config import settings
from ..schemas import InterpretationResult, InversionResult
from .llm_client import LLMClient, build_llm_client

logger = logging.getLogger("python-agent.lithology_interpreter")

_TARGET_KEYWORDS = ("clay", "wet", "saturated", "aquifer", "water", "coal", "ore")


class LithologyInterpreter(Protocol):
    def interpret(
        self, site_id: str, result: InversionResult, site_note: str | None
    ) -> InterpretationResult: ...


# --------------------------------------------------------------------------- #
# Real agent
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
You are a geological interpretation assistant. You are given predicted
lithology labels for a borehole interval (from a well-log classifier) and
optional free-text site context (a driller's log, a geological note).

Your job:
1. Summarize the predicted lithology sequence in plain language.
2. If the site context mentions a target material (e.g. clay, coal, an
   aquifer, ore), say whether the predicted labels corroborate it.
3. Decide whether this looks like a drilling target / anomaly worth flagging.
4. State your confidence: "high" if the classifier's own reported accuracy
   is high AND the site context corroborates the labels, "medium" if only
   one of those holds, "low" otherwise.

Respond with ONLY a single JSON object (no markdown fences, no prose outside
it) with exactly these keys:
{"summary": str, "confidence": "high"|"medium"|"low", "flagged_anomaly": bool,
"reasoning": str}
"""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    match = _JSON_OBJECT.search(text)
    if not match:
        raise ValueError(f"no JSON object found in interpreter reply: {text!r}")
    return json.loads(match.group(0))


class LLMLithologyInterpreter:
    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or build_llm_client("gemini", settings.gemini_model)

    def interpret(
        self, site_id: str, result: InversionResult, site_note: str | None
    ) -> InterpretationResult:
        labels = result.final_model.get("predicted_labels", [])
        counts = Counter(labels)
        accuracy = result.final_model.get("accuracy")
        user = (
            f"Predicted lithology label counts: {dict(counts)}\n"
            f"Classifier accuracy (if scored): {accuracy}\n"
            f"Site context: {site_note or '(none provided)'}\n\n"
            "Respond with the JSON object described in your instructions."
        )
        history = [{"role": "user", "parts": [{"text": user}]}]
        text = self._client.generate(SYSTEM_PROMPT, history, settings.gemini_max_tokens)
        try:
            parsed = _extract_json(text)
            return InterpretationResult(
                siteId=site_id,
                summary=str(parsed["summary"]),
                confidence=parsed["confidence"],
                flagged_anomaly=bool(parsed["flagged_anomaly"]),
                reasoning=str(parsed["reasoning"]),
            )
        except Exception as exc:
            logger.warning("Lithology interpreter reply failed to parse (%r); reply was: %s", exc, text)
            return InterpretationResult(
                siteId=site_id,
                summary="Interpretation unavailable — the model reply could not be parsed.",
                confidence="low",
                flagged_anomaly=False,
                reasoning=f"Parse error: {exc!r}",
            )


# --------------------------------------------------------------------------- #
# Test double / offline default
# --------------------------------------------------------------------------- #


class RuleBasedLithologyInterpreter:
    """Deterministic template test double — no API key needed, mirroring
    RuleBasedInterpreter's role for the curve-fit methods."""

    def interpret(
        self, site_id: str, result: InversionResult, site_note: str | None
    ) -> InterpretationResult:
        labels: list[str] = result.final_model.get("predicted_labels", [])
        counts = Counter(labels)
        note = (site_note or "").lower()
        note_hit = any(kw in note for kw in _TARGET_KEYWORDS)
        dominant = counts.most_common(1)[0][0] if counts else "unknown"
        flagged = note_hit and any(kw in dominant.lower() for kw in _TARGET_KEYWORDS)
        accuracy = result.final_model.get("accuracy")

        if accuracy is not None and accuracy >= 0.85 and note_hit:
            confidence = "high"
        elif labels:
            confidence = "medium"
        else:
            confidence = "low"

        return InterpretationResult(
            siteId=site_id,
            summary=(
                f"Predicted lithology dominated by {dominant} "
                f"({counts.get(dominant, 0)}/{len(labels)} intervals)."
                if labels
                else "No predicted lithology available."
            ),
            confidence=confidence,
            flagged_anomaly=flagged,
            reasoning=(
                f"Label distribution: {dict(counts)}. Site note "
                f"{'supports' if note_hit else 'does not mention'} a target lithology."
            ),
        )


def build_lithology_interpreter() -> LithologyInterpreter:
    mode = settings.interpreter_mode.lower()
    has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    if mode == "offline":
        logger.info("Using RuleBasedLithologyInterpreter (INTERPRETER_MODE=offline)")
        return RuleBasedLithologyInterpreter()

    if mode == "llm" or (mode == "auto" and has_key):
        logger.info("Using LLMLithologyInterpreter (%s)", settings.gemini_model)
        return LLMLithologyInterpreter()

    logger.warning(
        "GEMINI_API_KEY not set — falling back to RuleBasedLithologyInterpreter."
    )
    return RuleBasedLithologyInterpreter()

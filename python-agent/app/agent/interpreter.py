"""The Interpretation Agent.

Runs *after* an inversion converges (or hits max iterations). Unlike the
inversion modeler, there is no propose/execute/sandbox loop here — the model
isn't authoring executable code, just reading a converged (possibly
non-unique — see EQUIVALENCE_BAND in orchestrator.py) numeric earth model
plus optional free-text site context (a driller's log, a geological note)
and producing a structured natural-language interpretation. This is the part
of the pipeline that's genuinely LLM-shaped: reading unstructured text and
reasoning over it isn't something the classical inversion solver can do.

Two implementations, mirroring modeler.py's Modeler/OfflineHeuristicModeler
split:

* ``LLMInterpreter`` — the real agent, via the provider-agnostic LLMClient.
* ``RuleBasedInterpreter`` — a deterministic template test double (no API key
  needed), so the pipeline is demoable/testable for free, same role as
  OfflineHeuristicModeler plays for the inversion loop.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Protocol

from ..config import settings
from ..schemas import InterpretationResult, InversionResult
from .llm_client import LLMClient, build_llm_client

logger = logging.getLogger("python-agent.interpreter")


class Interpreter(Protocol):
    def interpret(
        self, site_id: str, inversion: InversionResult, site_note: str | None
    ) -> InterpretationResult: ...


# --------------------------------------------------------------------------- #
# Real agent: an LLM reads the numeric model + text context.
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
You are a geological interpretation assistant. You are given a converged (or \
best-effort) subsurface resistivity model from a TDEM inversion, optionally \
several other DISTINCT models that fit the observed data almost equally well \
(EM inversion is famously non-unique — this is called "equivalence"), and \
optionally free-text site context such as a driller's log or geological note.

Your job:
1. If multiple equivalent models are given, use the site context (if any) to \
say which one is more geologically plausible, and why.
2. Write a short, plain-language summary a field geologist would find useful.
3. Decide whether this looks like a drilling target / anomaly worth flagging.
4. State your confidence: "high" only if site context clearly supports one \
interpretation, "medium" if the model alone is fairly unambiguous, "low" if \
the models are ambiguous and there's no context to disambiguate them.

Respond with ONLY a single JSON object (no markdown fences, no prose outside \
it) with exactly these keys:
{"summary": str, "confidence": "high"|"medium"|"low", "flagged_anomaly": bool, \
"reasoning": str}
"""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    match = _JSON_OBJECT.search(text)
    if not match:
        raise ValueError(f"no JSON object found in interpreter reply: {text!r}")
    return json.loads(match.group(0))


def _user_prompt(inversion: InversionResult, site_note: str | None) -> str:
    lines = [
        f"Best-fit model: {json.dumps(inversion.final_model)}",
        f"Relative misfit (L2): {inversion.l2_norm_error}",
    ]
    if inversion.equivalent_models:
        lines.append("Other equally-good (equivalent) models:")
        for entry in inversion.equivalent_models:
            lines.append(f"  - {json.dumps(entry['model'])} (L2={entry['l2_norm_error']:.4g})")
    lines.append(f"Site context: {site_note or '(none provided)'}")
    lines.append("\nRespond with the JSON object described in your instructions.")
    return "\n".join(lines)


class LLMInterpreter:
    def __init__(self, client: LLMClient | None = None) -> None:
        # `client` is injectable for testing; production callers leave it None.
        self._client = client or build_llm_client("gemini", settings.gemini_model)

    def interpret(
        self, site_id: str, inversion: InversionResult, site_note: str | None
    ) -> InterpretationResult:
        history = [{"role": "user", "parts": [{"text": _user_prompt(inversion, site_note)}]}]
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
            logger.warning("Interpreter reply failed to parse (%r); reply was: %s", exc, text)
            return InterpretationResult(
                siteId=site_id,
                summary="Interpretation unavailable — the model reply could not be parsed.",
                confidence="low",
                flagged_anomaly=False,
                reasoning=f"Parse error: {exc!r}",
            )


# --------------------------------------------------------------------------- #
# Test double: deterministic, template-based interpretation.
# --------------------------------------------------------------------------- #

# Resistivities below this are consistent with saturated clay/conductive
# material — a coarse but real rule of thumb geophysicists use.
_CONDUCTIVE_OHM_M = 15.0
_CONDUCTIVE_KEYWORDS = ("clay", "wet", "saturated", "aquifer", "water")


def _resistivities(model: dict[str, Any]) -> list[float]:
    res = model.get("res") or []
    try:
        return [float(r) for r in res]
    except (TypeError, ValueError):
        return []


class RuleBasedInterpreter:
    """Template-based test double — no API key needed. Mirrors
    OfflineHeuristicModeler's role: a real (if simple) rule, not a stub, so
    the pipeline is demoable and testable for free."""

    def interpret(
        self, site_id: str, inversion: InversionResult, site_note: str | None
    ) -> InterpretationResult:
        note = (site_note or "").lower()
        note_hits_conductive = any(kw in note for kw in _CONDUCTIVE_KEYWORDS)
        resistivities = _resistivities(inversion.final_model)
        model_is_conductive = any(r < _CONDUCTIVE_OHM_M for r in resistivities if r > 0)
        n_equivalent = len(inversion.equivalent_models)

        if model_is_conductive and note_hits_conductive:
            return InterpretationResult(
                siteId=site_id,
                summary=(
                    "Low-resistivity layer detected, consistent with the site note "
                    "(saturated/clay-bearing material). Flagging as a candidate target."
                ),
                confidence="high",
                flagged_anomaly=True,
                reasoning=(
                    f"Model resistivities {resistivities} include a value below "
                    f"{_CONDUCTIVE_OHM_M} Ohm-m, and the site note contains a "
                    "conductive-material keyword — the numeric and textual "
                    "evidence agree."
                ),
            )

        if n_equivalent > 1:
            # Distinguish "there was no note" from "there was a note, and this
            # coarse keyword rule couldn't use it". Both leave the equivalence
            # unresolved, but claiming no context was available when a driller's
            # log IS on record is simply false, and that wording propagates
            # verbatim into the multi-method Joint Interpretation report.
            if note.strip():
                summary = (
                    f"{n_equivalent} distinct models fit the data almost equally well "
                    "(equivalence); the site note on record does not decide between them."
                )
                reasoning = (
                    "Multiple equivalent models. A site note is on record, but this "
                    "rule only matches a conductive-material keyword against a "
                    "low-resistivity layer, and that pairing is absent here — so the "
                    "note cannot disambiguate them. Reading the note as free text is "
                    "exactly what the LLM interpreter (INTERPRETER_MODE=llm) is for."
                )
            else:
                summary = (
                    f"{n_equivalent} distinct models fit the data almost equally well "
                    "(equivalence) and no site context was available to disambiguate them."
                )
                reasoning = "Multiple equivalent models, no disambiguating context provided."

            return InterpretationResult(
                siteId=site_id,
                summary=summary,
                confidence="low",
                flagged_anomaly=False,
                reasoning=reasoning,
            )

        return InterpretationResult(
            siteId=site_id,
            summary=f"Single well-constrained model: {inversion.final_model}.",
            confidence="medium",
            flagged_anomaly=model_is_conductive,
            reasoning="No equivalence ambiguity; interpretation follows the model directly.",
        )


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #


def build_interpreter() -> Interpreter:
    mode = settings.interpreter_mode.lower()
    has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    if mode == "offline":
        logger.info("Using RuleBasedInterpreter (INTERPRETER_MODE=offline)")
        return RuleBasedInterpreter()

    if mode == "llm" or (mode == "auto" and has_key):
        logger.info("Using LLMInterpreter (%s)", settings.gemini_model)
        return LLMInterpreter()

    logger.warning(
        "GEMINI_API_KEY not set — falling back to RuleBasedInterpreter. "
        "Set the key (or INTERPRETER_MODE=llm) to use the LLM interpreter."
    )
    return RuleBasedInterpreter()

"""Multi-method Joint Interpretation — the capstone of the multi-physics
expansion. Synthesizes results from SEVERAL different methods run at the
same site (e.g. gravity + magnetics + a borehole lithology log) into ONE
integrated geological report, explicitly reasoning about agreement and
disagreement between them.

This is the strongest defensible "why does this need an LLM" feature in
the whole platform: reconciling disagreeing evidence across
physically-unrelated measurement types (density for gravity, susceptibility
for magnetics, resistivity for MT/TDEM/ERT, direct lithology for a borehole
log) isn't something any classical algorithm does — it's exactly what a
senior integrative geophysicist does by hand.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Protocol

from ..config import settings
from ..schemas import JointInterpretationResult, MethodContribution, MethodResultInput
from .llm_client import LLMClient, build_llm_client

logger = logging.getLogger("python-agent.joint_interpreter")


class JointInterpreter(Protocol):
    def interpret(
        self, site_id: str, method_results: list[MethodResultInput], site_note: str | None
    ) -> JointInterpretationResult: ...


# --------------------------------------------------------------------------- #
# Real agent
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
You are a senior integrative geophysicist. You are given results from
SEVERAL DIFFERENT methods run at the SAME site over time — for example
gravity, magnetics, magnetotellurics, seismic, a borehole lithology log.
Each method has its own final model/prediction and, if available, its own
single-method interpretation and confidence. You are also given a free-text
site note.

Different methods are sensitive to different physical properties (density
for gravity, susceptibility for magnetics, resistivity for MT/TDEM/ERT,
acoustic impedance for seismic, direct lithology for a borehole log) and can
legitimately show DIFFERENT things about the SAME subsurface target — that
is not automatically a contradiction.

Your job:
1. State what each method, on its own, suggests (a target, a boundary, a
   rock type, or "inconclusive").
2. Cross-reference methods that speak to the same depth/location and decide,
   for each, whether the evidence is CONSISTENT (multiple signatures
   plausibly explained by one geological feature), CONFLICTING (cannot be
   reconciled under any simple single explanation), or INCONCLUSIVE.
3. When methods conflict, do NOT average or split the difference:
   a. Consider whether a depth offset, lateral offset, or a
      different-but-compatible lithology explains both observations (e.g. a
      resistive clay body vs. a magnetite-bearing schist both explain a
      gravity anomaly but disagree on magnetics — say so explicitly).
   b. Weigh direct, ground-truthed evidence (a borehole/lithology log at a
      specific depth) more heavily than remote, non-unique inversions
      (gravity/magnetics/EM) — but say when and why you are doing this.
   c. If nothing reconciles the conflict, say so plainly and set
      corroboration = "conflicting" rather than forcing false consensus.
4. Write a short, plain-language integrated summary.
5. confidence = "high" only if >=2 independent methods corroborate the SAME
   conclusion with no unexplained conflict; "medium" if the evidence points
   one way but is thin, single-method, or has a plausibly-explained
   conflict; "low" if methods are inconclusive or conflict unexplainably.
6. flagged_anomaly = true if the INTEGRATED picture (not any one method
   alone) suggests a drilling target, ore body, or other actionable feature.

Respond with ONLY a single JSON object (no markdown fences, no prose outside
it) with exactly these keys:
{"summary": str, "confidence": "high"|"medium"|"low", "flagged_anomaly": bool,
"reasoning": str, "corroboration": "consistent"|"conflicting"|"inconclusive",
"conflicts": [str, ...],
"methodContributions": [{"jobId": str, "dataType": str, "contributesTo": str,
"corroboration": "consistent"|"conflicting"|"inconclusive"}, ...]}
"""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    match = _JSON_OBJECT.search(text)
    if not match:
        raise ValueError(f"no JSON object found in joint interpreter reply: {text!r}")
    return json.loads(match.group(0))


def _user_prompt(method_results: list[MethodResultInput], site_note: str | None) -> str:
    lines = [f"Site note: {site_note or '(none provided)'}", ""]
    for r in method_results:
        lines.append(f"Method: {r.dataType} (job {r.jobId}, status={r.status})")
        lines.append(f"  Final model: {json.dumps(r.finalModel)}")
        if r.l2NormError is not None:
            lines.append(f"  Misfit (relative L2): {r.l2NormError}")
        if r.interpretation is not None:
            lines.append(
                f"  Single-method interpretation: summary={r.interpretation.summary!r}, "
                f"confidence={r.interpretation.confidence}, "
                f"flagged_anomaly={r.interpretation.flagged_anomaly}"
            )
        lines.append("")
    lines.append("Respond with the JSON object described in your instructions.")
    return "\n".join(lines)


class LLMJointInterpreter:
    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or build_llm_client("gemini", settings.gemini_model)

    def interpret(
        self, site_id: str, method_results: list[MethodResultInput], site_note: str | None
    ) -> JointInterpretationResult:
        history = [{"role": "user", "parts": [{"text": _user_prompt(method_results, site_note)}]}]
        text = self._client.generate(SYSTEM_PROMPT, history, settings.gemini_max_tokens)
        methods_considered = [r.dataType for r in method_results]
        try:
            parsed = _extract_json(text)
            contributions = [
                MethodContribution(
                    jobId=str(c["jobId"]),
                    dataType=str(c["dataType"]),
                    contributesTo=str(c["contributesTo"]),
                    corroboration=c["corroboration"],
                )
                for c in parsed.get("methodContributions", [])
            ]
            return JointInterpretationResult(
                siteId=site_id,
                summary=str(parsed["summary"]),
                confidence=parsed["confidence"],
                flagged_anomaly=bool(parsed["flagged_anomaly"]),
                reasoning=str(parsed["reasoning"]),
                corroboration=parsed["corroboration"],
                methodContributions=contributions,
                methodsConsidered=methods_considered,
                conflicts=[str(c) for c in parsed.get("conflicts", [])],
            )
        except Exception as exc:
            logger.warning("Joint interpreter reply failed to parse (%r); reply was: %s", exc, text)
            return JointInterpretationResult(
                siteId=site_id,
                summary="Joint interpretation unavailable — the model reply could not be parsed.",
                confidence="low",
                flagged_anomaly=False,
                reasoning=f"Parse error: {exc!r}",
                corroboration="inconclusive",
                methodsConsidered=methods_considered,
            )


# --------------------------------------------------------------------------- #
# Test double / offline default: deterministic corroboration counting.
# --------------------------------------------------------------------------- #


def _method_flag(r: MethodResultInput) -> bool | None:
    """None means "no determinable verdict" (no single-method interpretation
    to draw a flag from) — not counted either way."""
    return r.interpretation.flagged_anomaly if r.interpretation is not None else None


class RuleBasedJointInterpreter:
    """Deterministic corroboration counting — no API key needed, mirroring
    every other method's no-API-key-fallback pattern. The nuanced handling
    of genuine disagreement (depth offsets, alternate lithologies, weighting
    direct vs. remote evidence) is deliberately the LLM path's job; this
    fallback only needs to be a serviceable, honest, free default."""

    def interpret(
        self, site_id: str, method_results: list[MethodResultInput], site_note: str | None
    ) -> JointInterpretationResult:
        methods_considered = [r.dataType for r in method_results]
        flags = [(r, _method_flag(r)) for r in method_results]
        considered = [(r, f) for r, f in flags if f is not None]
        n_considered = len(considered)
        n_flag = sum(1 for _, f in considered if f)

        conflicts: list[str] = []
        if n_considered == 0:
            corroboration, confidence, flagged = "inconclusive", "low", False
            summary = "No method produced a determinable verdict to synthesize."
        elif n_flag >= 2:
            corroboration, confidence, flagged = "consistent", "high", True
            summary = f"{n_flag} of {n_considered} methods with a determinable verdict flagged an anomaly."
        elif n_flag == 1 and n_considered == 1:
            corroboration, confidence, flagged = "inconclusive", "low", True
            summary = "Only one method produced a determinable verdict; insufficient corroboration."
        elif n_flag == 1 and n_considered >= 2:
            corroboration, confidence, flagged = "conflicting", "medium", True
            flagging = [r.dataType for r, f in considered if f]
            quiet = [r.dataType for r, f in considered if not f]
            summary = f"{', '.join(flagging)} flagged an anomaly but {', '.join(quiet)} did not."
            conflicts.append(
                f"{', '.join(flagging)} indicate an anomaly while {', '.join(quiet)} do not — "
                "no rule-level reconciliation available; treat as medium-confidence pending further data."
            )
        else:  # n_flag == 0
            corroboration, confidence, flagged = "consistent", "medium", False
            summary = f"None of the {n_considered} methods with a determinable verdict flagged an anomaly."

        contributions = [
            MethodContribution(
                jobId=r.jobId,
                dataType=r.dataType,
                contributesTo=(
                    r.interpretation.summary if r.interpretation is not None else "no single-method interpretation available"
                ),
                singleMethodConfidence=(r.interpretation.confidence if r.interpretation is not None else None),
                corroboration=(corroboration if f is not None else "inconclusive"),
            )
            for r, f in flags
        ]

        return JointInterpretationResult(
            siteId=site_id,
            summary=summary,
            confidence=confidence,
            flagged_anomaly=flagged,
            reasoning=f"Corroboration counting across {methods_considered}: {n_flag}/{n_considered} flagged.",
            corroboration=corroboration,
            methodContributions=contributions,
            methodsConsidered=methods_considered,
            conflicts=conflicts,
        )


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #


def build_joint_interpreter() -> JointInterpreter:
    mode = settings.interpreter_mode.lower()
    has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    if mode == "offline":
        logger.info("Using RuleBasedJointInterpreter (INTERPRETER_MODE=offline)")
        return RuleBasedJointInterpreter()

    if mode == "llm" or (mode == "auto" and has_key):
        logger.info("Using LLMJointInterpreter (%s)", settings.gemini_model)
        return LLMJointInterpreter()

    logger.warning("GEMINI_API_KEY not set — falling back to RuleBasedJointInterpreter.")
    return RuleBasedJointInterpreter()

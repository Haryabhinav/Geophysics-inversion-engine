"""The Site Report Generator — an LLM-drafted markdown report summarizing a
site's findings, confidence, and recommended next steps.

Downstream of the same data joint_interpreter.py already reads: if Node has
a fresh JointInterpretationResult for this site, it's forwarded here so the
report builds on that synthesis rather than re-deriving cross-method
agreement/conflict reasoning from scratch. If not (e.g. only one method has
been run at this site), the generator works directly from the run history.

No offline fallback, by the same deliberate choice as
app/agent/data_cleaner.py and app/agent/chat_agent.py: drafting readable,
well-organized prose for a client-facing report is exactly the kind of
judgment call a rule-based test double can't credibly fake. build_report_generator()
requires a Gemini key and raises ReportUnavailableError (surfaced as a clear
503, not a crash) when one isn't configured.
"""

from __future__ import annotations

import json
import logging
import os
import re

from ..schemas import JointInterpretationResult, MethodResultInput
from ..schemas_report import ReportResult
from .llm_client import LLMClient, build_llm_client

logger = logging.getLogger("python-agent.report_generator")

SYSTEM_PROMPT = """\
You are a geophysicist drafting a client-facing site report from a survey's \
run history and (if available) an integrated joint interpretation across \
methods. Write a well-organized markdown report a non-specialist client \
could read, and a specialist could still trust.

Structure the report with these markdown sections:
## Summary
## Methods Surveyed
## Findings
## Confidence & Caveats
## Recommended Next Steps

Ground every claim in the given data only — never invent a run, a number, or
a finding that isn't in the data given to you. If the evidence is thin or
conflicting, say so plainly in "Confidence & Caveats" rather than
overstating certainty.

Respond with ONLY a single JSON object (no markdown fences, no prose outside
it) with exactly these keys:
{"markdown": str, "summary": str}

"markdown" is the full report body described above. "summary" is one plain-
language sentence suitable for a report-history list view.
"""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class ReportUnavailableError(RuntimeError):
    """Raised when the Site Report Generator has no LLM client to work with."""


def _extract_json(text: str) -> dict:
    match = _JSON_OBJECT.search(text)
    if not match:
        raise ValueError(f"no JSON object found in report generator reply: {text!r}")
    return json.loads(match.group(0))


def _user_prompt(
    run_history: list[MethodResultInput],
    site_note: str | None,
    joint_interpretation: JointInterpretationResult | None,
) -> str:
    lines = [f"Site note: {site_note or '(none provided)'}", "", "Run history:"]
    for r in run_history:
        lines.append(f"Method: {r.dataType} (job {r.jobId}, status={r.status})")
        lines.append(f"  Final model: {json.dumps(r.finalModel)}")
        if r.l2NormError is not None:
            lines.append(f"  Misfit (relative L2): {r.l2NormError}")
        if r.interpretation is not None:
            lines.append(
                f"  Interpretation: summary={r.interpretation.summary!r}, "
                f"confidence={r.interpretation.confidence}, "
                f"flagged_anomaly={r.interpretation.flagged_anomaly}"
            )
        lines.append("")

    if joint_interpretation is not None:
        lines.append("Existing joint interpretation across methods:")
        lines.append(f"  Summary: {joint_interpretation.summary}")
        lines.append(f"  Confidence: {joint_interpretation.confidence}")
        lines.append(f"  Corroboration: {joint_interpretation.corroboration}")
        lines.append(f"  Reasoning: {joint_interpretation.reasoning}")
        if joint_interpretation.conflicts:
            lines.append(f"  Conflicts: {'; '.join(joint_interpretation.conflicts)}")
        lines.append("")

    lines.append("Respond with the JSON object described in your instructions.")
    return "\n".join(lines)


class SiteReportGenerator:
    def __init__(self, client: LLMClient | None = None, model: str | None = None) -> None:
        # `client` is injectable for testing; production callers leave it None.
        if client is not None:
            self._client = client
        else:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ReportUnavailableError(
                    "Site report generation requires GEMINI_API_KEY to be configured on the server."
                )
            from ..config import settings

            self._client = build_llm_client("gemini", model or settings.gemini_model)

    def generate(
        self,
        site_id: str,
        run_history: list[MethodResultInput],
        site_note: str | None,
        joint_interpretation: JointInterpretationResult | None,
    ) -> ReportResult:
        from ..config import settings

        prompt = _user_prompt(run_history, site_note, joint_interpretation)
        history = [{"role": "user", "parts": [{"text": prompt}]}]
        text = self._client.generate(SYSTEM_PROMPT, history, settings.gemini_max_tokens)
        parsed = _extract_json(text)
        return ReportResult(
            siteId=site_id,
            markdown=str(parsed["markdown"]),
            summary=str(parsed["summary"]),
        )


def build_report_generator() -> SiteReportGenerator:
    """No mode toggle, unlike build_interpreter/build_joint_interpreter —
    this stage is LLM-only by deliberate choice (see module docstring).
    Raises ReportUnavailableError (not a generic exception) so main.py can
    translate it into a clear 503 rather than a 500."""
    return SiteReportGenerator()

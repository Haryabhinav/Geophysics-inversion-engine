"""Tests for the Site Report Generator (app/agent/report_generator.py).

SiteReportGenerator is tested with a stubbed LLMClient — no network, no API
key — same style as test_data_cleaner.py / test_chat_agent.py. There is no
offline/rule-based double to test here: this stage is deliberately LLM-only
(see the module docstring for why), so `build_report_generator()` without a
key configured is itself a test case, not a gap.
"""

import pytest

from app.agent.report_generator import (
    ReportUnavailableError,
    SiteReportGenerator,
    build_report_generator,
)
from app.schemas import InterpretationResult, JointInterpretationResult, MethodResultInput


def _run(job_id="job-1"):
    return MethodResultInput(
        jobId=job_id,
        dataType="TDEM",
        status="converged",
        finalModel={"resistivity": 50.0, "thickness": 10.0},
        l2NormError=0.04,
        interpretation=InterpretationResult(
            siteId="site-1",
            summary="Conductive layer at depth.",
            confidence="high",
            flagged_anomaly=True,
            reasoning="Low resistivity zone consistent with target.",
        ),
    )


def test_generates_report_from_valid_reply():
    reply = (
        '{"markdown": "## Summary\\nA conductive target was identified.", '
        '"summary": "Conductive target identified at Site 1."}'
    )
    generator = SiteReportGenerator(client=_StubClient(reply))
    result = generator.generate("site-1", [_run()], "drilled to 20m", None)

    assert "## Summary" in result.markdown
    assert result.summary == "Conductive target identified at Site 1."
    assert result.siteId == "site-1"


def test_uses_existing_joint_interpretation_when_provided():
    reply = '{"markdown": "## Summary\\nIntegrated report.", "summary": "Integrated report."}'
    joint = JointInterpretationResult(
        siteId="site-1",
        summary="Two methods corroborate an anomaly.",
        confidence="high",
        flagged_anomaly=True,
        reasoning="Gravity and magnetics agree.",
        corroboration="consistent",
        methodsConsidered=["GRAVITY_SPHERE", "MAGNETICS_DIPOLE"],
    )
    generator = SiteReportGenerator(client=_StubClient(reply))
    result = generator.generate("site-1", [_run()], None, joint)

    assert result.summary == "Integrated report."


def test_raises_on_malformed_reply():
    generator = SiteReportGenerator(client=_StubClient("not json at all"))
    with pytest.raises(Exception):
        generator.generate("site-1", [_run()], None, None)


def test_build_report_generator_without_api_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ReportUnavailableError, match="GEMINI_API_KEY"):
        build_report_generator()


class _StubClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def generate(self, system, history, max_tokens):
        return self._reply

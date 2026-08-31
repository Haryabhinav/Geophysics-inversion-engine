"""Tests for the Site Chat Agent (app/agent/chat_agent.py).

SiteChatAgent is tested with a stubbed LLMClient — no network, no API key —
same style as test_data_cleaner.py. There is no offline/rule-based double to
test here: this stage is deliberately LLM-only (see the module docstring for
why), so `build_chat_agent()` without a key configured is itself a test
case, not a gap.
"""

import pytest

from app.agent.chat_agent import ChatUnavailableError, SiteChatAgent, build_chat_agent
from app.schemas import InterpretationResult, MethodResultInput
from app.schemas_chat import ChatTurn


class _StubClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def generate(self, system, history, max_tokens):
        return self._reply


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


def test_answers_valid_reply():
    reply = (
        '{"answer": "The TDEM run (job job-1) converged at L2=0.04 and flagged an anomaly.", '
        '"citedRuns": ["job-1"], "confidence": "high"}'
    )
    agent = SiteChatAgent(client=_StubClient(reply))
    result = agent.answer("site-1", "What did the TDEM run show?", [], [_run()], "drilled to 20m")

    assert "job-1" in result.answer
    assert result.citedRuns == ["job-1"]
    assert result.confidence == "high"


def test_includes_conversation_history_and_defaults_missing_cited_runs():
    reply = '{"answer": "No stored runs support that.", "confidence": "low"}'
    agent = SiteChatAgent(client=_StubClient(reply))
    history = [ChatTurn(role="user", content="Any anomalies?"), ChatTurn(role="assistant", content="Not yet.")]
    result = agent.answer("site-1", "Are you sure?", history, [], None)

    assert result.citedRuns == []
    assert result.confidence == "low"


def test_raises_on_malformed_reply():
    agent = SiteChatAgent(client=_StubClient("not json at all"))
    with pytest.raises(Exception):
        agent.answer("site-1", "What happened?", [], [_run()], None)


def test_build_chat_agent_without_api_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ChatUnavailableError, match="GEMINI_API_KEY"):
        build_chat_agent()

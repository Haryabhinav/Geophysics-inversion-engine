"""Pydantic models for the Site Chat Agent (app/agent/chat_agent.py).

A sibling to schemas_cleaning.py's pattern: this feature's request/response
shape doesn't overlay cleanly onto InversionJob or the joint-interpretation
schemas (it carries a free-text question and a running conversation), so it
gets its own small schema file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .schemas import Confidence, MethodResultInput


class ChatTurn(BaseModel):
    """One prior turn in the conversation, as Node persisted and replays it
    back so the agent has continuity across questions."""

    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4_000)


class ChatRequest(BaseModel):
    """What node-ingestion's POST /sites/:siteId/chat forwards to Python.

    `runHistory` is the same MethodResultInput shape already sent to
    /interpret/joint — Node assembles it the same way (repository.listBySite)
    so this feature needed no new persistence-reading code on the Node side.
    """

    siteId: str
    question: str = Field(..., min_length=1, max_length=2_000)
    history: list[ChatTurn] = Field(default_factory=list)
    runHistory: list[MethodResultInput] = Field(default_factory=list)
    siteNote: str | None = None


class ChatResponse(BaseModel):
    """The agent's answer, plus which runs it actually drew on — lets the UI
    show citations a user can click through to the underlying run, rather
    than asking them to trust free-text prose."""

    answer: str
    citedRuns: list[str] = Field(default_factory=list)
    confidence: Confidence

"""Pydantic models for the Site Report Generator (app/agent/report_generator.py).

A sibling to schemas_chat.py's pattern. Reuses MethodResultInput and
JointInterpretationResult from schemas.py directly — a report is downstream
of the same data joint interpretation already reads, so no new run-history
shape is needed.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .schemas import JointInterpretationResult, MethodResultInput


class ReportRequest(BaseModel):
    """What node-ingestion's POST /sites/:siteId/report forwards to Python."""

    siteId: str
    runHistory: list[MethodResultInput] = Field(..., min_length=1)
    siteNote: str | None = None
    # If Node already has a fresh joint interpretation for this site (e.g.
    # from a prior POST /sites/:siteId/interpret), it's forwarded here so the
    # report generator can build on it instead of re-deriving the same
    # cross-method synthesis from scratch.
    jointInterpretation: JointInterpretationResult | None = None


class ReportResult(BaseModel):
    """The generated report — markdown for in-app rendering (and a browser
    print/export path to PDF), plus a one-line summary for list views."""

    siteId: str
    markdown: str
    summary: str

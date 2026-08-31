"""Pydantic models for the raw-data Cleaning Agent (app/agent/data_cleaner.py).

A sibling to schemas_classification.py's pattern: a genuinely different data
shape (arbitrary raw text, not a validated {time, amplitude} pair) gets its
own small schema file rather than overloading InversionJob/CleanSeries, which
assume the data has already been parsed into two equal-length numeric arrays.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class CleaningRequest(BaseModel):
    """What node-ingestion's POST /clean/raw-data forwards to Python.

    `rawText` is the UNPARSED file contents — CSV, TSV, or loosely-structured
    text, headers present or not, extra junk columns possible. Deliberately
    not pre-split into columns: knowing which column is time and which is
    amplitude (or discovering the file has neither, in whatever order) is
    itself part of what the agent is asked to do.
    """

    dataType: str
    fileName: str
    rawText: str = Field(..., min_length=1, max_length=50_000)


class CleaningResult(BaseModel):
    """What the Cleaning Agent hands back — cleaned arrays ready to flow into
    the EXISTING ingest path (POST /ingest/field-data) unchanged, plus a
    plain-language account of what was done so a human can sanity-check an
    LLM-authored data transformation before trusting it."""

    timeSteps: list[float] = Field(..., min_length=1)
    amplitudes: list[float] = Field(..., min_length=1)
    originalCount: int
    droppedCount: int
    summary: str
    actions: list[str]

    @field_validator("amplitudes")
    @classmethod
    def _equal_length(cls, amplitudes: list[float], info: ValidationInfo) -> list[float]:
        # An LLM reply passes json.loads fine while still getting this wrong
        # (e.g. dropping the last amplitude but not the last time step) — the
        # downstream /ingest/field-data pairs these positionally with no
        # length check of its own, so catching it here is the only guard.
        time_steps = info.data.get("timeSteps")
        if time_steps is not None and len(amplitudes) != len(time_steps):
            raise ValueError(
                f"timeSteps ({len(time_steps)}) and amplitudes ({len(amplitudes)}) must have equal length"
            )
        return amplitudes

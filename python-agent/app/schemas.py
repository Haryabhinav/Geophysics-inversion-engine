"""Pydantic models for data crossing the WebSocket boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class CleanSeries(BaseModel):
    """A cleaned, index-aligned time/amplitude series."""

    time: list[float] = Field(..., min_length=1)
    amplitude: list[float] = Field(..., min_length=1)

    @field_validator("amplitude")
    @classmethod
    def _equal_length(cls, amplitude: list[float], info: ValidationInfo) -> list[float]:
        time = info.data.get("time")
        if time is not None and len(amplitude) != len(time):
            raise ValueError(
                f"time ({len(time)}) and amplitude ({len(amplitude)}) must have equal length"
            )
        return amplitude


class InversionJob(BaseModel):
    """The payload streamed from the Node.js ingestion layer."""

    jobId: str
    sensorId: str
    dataType: str
    data: CleanSeries
    # Optional free-text context for this site (driller's log, geological
    # note) — looked up by Node from whatever it was given via
    # POST /context/:siteId, and forwarded here so the Interpretation Agent
    # can use it. None if no context has been recorded for this sensor.
    siteNote: str | None = None
    # Fixed, non-curve metadata a method may need (e.g. station coordinates
    # for EARTHQUAKE_LOCATION). None for methods that don't need it.
    auxData: dict[str, list[float]] | None = None

    @field_validator("dataType")
    @classmethod
    def _known_method(cls, v: str) -> str:
        from .agent.methods import METHOD_REGISTRY

        if v not in METHOD_REGISTRY:
            raise ValueError(f"unknown dataType {v!r}; known: {sorted(METHOD_REGISTRY)}")
        return v


# Terminal states for an inversion run:
#   converged              -> L2 norm fell to/below tolerance
#   max_iterations_reached -> ran out of iterations; best-effort model returned
#   error                  -> every iteration failed to execute
InversionStatus = Literal["converged", "max_iterations_reached", "error"]

Confidence = Literal["high", "medium", "low"]


class InterpretationResult(BaseModel):
    """A geological interpretation of a converged (or best-effort) inversion
    result, optionally informed by free-text site context (drill logs,
    geological notes). Produced by the Interpretation Agent — see
    app/agent/interpreter.py."""

    siteId: str
    summary: str
    confidence: Confidence
    flagged_anomaly: bool
    reasoning: str


class InversionResult(BaseModel):
    """The response streamed back to the Node.js ingestion layer."""

    jobId: str
    status: InversionStatus
    final_model: dict[str, Any] = Field(default_factory=dict)
    l2_norm_error: float | None = None
    iterations: int = 0
    message: str | None = None
    # Best-fit predicted response (aligned with the observed series) and the
    # per-iteration L2 history — used by the dashboard to plot fit + convergence.
    predicted: list[float] | None = None
    l2_history: list[float] = Field(default_factory=list)
    # Distinct models whose misfit is within EQUIVALENCE_BAND of the best L2 —
    # EM inversion is famously non-unique ("equivalence"), so several different
    # resistivity/depth combinations can fit the data almost equally well. This
    # is the ambiguity a downstream interpretation step resolves using textual
    # geological context, since the misfit number alone can't.
    equivalent_models: list[dict[str, Any]] = Field(default_factory=list)
    # Populated by the Interpretation Agent after the inversion finishes; None
    # if interpretation wasn't run (e.g. status == "error").
    interpretation: InterpretationResult | None = None


# --------------------------------------------------------------------------- #
# Joint interpretation — synthesizes results from SEVERAL methods run at the
# same site into one integrated report. See app/agent/joint_interpreter.py.
# --------------------------------------------------------------------------- #

Corroboration = Literal["consistent", "conflicting", "inconclusive"]


class MethodContribution(BaseModel):
    """One method's standing within a joint interpretation: what it showed,
    and whether it agrees with the overall synthesis."""

    jobId: str
    dataType: str
    contributesTo: str
    singleMethodConfidence: Confidence | None = None
    corroboration: Corroboration


class JointInterpretationResult(BaseModel):
    """An integrated interpretation across multiple methods run at the same
    site — the strongest defensible "why an LLM" feature in the platform:
    reconciling disagreeing evidence across physically-unrelated measurement
    types isn't something any classical algorithm does."""

    siteId: str
    summary: str
    confidence: Confidence
    flagged_anomaly: bool
    reasoning: str
    corroboration: Corroboration
    methodContributions: list[MethodContribution] = Field(default_factory=list)
    methodsConsidered: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class MethodResultInput(BaseModel):
    """One method's stored result, as Node sends it into POST /interpret/joint."""

    jobId: str
    dataType: str
    status: str
    finalModel: dict[str, Any] = Field(default_factory=dict)
    l2NormError: float | None = None
    interpretation: InterpretationResult | None = None
    createdAt: int | None = None


class JointInterpretationRequest(BaseModel):
    """The payload Node sends to POST /interpret/joint."""

    siteId: str
    siteNote: str | None = None
    methodResults: list[MethodResultInput] = Field(..., min_length=1)

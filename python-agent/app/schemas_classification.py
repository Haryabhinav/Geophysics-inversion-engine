"""Schemas for the borehole lithology method — the one registered method
that's a CLASSIFICATION problem, not a curve fit, so it doesn't reuse
InversionJob/CleanSeries (a single time/amplitude pair). Kept as a sibling
module rather than folding into schemas.py, since the shapes genuinely don't
overlap.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class LogCurve(BaseModel):
    """One named well-log curve (e.g. gamma ray, resistivity)."""

    name: str
    unit: str
    values: list[float]


class WellLogSeries(BaseModel):
    """Depth-indexed log curves — every curve must have one value per depth."""

    depth: list[float] = Field(..., min_length=1)
    curves: list[LogCurve]

    @field_validator("curves")
    @classmethod
    def _curves_match_depth(cls, curves: list[LogCurve], info: ValidationInfo) -> list[LogCurve]:
        depth = info.data.get("depth")
        if depth is not None:
            for curve in curves:
                if len(curve.values) != len(depth):
                    raise ValueError(
                        f"curve {curve.name!r} has {len(curve.values)} values but "
                        f"depth has {len(depth)} entries"
                    )
        return curves


class LabeledWellLogSeries(WellLogSeries):
    """A WellLogSeries with a known lithology label per depth sample — the
    small "core-calibrated" training set. Features AND labels."""

    labels: list[str]

    @field_validator("labels")
    @classmethod
    def _labels_match_depth(cls, labels: list[str], info: ValidationInfo) -> list[str]:
        depth = info.data.get("depth")
        if depth is not None and len(labels) != len(depth):
            raise ValueError(f"labels has {len(labels)} entries but depth has {len(depth)} entries")
        return labels


class BoreholeClassificationJob(BaseModel):
    """The payload streamed from Node for the LITHOLOGY method.

    `predict` carries FEATURES ONLY (no labels) — that's the real target,
    the unlabeled interval to classify. `predictTrueLabels`, if present, is
    for DEMO/TEST SCORING ONLY: the harness uses it to independently score
    the classifier's predictions after the fact, but it is never forwarded
    into the sandbox (a real deployment has no ground truth for `predict` at
    all, and simply omits this field)."""

    jobId: str
    sensorId: str
    dataType: Literal["LITHOLOGY"] = "LITHOLOGY"
    train: LabeledWellLogSeries
    predict: WellLogSeries
    classes: list[str]
    siteNote: str | None = None
    predictTrueLabels: list[str] | None = None

    @field_validator("predictTrueLabels")
    @classmethod
    def _predict_true_labels_match_predict(
        cls, v: list[str] | None, info: ValidationInfo
    ) -> list[str] | None:
        predict = info.data.get("predict")
        if v is not None and predict is not None and len(v) != len(predict.depth):
            raise ValueError(
                f"predictTrueLabels has {len(v)} entries but predict.depth has "
                f"{len(predict.depth)} entries"
            )
        return v

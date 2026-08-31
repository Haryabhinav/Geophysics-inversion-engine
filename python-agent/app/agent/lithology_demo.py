"""Synthetic demo/test well-log scenario for the LITHOLOGY method — mirrors
the role buildEmpymodTdem/buildBiexpTdem play for TDEM on the Node side.

4 lithology classes, 4 log curves (the canonical petrophysics quad-combo),
piecewise-constant per bed (no noise) — deliberately noise-free so the demo
shows the pipeline mechanism working end-to-end rather than stress-testing
classifier robustness. Sparse "core-calibrated" labels every 5m form the
training set; the rest is the unlabeled interval to classify, mirroring how
real wells are actually cored (a small labeled sample, a much larger
unlabeled interval).
"""

from __future__ import annotations

LITHOLOGY_CLASSES = ["Sandstone", "Shale", "Limestone", "Coal"]

_CURVE_UNITS = {
    "gamma_ray": "API",
    "resistivity": "Ohm-m",
    "bulk_density": "g/cc",
    "sonic_dt": "us/ft",
}

_CURVE_VALUE_BY_CLASS = {
    "gamma_ray": {"Sandstone": 40.0, "Shale": 115.0, "Limestone": 17.0, "Coal": 25.0},
    "resistivity": {"Sandstone": 100.0, "Shale": 10.0, "Limestone": 500.0, "Coal": 500.0},
    "bulk_density": {"Sandstone": 2.32, "Shale": 2.55, "Limestone": 2.60, "Coal": 1.50},
    "sonic_dt": {"Sandstone": 65.0, "Shale": 95.0, "Limestone": 51.0, "Coal": 115.0},
}

# (depth_from, depth_to, lithology) — a bedded sequence, 0-200m.
_BEDS = [
    (0.0, 40.0, "Sandstone"),
    (40.0, 90.0, "Shale"),
    (90.0, 130.0, "Limestone"),
    (130.0, 140.0, "Coal"),
    (140.0, 180.0, "Shale"),
    (180.0, 200.0, "Sandstone"),
]


def _lithology_at(depth: float) -> str:
    for lo, hi, lith in _BEDS:
        if lo <= depth < hi:
            return lith
    return _BEDS[-1][2]


def build_demo_well_log(spacing: float = 0.5, train_stride: int = 10) -> dict:
    """Returns depths/curves/true_labels for the full 0-200m column, plus
    the train/predict index split. `train_stride=10` at `spacing=0.5` means
    one labeled sample every 5m."""
    n = int(200.0 / spacing) + 1
    depths = [round(i * spacing, 4) for i in range(n)]
    true_labels = [_lithology_at(d) for d in depths]
    curves = {
        name: [by_class[_lithology_at(d)] for d in depths] for name, by_class in _CURVE_VALUE_BY_CLASS.items()
    }
    train_idx = list(range(0, n, train_stride))
    train_idx_set = set(train_idx)
    predict_idx = [i for i in range(n) if i not in train_idx_set]
    return {
        "depths": depths,
        "curves": curves,
        "true_labels": true_labels,
        "train_idx": train_idx,
        "predict_idx": predict_idx,
        "units": _CURVE_UNITS,
        "classes": LITHOLOGY_CLASSES,
    }

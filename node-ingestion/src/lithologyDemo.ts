/**
 * Synthetic demo well-log scenario for the LITHOLOGY method — mirrors
 * python-agent/app/agent/lithology_demo.py exactly (same classes, curve
 * values per class, bed sequence, spacing, and train stride) so a click on
 * the dashboard produces the same scenario the Python-side offline test
 * already verified achieves ~100% accuracy.
 */
import type {
  BoreholeClassificationJobPayload,
  LabeledWellLogSeriesPayload,
  LogCurvePayload,
  WellLogSeriesPayload,
} from './types.js';

const CLASSES = ['Sandstone', 'Shale', 'Limestone', 'Coal'];

const CURVE_UNITS: Record<string, string> = {
  gamma_ray: 'API',
  resistivity: 'Ohm-m',
  bulk_density: 'g/cc',
  sonic_dt: 'us/ft',
};

const CURVE_VALUE_BY_CLASS: Record<string, Record<string, number>> = {
  gamma_ray: { Sandstone: 40.0, Shale: 115.0, Limestone: 17.0, Coal: 25.0 },
  resistivity: { Sandstone: 100.0, Shale: 10.0, Limestone: 500.0, Coal: 500.0 },
  bulk_density: { Sandstone: 2.32, Shale: 2.55, Limestone: 2.6, Coal: 1.5 },
  sonic_dt: { Sandstone: 65.0, Shale: 95.0, Limestone: 51.0, Coal: 115.0 },
};

// [depth_from, depth_to, lithology) — a bedded sequence, 0-200m.
const BEDS: Array<[number, number, string]> = [
  [0, 40, 'Sandstone'],
  [40, 90, 'Shale'],
  [90, 130, 'Limestone'],
  [130, 140, 'Coal'],
  [140, 180, 'Shale'],
  [180, 200, 'Sandstone'],
];

function lithologyAt(depth: number): string {
  for (const [lo, hi, lith] of BEDS) {
    if (depth >= lo && depth < hi) return lith;
  }
  return BEDS[BEDS.length - 1]![2];
}

export function buildLithologyDemoJob(
  jobId: string,
  sensorId = 'dashboard-sim',
): BoreholeClassificationJobPayload {
  const spacing = 0.5;
  const trainStride = 10; // one labeled sample every 5m
  const n = Math.floor(200 / spacing) + 1;

  const depths: number[] = [];
  const trueLabels: string[] = [];
  for (let i = 0; i < n; i++) {
    const d = Math.round(i * spacing * 10000) / 10000;
    depths.push(d);
    trueLabels.push(lithologyAt(d));
  }

  const curveNames = Object.keys(CURVE_VALUE_BY_CLASS);
  const curveValues: Record<string, number[]> = {};
  for (const name of curveNames) {
    curveValues[name] = depths.map((d) => CURVE_VALUE_BY_CLASS[name]![lithologyAt(d)]!);
  }

  const trainIdx: number[] = [];
  for (let i = 0; i < n; i += trainStride) trainIdx.push(i);
  const trainIdxSet = new Set(trainIdx);
  const predictIdx: number[] = [];
  for (let i = 0; i < n; i++) {
    if (!trainIdxSet.has(i)) predictIdx.push(i);
  }

  const buildCurves = (indices: number[]): LogCurvePayload[] =>
    curveNames.map((name) => ({
      name,
      unit: CURVE_UNITS[name]!,
      values: indices.map((i) => curveValues[name]![i]!),
    }));

  const train: LabeledWellLogSeriesPayload = {
    depth: trainIdx.map((i) => depths[i]!),
    curves: buildCurves(trainIdx),
    labels: trainIdx.map((i) => trueLabels[i]!),
  };
  const predict: WellLogSeriesPayload = {
    depth: predictIdx.map((i) => depths[i]!),
    curves: buildCurves(predictIdx),
  };

  return {
    jobId,
    sensorId,
    dataType: 'LITHOLOGY',
    train,
    predict,
    classes: CLASSES,
    predictTrueLabels: predictIdx.map((i) => trueLabels[i]!),
  };
}

import type { SensorPayload, CleanSeries } from './types.js';

export interface SanitizeResult {
  clean: CleanSeries;
  totalCount: number;
  droppedCount: number;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * Drops bad samples from a raw sensor payload.
 *
 * A sample pair (time[i], amplitude[i]) is kept only if BOTH values are
 * finite numbers. This removes NaN, ±Infinity, null, and any value lost to a
 * length mismatch between the two arrays.
 */
export function sanitize(payload: SensorPayload): SanitizeResult {
  const { timeSteps, amplitudes } = payload;

  const time: number[] = [];
  const amplitude: number[] = [];

  const pairLength = Math.min(timeSteps.length, amplitudes.length);
  for (let i = 0; i < pairLength; i++) {
    const t = timeSteps[i];
    const a = amplitudes[i];
    if (isFiniteNumber(t) && isFiniteNumber(a)) {
      time.push(t);
      amplitude.push(a);
    }
  }

  // Count everything the caller sent so the dropped tally reflects both
  // non-finite values and any trailing unpaired samples.
  const totalCount = Math.max(timeSteps.length, amplitudes.length);

  return {
    clean: { time, amplitude },
    totalCount,
    droppedCount: totalCount - time.length,
  };
}

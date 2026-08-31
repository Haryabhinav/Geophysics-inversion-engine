import { describe, it, expect } from 'vitest';

import { sanitize } from '../src/sanitize';
import type { SensorPayload, DataType } from '../src/types';

function payload(
  timeSteps: Array<number | null>,
  amplitudes: Array<number | null>,
  dataType: DataType = 'TDEM',
): SensorPayload {
  return { sensorId: 'sim', dataType, timeSteps, amplitudes };
}

describe('sanitize', () => {
  it('keeps all valid pairs untouched', () => {
    const r = sanitize(payload([1, 2, 3], [0.1, 0.2, 0.3]));
    expect(r.clean.time).toEqual([1, 2, 3]);
    expect(r.clean.amplitude).toEqual([0.1, 0.2, 0.3]);
    expect(r.totalCount).toBe(3);
    expect(r.droppedCount).toBe(0);
  });

  it('drops null, NaN, and Infinity samples', () => {
    const r = sanitize(payload([1, null, 3, 4], [0.1, 0.2, NaN, Infinity]));
    expect(r.clean.time).toEqual([1]);
    expect(r.clean.amplitude).toEqual([0.1]);
    expect(r.totalCount).toBe(4);
    expect(r.droppedCount).toBe(3);
  });

  it('drops unpaired trailing samples on length mismatch', () => {
    const r = sanitize(payload([1, 2, 3], [0.1, 0.2]));
    expect(r.clean.time).toEqual([1, 2]);
    expect(r.clean.amplitude).toEqual([0.1, 0.2]);
    expect(r.totalCount).toBe(3);
    expect(r.droppedCount).toBe(1);
  });

  it('returns an empty series when every sample is bad', () => {
    const r = sanitize(payload([null, NaN], [null, NaN]));
    expect(r.clean.time).toEqual([]);
    expect(r.clean.amplitude).toEqual([]);
    expect(r.totalCount).toBe(2);
    expect(r.droppedCount).toBe(2);
  });
});

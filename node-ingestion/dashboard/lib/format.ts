export function formatNumber(value: unknown, sigFigs = 4): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return String(value);
  if (value === 0) return '0';
  const abs = Math.abs(value);
  if (abs >= 1e5 || abs < 1e-3) return value.toExponential(sigFigs - 1);
  return Number(value.toPrecision(sigFigs)).toString();
}

export function formatRelativeTime(epochMs: number): string {
  const diffSec = Math.round((Date.now() - epochMs) / 1000);
  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay}d ago`;
}

/** Flattens a possibly-nested model dict (e.g. {params: {res1, res2}}) into
 * flat key/value pairs for display, skipping non-scalar/array noise fields. */
export function flattenModelParams(model: Record<string, unknown>): Array<[string, unknown]> {
  const source = (model.params as Record<string, unknown> | undefined) ?? model;
  return Object.entries(source).filter(([key, value]) => {
    if (key === 'predicted_labels') return false; // shown separately (potentially huge array)
    return typeof value !== 'object' || value === null;
  });
}

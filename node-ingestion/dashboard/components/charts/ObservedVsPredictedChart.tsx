import {
  CartesianGrid,
  Legend,
  Line,
  ComposedChart,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { methodMeta } from '@constants/methods';

interface Point {
  x: number;
  observed?: number;
  predicted?: number;
}

export function ObservedVsPredictedChart({
  dataType,
  time,
  observed,
  predicted,
}: {
  dataType: string;
  time: number[];
  observed: number[];
  predicted: number[] | null;
}) {
  const meta = methodMeta(dataType);

  if (!time.length || !observed.length) {
    return (
      <div className="flex h-64 items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
        No curve data for this run.
      </div>
    );
  }

  const points: Point[] = time.map((x, i) => ({
    x,
    observed: observed[i],
    predicted: predicted?.[i],
  }));

  return (
    <div style={{ background: 'var(--viz-surface)' }}>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 4 }}>
          <CartesianGrid stroke="var(--viz-grid)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="x"
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            stroke="var(--viz-grid)"
            label={{ value: meta.xLabel, position: 'insideBottom', offset: -4, fill: 'var(--text-muted)', fontSize: 11 }}
          />
          <YAxis
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            stroke="var(--viz-grid)"
            width={70}
            label={{ value: meta.dLabel, angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--card-bg)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Scatter name="Observed" dataKey="observed" fill="var(--viz-series1)" />
          {predicted && (
            <Line
              name="Predicted"
              type="monotone"
              dataKey="predicted"
              stroke="var(--viz-series2)"
              strokeWidth={2}
              dot={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

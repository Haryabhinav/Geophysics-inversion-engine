import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export function ConvergenceChart({ l2History }: { l2History: number[] }) {
  if (!l2History.length) {
    return (
      <div className="flex h-52 items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
        No convergence history for this run.
      </div>
    );
  }

  const points = l2History.map((l2, i) => ({ iteration: i + 1, l2 }));
  const allPositive = l2History.every((v) => v > 0);

  return (
    <div style={{ background: 'var(--viz-surface)' }}>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 4 }}>
          <CartesianGrid stroke="var(--viz-grid)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="iteration"
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            stroke="var(--viz-grid)"
            label={{ value: 'iteration', position: 'insideBottom', offset: -4, fill: 'var(--text-muted)', fontSize: 11 }}
          />
          <YAxis
            scale={allPositive ? 'log' : 'linear'}
            domain={allPositive ? ['auto', 'auto'] : undefined}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            stroke="var(--viz-grid)"
            width={64}
            label={{ value: 'relative L2', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 11 }}
          />
          <Tooltip
            formatter={(value) => (typeof value === 'number' ? value.toPrecision(4) : String(value))}
            contentStyle={{
              background: 'var(--card-bg)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Line type="monotone" dataKey="l2" stroke="var(--viz-series1)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

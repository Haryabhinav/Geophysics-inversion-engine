import { Card, Progress, Statistic } from 'antd';

import { FAMILY_COLOR } from '@constants/methods';

export function LithologySummary({ finalModel }: { finalModel: Record<string, unknown> }) {
  const labels = (finalModel.predicted_labels as string[] | undefined) ?? [];
  const accuracy = finalModel.accuracy as number | undefined;
  const f1 = finalModel.f1_macro as number | undefined;
  const algorithm = finalModel.algorithm as string | undefined;

  if (!labels.length) return null;

  const counts = labels.reduce<Record<string, number>>((acc, label) => {
    acc[label] = (acc[label] ?? 0) + 1;
    return acc;
  }, {});
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const total = labels.length;
  const color = FAMILY_COLOR.Classification;

  return (
    <Card size="small" title="Predicted lithology" className="shadow-card" style={{ borderRadius: 12 }}>
      {(accuracy !== undefined || f1 !== undefined) && (
        <div className="mb-4 flex gap-8">
          {accuracy !== undefined && (
            <Statistic title="Accuracy" value={accuracy * 100} precision={1} suffix="%" />
          )}
          {f1 !== undefined && <Statistic title="F1 (macro)" value={f1 * 100} precision={1} suffix="%" />}
          {algorithm && <Statistic title="Model" value={algorithm} valueStyle={{ fontSize: 14 }} />}
        </div>
      )}
      <div className="flex flex-col gap-2.5">
        {entries.map(([label, count]) => (
          <div key={label}>
            <div className="mb-1 flex justify-between text-xs">
              <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
              <span className="tabular-nums" style={{ color: 'var(--text-muted)' }}>
                {count} / {total}
              </span>
            </div>
            <Progress
              percent={(count / total) * 100}
              showInfo={false}
              strokeColor={color}
              trailColor="var(--page-bg)"
              size="small"
            />
          </div>
        ))}
      </div>
    </Card>
  );
}

import { Card, Descriptions } from 'antd';

import { formatNumber, flattenModelParams } from '@lib/format';
import { methodMeta } from '@constants/methods';

export function ModelResultCard({
  dataType,
  finalModel,
}: {
  dataType: string;
  finalModel: Record<string, unknown>;
}) {
  const meta = methodMeta(dataType);
  const paramMetaByName = Object.fromEntries(meta.params.map((p) => [p.name, p]));
  const entries = flattenModelParams(finalModel);

  if (!entries.length) {
    return null;
  }

  return (
    <Card size="small" title="Recovered model" className="shadow-card" style={{ borderRadius: 12 }}>
      <Descriptions column={1} size="small" colon={false}>
        {entries.map(([key, value]) => {
          const p = paramMetaByName[key];
          return (
            <Descriptions.Item
              key={key}
              label={
                <span style={{ color: 'var(--text-secondary)' }}>
                  {p?.description ?? key}
                  {p?.unit && p.unit !== '—' ? ` (${p.unit})` : ''}
                </span>
              }
            >
              <span className="tabular-nums font-medium">{formatNumber(value)}</span>
            </Descriptions.Item>
          );
        })}
      </Descriptions>
    </Card>
  );
}

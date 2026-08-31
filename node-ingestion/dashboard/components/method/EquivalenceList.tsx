import { Card, Tag } from 'antd';

import { formatNumber, flattenModelParams } from '@lib/format';
import type { EquivalentModel } from '@types_/api';

export function EquivalenceList({ models }: { models: EquivalentModel[] }) {
  if (models.length < 2) return null;

  return (
    <Card
      size="small"
      title="Equivalent models"
      className="shadow-card"
      style={{ borderRadius: 12 }}
      extra={
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          non-uniqueness
        </span>
      }
    >
      <p className="mb-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
        {models.length} distinct models fit the data almost equally well — this is why the
        Interpretation Agent exists: the misfit alone can&apos;t disambiguate them.
      </p>
      <div className="flex flex-col gap-2">
        {models.map((m, i) => (
          <div
            key={i}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm"
            style={{ background: 'var(--page-bg)' }}
          >
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              {flattenModelParams(m.model).map(([key, value]) => (
                <span key={key}>
                  <span style={{ color: 'var(--text-muted)' }}>{key}:</span>{' '}
                  <span className="tabular-nums font-medium">{formatNumber(value)}</span>
                </span>
              ))}
            </div>
            <Tag color={i === 0 ? 'blue' : 'default'}>L2 {formatNumber(m.l2_norm_error)}</Tag>
          </div>
        ))}
      </div>
    </Card>
  );
}

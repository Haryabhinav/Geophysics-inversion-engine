import { Card, Skeleton } from 'antd';
import type { ReactNode } from 'react';

export function StatTile({
  label,
  value,
  icon,
  loading,
  accent,
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  loading?: boolean;
  accent?: string;
}) {
  return (
    <Card size="small" className="shadow-card" style={{ borderRadius: 12 }}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
            {label}
          </div>
          {loading ? (
            <Skeleton.Input active size="small" style={{ width: 72, marginTop: 8 }} />
          ) : (
            <div
              className="tabular-nums mt-1 text-[26px] font-bold leading-tight"
              style={{ color: accent ?? 'var(--text-primary)' }}
            >
              {value}
            </div>
          )}
        </div>
        {icon && (
          <div
            className="flex h-9 w-9 items-center justify-center rounded-full text-base"
            style={{ background: 'var(--page-bg)', color: accent ?? 'var(--text-secondary)' }}
          >
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}

import { Button, Empty } from 'antd';
import type { ReactNode } from 'react';

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description?: ReactNode;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-card border py-16" style={{ borderColor: 'var(--border-hairline)', background: 'var(--card-bg)' }}>
      <Empty description={<span style={{ color: 'var(--text-secondary)' }}>{title}</span>} />
      {description && (
        <div className="mt-1 max-w-sm text-center text-sm" style={{ color: 'var(--text-muted)' }}>
          {description}
        </div>
      )}
      {actionLabel && onAction && (
        <Button type="primary" className="mt-4" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

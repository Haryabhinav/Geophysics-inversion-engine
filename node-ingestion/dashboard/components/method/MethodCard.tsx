import { Card, Typography } from 'antd';

import { FamilyTag } from '@components/common/FamilyTag';
import { BRAND, tint } from '@lib/theme/tokens';
import type { MethodMeta } from '@constants/methods';

export function MethodCard({
  method,
  selected,
  onClick,
}: {
  method: MethodMeta;
  selected?: boolean;
  onClick?: () => void;
}) {
  return (
    <Card
      hoverable
      size="small"
      onClick={onClick}
      className="shadow-card transition-shadow"
      style={{
        borderRadius: 12,
        borderColor: selected ? BRAND : 'var(--border-hairline)',
        // Was a hard-coded rgba(107,74,252) purple — a hue that appears
        // nowhere else in the token set, so a selected card read as a
        // different accent colour than the brand border right beside it.
        boxShadow: selected ? `0 0 0 2px ${tint(BRAND, 35)}` : undefined,
      }}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <Typography.Text strong style={{ fontSize: 14 }}>
          {method.displayName}
        </Typography.Text>
        <FamilyTag family={method.family} />
      </div>
      <p className="mb-2 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        {method.description}
      </p>
      <p className="text-[11px] italic" style={{ color: 'var(--text-muted)' }}>
        {method.reference}
      </p>
    </Card>
  );
}

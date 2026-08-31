import { RobotOutlined } from '@ant-design/icons';
import { Card, Typography } from 'antd';

import { AnomalyBadge, ConfidenceBadge } from '@components/common/Badges';
import { BRAND } from '@lib/theme/tokens';
import type { InterpretationResult } from '@types_/api';

export function InterpretationCard({ interpretation }: { interpretation: InterpretationResult | null }) {
  if (!interpretation) return null;

  return (
    <Card
      size="small"
      className="shadow-card"
      style={{ borderRadius: 12, borderColor: 'var(--border-hairline)' }}
      title={
        <span className="flex items-center gap-2">
          <RobotOutlined style={{ color: BRAND }} />
          Interpretation
        </span>
      }
      extra={
        <div className="flex gap-2">
          <ConfidenceBadge confidence={interpretation.confidence} />
          <AnomalyBadge flagged={interpretation.flagged_anomaly} />
        </div>
      }
    >
      <Typography.Paragraph style={{ marginBottom: 8 }}>{interpretation.summary}</Typography.Paragraph>
      <Typography.Text style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
        {interpretation.reasoning}
      </Typography.Text>
    </Card>
  );
}

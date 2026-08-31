import { RobotOutlined } from '@ant-design/icons';
import { Card, Table, Tag, Typography } from 'antd';

import { ConfidenceBadge, CorroborationBadge, AnomalyBadge } from '@components/common/Badges';
import { BRAND, STATUS_COLOR, tint } from '@lib/theme/tokens';
import type { JointInterpretationResult } from '@types_/api';

export function JointReportCard({ report }: { report: JointInterpretationResult }) {
  return (
    <Card
      className="shadow-card"
      style={{ borderRadius: 12, borderColor: tint(BRAND, 20) }}
      title={
        <span className="flex items-center gap-2">
          <RobotOutlined style={{ color: BRAND }} />
          Joint Interpretation
        </span>
      }
      extra={
        <div className="flex flex-wrap gap-2">
          <CorroborationBadge corroboration={report.corroboration} />
          <ConfidenceBadge confidence={report.confidence} />
          <AnomalyBadge flagged={report.flagged_anomaly} />
        </div>
      }
    >
      <Typography.Paragraph style={{ fontSize: 15 }}>{report.summary}</Typography.Paragraph>
      <Typography.Text style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
        {report.reasoning}
      </Typography.Text>

      {report.conflicts.length > 0 && (
        <div className="mt-4 rounded-lg p-3" style={{
            background: tint(STATUS_COLOR.critical, 6),
            border: `1px solid ${tint(STATUS_COLOR.critical, 20)}`,
          }}>
          <div className="mb-1 text-xs font-semibold" style={{ color: STATUS_COLOR.critical }}>
            Unreconciled conflicts
          </div>
          <ul className="ml-4 list-disc text-xs" style={{ color: 'var(--text-secondary)' }}>
            {report.conflicts.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      <Table
        className="mt-4"
        size="small"
        pagination={false}
        rowKey="jobId"
        dataSource={report.methodContributions}
        columns={[
          { title: 'Method', dataIndex: 'dataType', render: (v) => <Tag>{v}</Tag> },
          { title: 'Contribution', dataIndex: 'contributesTo' },
          {
            title: 'Standing',
            dataIndex: 'corroboration',
            width: 130,
            render: (v) => <CorroborationBadge corroboration={v} />,
          },
        ]}
      />
    </Card>
  );
}

import { RobotOutlined } from '@ant-design/icons';
import { Card, List, Tag, Typography } from 'antd';

import { BRAND } from '@lib/theme/tokens';
import type { CleaningResult } from '@types_/api';

/** Shows what the AI Data Cleaning Agent (`app/agent/data_cleaner.py`) did
 * to a raw upload, so the user can sanity-check an LLM-authored data
 * transformation before it flows into an inversion — this is intentionally
 * NOT hidden behind a "trust me" toggle. */
export function CleaningReportCard({ result }: { result: CleaningResult }) {
  const keptCount = result.originalCount - result.droppedCount;

  return (
    <Card
      size="small"
      className="shadow-card"
      style={{ borderRadius: 12 }}
      title={
        <span className="flex items-center gap-2">
          <RobotOutlined style={{ color: BRAND }} />
          AI cleaning report
        </span>
      }
      extra={
        <Tag color={result.droppedCount > 0 ? 'gold' : 'default'}>
          {keptCount} kept{result.droppedCount ? `, ${result.droppedCount} removed` : ''} of{' '}
          {result.originalCount}
        </Tag>
      }
    >
      <Typography.Paragraph style={{ marginBottom: result.actions.length ? 8 : 0 }}>
        {result.summary}
      </Typography.Paragraph>
      {result.actions.length > 0 && (
        <List
          size="small"
          dataSource={result.actions}
          renderItem={(action) => (
            <List.Item style={{ padding: '4px 0', border: 'none' }}>
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                • {action}
              </span>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}

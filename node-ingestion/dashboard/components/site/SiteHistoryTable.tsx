import { Table, Tag } from 'antd';
import { useRouter } from 'next/router';

import { RunStatusBadge } from '@components/common/Badges';
import { formatNumber, formatRelativeTime } from '@lib/format';
import type { PersistedInversion } from '@types_/api';

export function SiteHistoryTable({ records, loading }: { records: PersistedInversion[]; loading?: boolean }) {
  const router = useRouter();

  return (
    <Table
      size="small"
      loading={loading}
      rowKey="jobId"
      dataSource={records}
      pagination={{ pageSize: 8, hideOnSinglePage: true }}
      onRow={(record) => ({
        style: { cursor: 'pointer' },
        onClick: () => router.push(`/runs?jobId=${encodeURIComponent(record.jobId)}`),
      })}
      columns={[
        { title: 'Method', dataIndex: 'dataType', render: (v) => <Tag>{v}</Tag> },
        { title: 'Status', dataIndex: 'status', render: (v) => <RunStatusBadge status={v} /> },
        {
          title: 'Relative L2',
          dataIndex: 'l2NormError',
          render: (v) => (v === null ? '—' : formatNumber(v)),
        },
        { title: 'Iterations', dataIndex: 'iterations' },
        {
          title: 'When',
          dataIndex: 'createdAt',
          render: (v) => formatRelativeTime(v),
        },
      ]}
    />
  );
}

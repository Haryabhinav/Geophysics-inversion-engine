import { useQuery } from '@tanstack/react-query';
import { Table, Tag } from 'antd';
import { useRouter } from 'next/router';
import { useMemo } from 'react';

import { RunStatusBadge } from '@components/common/Badges';
import { EmptyState } from '@components/common/EmptyState';
import { PageHeader } from '@components/common/PageHeader';
import { formatNumber, formatRelativeTime } from '@lib/format';
import { listResults } from '@services/runs';
import type { PersistedInversion } from '@types_/api';

export default function HistoryPage() {
  const router = useRouter();
  const { data: results, isLoading } = useQuery({
    queryKey: ['results'],
    queryFn: () => listResults(200),
  });

  const methodFilters = useMemo(
    () => [...new Set((results ?? []).map((r) => r.dataType))].map((v) => ({ text: v, value: v })),
    [results],
  );
  const statusFilters = useMemo(
    () => [...new Set((results ?? []).map((r) => r.status))].map((v) => ({ text: v, value: v })),
    [results],
  );
  const siteFilters = useMemo(
    () => [...new Set((results ?? []).map((r) => r.sensorId))].map((v) => ({ text: v, value: v })),
    [results],
  );

  return (
    <div>
      <PageHeader title="History" description="Every run this platform has processed, across all 13 methods." />

      {!isLoading && results?.length === 0 ? (
        <EmptyState
          title="No runs yet"
          description="Submit a job from the Run page — it'll show up here once it converges."
          actionLabel="Run a method"
          onAction={() => router.push('/run')}
        />
      ) : (
        <Table<PersistedInversion>
          size="small"
          loading={isLoading}
          rowKey="jobId"
          dataSource={results}
          onRow={(record) => ({
            style: { cursor: 'pointer' },
            onClick: () => router.push(`/runs?jobId=${encodeURIComponent(record.jobId)}`),
          })}
          pagination={{ pageSize: 15 }}
          columns={[
            {
              title: 'Method',
              dataIndex: 'dataType',
              filters: methodFilters,
              onFilter: (value, record) => record.dataType === value,
              render: (v) => <Tag>{v}</Tag>,
            },
            {
              title: 'Site',
              dataIndex: 'sensorId',
              filters: siteFilters,
              onFilter: (value, record) => record.sensorId === value,
            },
            {
              title: 'Status',
              dataIndex: 'status',
              filters: statusFilters,
              onFilter: (value, record) => record.status === value,
              render: (v) => <RunStatusBadge status={v} />,
            },
            {
              title: 'Relative L2',
              dataIndex: 'l2NormError',
              sorter: (a, b) => (a.l2NormError ?? 0) - (b.l2NormError ?? 0),
              render: (v) => (v === null ? '—' : formatNumber(v)),
            },
            { title: 'Iterations', dataIndex: 'iterations', sorter: (a, b) => a.iterations - b.iterations },
            {
              title: 'When',
              dataIndex: 'createdAt',
              defaultSortOrder: 'descend',
              sorter: (a, b) => a.createdAt - b.createdAt,
              render: (v) => formatRelativeTime(v),
            },
          ]}
        />
      )}
    </div>
  );
}

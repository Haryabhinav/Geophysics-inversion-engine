import { PlayCircleFilled } from '@ant-design/icons';
import { Button, Card, Table, Typography } from 'antd';

import { FamilyTag } from '@components/common/FamilyTag';
import type { MethodMeta } from '@constants/methods';

export function MethodDetailPanel({
  method,
  running,
  onRun,
}: {
  method: MethodMeta;
  running: boolean;
  onRun: () => void;
}) {
  return (
    <Card size="small" className="shadow-card" style={{ borderRadius: 12 }}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <Typography.Title level={4} style={{ margin: 0 }}>
              {method.displayName}
            </Typography.Title>
            <FamilyTag family={method.family} />
          </div>
          <Typography.Text style={{ color: 'var(--text-secondary)' }}>{method.description}</Typography.Text>
        </div>
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleFilled />}
          loading={running}
          onClick={onRun}
        >
          {running ? 'Running…' : 'Run simulated job'}
        </Button>
      </div>

      <div className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-xs" style={{ color: 'var(--text-muted)' }}>
        <span>
          <strong style={{ color: 'var(--text-secondary)' }}>x-axis:</strong> {method.xLabel}
        </span>
        <span>
          <strong style={{ color: 'var(--text-secondary)' }}>y-axis:</strong> {method.dLabel}
        </span>
        <span>
          <strong style={{ color: 'var(--text-secondary)' }}>reference:</strong> {method.reference}
        </span>
      </div>

      {method.params.length > 0 && (
        <Table
          className="mt-4"
          size="small"
          pagination={false}
          rowKey="name"
          dataSource={method.params}
          columns={[
            { title: 'Parameter', dataIndex: 'name', width: 120, render: (v) => <code>{v}</code> },
            { title: 'Unit', dataIndex: 'unit', width: 100 },
            { title: 'Meaning', dataIndex: 'description' },
          ]}
        />
      )}
    </Card>
  );
}

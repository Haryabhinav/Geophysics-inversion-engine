import { LoadingOutlined } from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import { App, Card, Col, Row, Spin } from 'antd';
import { useRouter } from 'next/router';
import { useState } from 'react';

import { EmptyState } from '@components/common/EmptyState';
import { PageHeader } from '@components/common/PageHeader';
import { MethodDetailPanel } from '@components/method/MethodDetailPanel';
import { MethodPickerGrid } from '@components/method/MethodPickerGrid';
import { RunResultView } from '@components/method/RunResultView';
import { methodMeta } from '@constants/methods';
import { BRAND } from '@lib/theme/tokens';
import { simulate } from '@services/runs';
import { useLiveStore } from '@store/useLiveStore';

export default function RunPage() {
  const router = useRouter();
  const { message } = App.useApp();
  const [runningJobId, setRunningJobId] = useState<string | null>(null);

  const selectedId = typeof router.query.method === 'string' ? router.query.method : null;
  const record = useLiveStore((s) => (runningJobId ? s.latestResultByJobId[runningJobId] : undefined));

  const runMutation = useMutation({
    mutationFn: (methodId: string) => simulate(methodId),
    onSuccess: (data) => {
      setRunningJobId(data.jobId);
      message.info(`Job ${data.jobId} submitted — ${data.accepted} samples accepted.`);
    },
    onError: (err: Error) => message.error(err.message),
  });

  const selectMethod = (id: string) => {
    // Reset right here (the only place `selectedId` actually changes while
    // this page stays mounted) rather than in an effect keyed on
    // `selectedId` — a direct-navigation entry to /run?method=... already
    // starts with a fresh `runningJobId` from useState's initial value, so
    // no separate sync-on-change effect is needed.
    setRunningJobId(null);
    void router.push({ pathname: '/run', query: { method: id } }, undefined, { shallow: true });
  };

  const meta = selectedId ? methodMeta(selectedId) : null;

  return (
    <div>
      <PageHeader
        title="Run a Method"
        description="Pick a geophysical method, run a synthetic job through the real pipeline, and watch it converge live."
      />

      <Row gutter={24}>
        <Col xs={24} lg={9}>
          <MethodPickerGrid selectedId={selectedId} onSelect={selectMethod} />
        </Col>

        <Col xs={24} lg={15}>
          {!meta ? (
            <EmptyState
              title="Choose a method to get started"
              description="Select any of the 13 methods on the left — each shows its physics reference, inverted parameters, and a live run panel."
            />
          ) : (
            <div className="flex flex-col gap-4">
              <MethodDetailPanel
                method={meta}
                running={runMutation.isPending}
                onRun={() => runMutation.mutate(meta.id)}
              />

              {runMutation.isPending || (runningJobId && !record) ? (
                <Card size="small" className="shadow-card" style={{ borderRadius: 12 }}>
                  <div className="flex flex-col items-center gap-3 py-10">
                    <Spin indicator={<LoadingOutlined style={{ fontSize: 28, color: BRAND }} spin />} />
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {runMutation.isPending
                        ? 'Submitting job…'
                        : 'Running — classical solver / LLM agent iterating in the sandbox…'}
                    </p>
                  </div>
                </Card>
              ) : (
                record && <RunResultView record={record} />
              )}
            </div>
          )}
        </Col>
      </Row>
    </div>
  );
}

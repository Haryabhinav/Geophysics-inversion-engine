import { ClusterOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { App, Button, Card, Col, List, Row, Skeleton, Tabs, Tag } from 'antd';
import { useRouter } from 'next/router';
import { useMemo, useState } from 'react';

import { EmptyState } from '@components/common/EmptyState';
import { PageHeader } from '@components/common/PageHeader';
import { JointReportCard } from '@components/site/JointReportCard';
import { SiteChatPanel } from '@components/site/SiteChatPanel';
import { SiteHistoryTable } from '@components/site/SiteHistoryTable';
import { SiteNoteEditor } from '@components/site/SiteNoteEditor';
import { SiteReportPanel } from '@components/site/SiteReportPanel';
import { listResults } from '@services/runs';
import { listSiteHistory, requestJointInterpretation } from '@services/sites';
import type { JointInterpretationResult } from '@types_/api';

export default function SitesPage() {
  const router = useRouter();
  const { message } = App.useApp();
  const [report, setReport] = useState<JointInterpretationResult | null>(null);

  const siteId = typeof router.query.siteId === 'string' ? router.query.siteId : null;

  const { data: allResults, isLoading: sitesLoading } = useQuery({
    queryKey: ['results'],
    queryFn: () => listResults(200),
  });

  const sites = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of allResults ?? []) counts.set(r.sensorId, (counts.get(r.sensorId) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [allResults]);

  const { data: siteHistory, isLoading: historyLoading } = useQuery({
    queryKey: ['siteHistory', siteId],
    queryFn: () => listSiteHistory(siteId as string),
    enabled: !!siteId,
  });

  const methodsAtSite = useMemo(
    () => [...new Set((siteHistory ?? []).filter((r) => r.status !== 'error').map((r) => r.dataType))],
    [siteHistory],
  );

  const jointMutation = useMutation({
    mutationFn: () => requestJointInterpretation(siteId as string),
    onSuccess: (data) => setReport(data),
    onError: (err: Error) => message.error(err.message),
  });

  const selectSite = (id: string) => {
    setReport(null);
    void router.push({ pathname: '/sites', query: { siteId: id } }, undefined, { shallow: true });
  };

  return (
    <div>
      <PageHeader
        title="Site Reports"
        description="Synthesize results from multiple methods run at the same site into one integrated interpretation."
      />

      <Row gutter={24}>
        <Col xs={24} lg={7}>
          <Card size="small" className="shadow-card" style={{ borderRadius: 12 }} styles={{ body: { padding: 0 } }}>
            {sitesLoading ? (
              <div className="p-4">
                <Skeleton active paragraph={{ rows: 4 }} />
              </div>
            ) : sites.length === 0 ? (
              <div className="p-4">
                <EmptyState title="No sites yet" description="Run a method first — its sensorId becomes a site." />
              </div>
            ) : (
              <List
                dataSource={sites}
                renderItem={([id, count]) => (
                  <List.Item
                    onClick={() => selectSite(id)}
                    className="cursor-pointer px-4 transition-colors hover:opacity-80"
                    style={{ background: id === siteId ? 'var(--page-bg)' : undefined }}
                  >
                    <div className="flex w-full items-center justify-between">
                      <span className="flex items-center gap-2 text-sm font-medium">
                        <ClusterOutlined style={{ color: 'var(--text-muted)' }} />
                        {id}
                      </span>
                      <Tag>{count} runs</Tag>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={17}>
          {!siteId ? (
            <EmptyState title="Choose a site" description="Select a site on the left to see its history and generate a joint interpretation." />
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">{siteId}</h2>
                <Button
                  type="primary"
                  icon={<ThunderboltOutlined />}
                  loading={jointMutation.isPending}
                  disabled={methodsAtSite.length === 0}
                  onClick={() => jointMutation.mutate()}
                >
                  Generate Joint Report
                </Button>
              </div>

              <Tabs
                items={[
                  {
                    key: 'overview',
                    label: 'Overview',
                    children: (
                      <div className="flex flex-col gap-4">
                        <SiteNoteEditor siteId={siteId} />
                        {report && <JointReportCard report={report} />}
                        <Card
                          size="small"
                          title={`History (${methodsAtSite.length} methods)`}
                          className="shadow-card"
                          style={{ borderRadius: 12 }}
                        >
                          <SiteHistoryTable records={siteHistory ?? []} loading={historyLoading} />
                        </Card>
                      </div>
                    ),
                  },
                  {
                    key: 'chat',
                    label: 'Chat',
                    children: <SiteChatPanel siteId={siteId} />,
                  },
                  {
                    key: 'report',
                    label: 'Report',
                    children: <SiteReportPanel siteId={siteId} />,
                  },
                ]}
              />
            </div>
          )}
        </Col>
      </Row>
    </div>
  );
}

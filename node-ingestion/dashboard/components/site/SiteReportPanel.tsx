import { FileTextOutlined, PrinterOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { App, Button, Card, Collapse, Empty, Skeleton, Typography } from 'antd';
import ReactMarkdown from 'react-markdown';

import { BRAND, tint } from '@lib/theme/tokens';
import { generateReport, getReports } from '@services/reports';

/**
 * Auto-generated site reports — an LLM-drafted markdown report (findings,
 * confidence, next steps) from a site's run history and joint
 * interpretation (see python-agent's app/agent/report_generator.py).
 * Rendered in-app; "Print" uses the browser's native print-to-PDF rather
 * than a server-generated file, per the project's no-new-server-dependency
 * approach to this feature.
 */
export function SiteReportPanel({ siteId }: { siteId: string }) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['reports', siteId],
    queryFn: () => getReports(siteId),
  });

  const generateMutation = useMutation({
    mutationFn: () => generateReport(siteId),
    onSuccess: () => {
      message.success('Report generated.');
      void queryClient.invalidateQueries({ queryKey: ['reports', siteId] });
    },
    onError: (err: Error) => message.error(err.message),
  });

  const reports = data?.reports ?? [];
  const latest = reports[0];

  return (
    <Card
      size="small"
      title="Site Report"
      className="shadow-card"
      style={{ borderRadius: 12 }}
      extra={
        <div className="flex gap-2 print:hidden">
          {latest && (
            <Button size="small" icon={<PrinterOutlined />} onClick={() => window.print()}>
              Print / Export PDF
            </Button>
          )}
          <Button
            size="small"
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={generateMutation.isPending}
            onClick={() => generateMutation.mutate()}
          >
            Generate Report
          </Button>
        </div>
      }
    >
      {isLoading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : !latest ? (
        <Empty description="No report generated yet for this site." image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className="flex flex-col gap-4">
          <div
            id="site-report-print-area"
            className="markdown-body rounded-lg p-4"
            style={{ border: `1px solid ${tint(BRAND, 20)}`, background: 'var(--card-bg)' }}
          >
            <ReactMarkdown>{latest.markdown}</ReactMarkdown>
          </div>
          <Typography.Text style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            Generated {new Date(latest.createdAt).toLocaleString()}
          </Typography.Text>

          {reports.length > 1 && (
            <Collapse
              size="small"
              items={[
                {
                  key: 'history',
                  label: (
                    <span className="flex items-center gap-2 text-sm">
                      <FileTextOutlined /> Report history ({reports.length - 1} earlier)
                    </span>
                  ),
                  children: (
                    <div className="flex flex-col gap-3">
                      {reports.slice(1).map((r) => (
                        <div key={r.createdAt} className="rounded-lg p-3" style={{ background: 'var(--page-bg)' }}>
                          <Typography.Text style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                            {new Date(r.createdAt).toLocaleString()}
                          </Typography.Text>
                          <p className="mt-1 text-sm">{r.summary}</p>
                        </div>
                      ))}
                    </div>
                  ),
                },
              ]}
            />
          )}
        </div>
      )}
    </Card>
  );
}

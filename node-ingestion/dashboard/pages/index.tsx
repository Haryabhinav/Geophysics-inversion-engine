import {
  CheckCircleOutlined,
  ClusterOutlined,
  DatabaseOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Card, Col, Row } from 'antd';
import Link from 'next/link';
import { useRouter } from 'next/router';

import { RunStatusBadge } from '@components/common/Badges';
import { EmptyState } from '@components/common/EmptyState';
import { PageHeader } from '@components/common/PageHeader';
import { StatTile } from '@components/common/StatTile';
import { MethodCard } from '@components/method/MethodCard';
import { METHOD_CATALOG } from '@constants/methods';
import { formatRelativeTime } from '@lib/format';
import { BRAND, STATUS_COLOR } from '@lib/theme/tokens';
import { listResults } from '@services/runs';
import { useLiveStore } from '@store/useLiveStore';

const FEATURED_METHOD_IDS = ['TDEM', 'GRAVITY_SPHERE', 'LITHOLOGY'];

export default function OverviewPage() {
  const router = useRouter();
  const activity = useLiveStore((s) => s.activity);

  const { data: results, isLoading } = useQuery({
    queryKey: ['results'],
    queryFn: () => listResults(200),
  });

  const totalRuns = results?.length ?? 0;
  const converged = results?.filter((r) => r.status === 'converged').length ?? 0;
  const convergedRate = totalRuns ? Math.round((converged / totalRuns) * 100) : 0;
  const sites = new Set(results?.map((r) => r.sensorId)).size;

  const feed = activity.length
    ? activity.slice(0, 12)
    : (results ?? []).slice(0, 12).map((r) => ({
        kind: 'result' as const,
        jobId: r.jobId,
        sensorId: r.sensorId,
        dataType: r.dataType,
        status: r.status,
        at: r.createdAt,
      }));

  return (
    <div>
      <PageHeader
        title="Overview"
        description="A multi-physics geophysical inversion platform — 13 methods, one agentic pipeline."
        actions={
          <Link href="/run">
            <button
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
              style={{ background: BRAND }}
            >
              <PlayCircleOutlined /> Run a method
            </button>
          </Link>
        }
      />

      <Row gutter={16} className="mb-6">
        <Col xs={12} md={6}>
          <StatTile label="Methods available" value={METHOD_CATALOG.length} icon={<DatabaseOutlined />} />
        </Col>
        <Col xs={12} md={6}>
          <StatTile label="Total runs" value={totalRuns} loading={isLoading} icon={<PlayCircleOutlined />} />
        </Col>
        <Col xs={12} md={6}>
          <StatTile
            label="Converged rate"
            value={`${convergedRate}%`}
            loading={isLoading}
            icon={<CheckCircleOutlined />}
            accent={convergedRate >= 50 ? STATUS_COLOR.good : undefined}
          />
        </Col>
        <Col xs={12} md={6}>
          <StatTile label="Sites tracked" value={sites} loading={isLoading} icon={<ClusterOutlined />} />
        </Col>
      </Row>

      <Row gutter={24}>
        <Col xs={24} lg={14}>
          <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Quick launch
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {FEATURED_METHOD_IDS.map((id) => {
              const method = METHOD_CATALOG.find((m) => m.id === id);
              if (!method) return null;
              return (
                <MethodCard
                  key={id}
                  method={method}
                  onClick={() => router.push({ pathname: '/run', query: { method: id } })}
                />
              );
            })}
          </div>
          <div className="mt-3 text-right">
            <Link href="/run" className="text-sm" style={{ color: BRAND }}>
              Browse all {METHOD_CATALOG.length} methods →
            </Link>
          </div>
        </Col>

        <Col xs={24} lg={10}>
          <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Recent activity
          </h3>
          <Card size="small" className="shadow-card" style={{ borderRadius: 12 }} styles={{ body: { padding: 0 } }}>
            {feed.length === 0 ? (
              <div className="p-6">
                <EmptyState title="No runs yet" description="Submit a job from the Run page to see activity here." />
              </div>
            ) : (
              <div className="divide-y" style={{ borderColor: 'var(--border-hairline)' }}>
                {feed.map((item, i) => (
                  <Link
                    key={`${item.jobId}-${i}`}
                    href={`/runs?jobId=${encodeURIComponent(item.jobId)}`}
                    className="flex items-center justify-between gap-2 px-4 py-3 transition-colors hover:opacity-80"
                  >
                    <div>
                      <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                        {item.dataType}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {item.sensorId} · {formatRelativeTime(item.at)}
                      </div>
                    </div>
                    {item.kind === 'pending' || !item.status ? (
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        running…
                      </span>
                    ) : (
                      <RunStatusBadge status={item.status} />
                    )}
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

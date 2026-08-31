import { useQuery } from '@tanstack/react-query';
import { Skeleton, Tag } from 'antd';
import { useRouter } from 'next/router';

import { EmptyState } from '@components/common/EmptyState';
import { PageHeader } from '@components/common/PageHeader';
import { RunResultView } from '@components/method/RunResultView';
import { methodMeta } from '@constants/methods';
import { getResult } from '@services/runs';

/**
 * The single-run detail page, at `/runs` and deliberately NOT `/results`.
 *
 * The dashboard is served same-origin by the very Fastify server it calls
 * (see DESIGN.md 14.4), so page routes and API routes share one URL space —
 * and Fastify's `GET /results` + `GET /results/:jobId` win over the static
 * file at `public/results/index.html`. Named `/results`, this page was
 * unreachable on a hard load: opening or refreshing a run link returned the
 * API's raw JSON instead of the UI. `/results` is the documented public API
 * contract, so the page is what moves.
 *
 * Adding a page here means checking its name against server.ts's routes.
 */
export default function ResultDetailPage() {
  const router = useRouter();
  const jobId = typeof router.query.jobId === 'string' ? router.query.jobId : null;

  const { data: record, isLoading, isError } = useQuery({
    queryKey: ['result', jobId],
    queryFn: () => getResult(jobId as string),
    enabled: !!jobId,
  });

  if (!jobId) {
    return <EmptyState title="No job selected" description="Pick a run from History or the Overview activity feed." />;
  }

  return (
    <div>
      <PageHeader
        title={record ? methodMeta(record.dataType).displayName : 'Run detail'}
        description={
          <span className="flex items-center gap-2">
            <code className="text-xs">{jobId}</code>
            {record && <Tag>{record.sensorId}</Tag>}
          </span>
        }
      />

      {isLoading && <Skeleton active paragraph={{ rows: 6 }} />}
      {isError && <EmptyState title="Run not found" description="This job may not have persisted (no database configured), or the id is wrong." />}
      {record && <RunResultView record={record} />}
    </div>
  );
}

import { Card, Col, Row, Statistic } from 'antd';

import { RunStatusBadge } from '@components/common/Badges';
import { ConvergenceChart } from '@components/charts/ConvergenceChart';
import { ObservedVsPredictedChart } from '@components/charts/ObservedVsPredictedChart';
import { EquivalenceList } from '@components/method/EquivalenceList';
import { InterpretationCard } from '@components/method/InterpretationCard';
import { LithologySummary } from '@components/method/LithologySummary';
import { ModelResultCard } from '@components/method/ModelResultCard';
import { formatNumber, formatRelativeTime } from '@lib/format';
import { methodMeta } from '@constants/methods';
import type { PersistedInversion } from '@types_/api';

export function RunResultView({ record }: { record: PersistedInversion }) {
  const meta = methodMeta(record.dataType);

  return (
    <div className="flex flex-col gap-4">
      <Card size="small" className="shadow-card" style={{ borderRadius: 12 }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <RunStatusBadge status={record.status} />
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {formatRelativeTime(record.createdAt)}
            </span>
          </div>
          <Row gutter={32}>
            {record.l2NormError !== null && (
              <Col>
                <Statistic
                  title="Relative L2"
                  value={formatNumber(record.l2NormError)}
                  valueStyle={{ fontSize: 16 }}
                />
              </Col>
            )}
            <Col>
              <Statistic title="Iterations" value={record.iterations} valueStyle={{ fontSize: 16 }} />
            </Col>
            <Col>
              <Statistic
                title="Samples"
                value={record.samplesUsed}
                suffix={record.droppedCount ? `(${record.droppedCount} dropped)` : undefined}
                valueStyle={{ fontSize: 16 }}
              />
            </Col>
          </Row>
        </div>
        {record.message && (
          <p className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>
            {record.message}
          </p>
        )}
      </Card>

      {meta.isClassification ? (
        <LithologySummary finalModel={record.finalModel} />
      ) : (
        <>
          <Card
            size="small"
            title="Observed vs. predicted"
            className="shadow-card"
            style={{ borderRadius: 12 }}
          >
            <ObservedVsPredictedChart
              dataType={record.dataType}
              time={record.observed?.time ?? []}
              observed={record.observed?.amplitude ?? []}
              predicted={record.predicted}
            />
          </Card>
          <Card size="small" title="Convergence" className="shadow-card" style={{ borderRadius: 12 }}>
            <ConvergenceChart l2History={record.l2History} />
          </Card>
        </>
      )}

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <ModelResultCard dataType={record.dataType} finalModel={record.finalModel} />
        </Col>
        <Col xs={24} md={12}>
          <InterpretationCard interpretation={record.interpretation} />
        </Col>
      </Row>

      <EquivalenceList models={record.equivalentModels} />
    </div>
  );
}

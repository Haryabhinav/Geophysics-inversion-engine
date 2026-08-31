import {
  CheckCircleFilled,
  CloseCircleFilled,
  ExclamationCircleFilled,
  MinusCircleFilled,
  QuestionCircleFilled,
} from '@ant-design/icons';
import { Tag } from 'antd';

import { STATUS_COLOR, tint } from '@lib/theme/tokens';
import type { Confidence, Corroboration, InversionStatus } from '@types_/api';

function StatusTag({
  color,
  icon,
  label,
}: {
  color: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Tag
      icon={icon}
      style={{
        color,
        background: tint(color, 8),
        borderColor: tint(color, 20),
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      {label}
    </Tag>
  );
}

const RUN_STATUS_META: Record<
  InversionStatus | 'rejected',
  { color: string; icon: React.ReactNode; label: string }
> = {
  converged: { color: STATUS_COLOR.good, icon: <CheckCircleFilled />, label: 'Converged' },
  max_iterations_reached: {
    color: STATUS_COLOR.warning,
    icon: <ExclamationCircleFilled />,
    label: 'Max Iterations',
  },
  error: { color: STATUS_COLOR.critical, icon: <CloseCircleFilled />, label: 'Error' },
  rejected: { color: STATUS_COLOR.critical, icon: <CloseCircleFilled />, label: 'Rejected' },
};

export function RunStatusBadge({ status }: { status: InversionStatus | 'rejected' | string }) {
  const meta = RUN_STATUS_META[status as InversionStatus] ?? {
    color: STATUS_COLOR.neutral,
    icon: <QuestionCircleFilled />,
    label: status,
  };
  return <StatusTag {...meta} />;
}

const CONFIDENCE_META: Record<Confidence, { color: string; icon: React.ReactNode; label: string }> = {
  high: { color: STATUS_COLOR.good, icon: <CheckCircleFilled />, label: 'High confidence' },
  medium: { color: STATUS_COLOR.warning, icon: <ExclamationCircleFilled />, label: 'Medium confidence' },
  low: { color: STATUS_COLOR.neutral, icon: <MinusCircleFilled />, label: 'Low confidence' },
};

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return <StatusTag {...CONFIDENCE_META[confidence]} />;
}

const CORROBORATION_META: Record<Corroboration, { color: string; icon: React.ReactNode; label: string }> = {
  consistent: { color: STATUS_COLOR.good, icon: <CheckCircleFilled />, label: 'Consistent' },
  conflicting: { color: STATUS_COLOR.critical, icon: <ExclamationCircleFilled />, label: 'Conflicting' },
  inconclusive: { color: STATUS_COLOR.neutral, icon: <QuestionCircleFilled />, label: 'Inconclusive' },
};

export function CorroborationBadge({ corroboration }: { corroboration: Corroboration }) {
  return <StatusTag {...CORROBORATION_META[corroboration]} />;
}

export function AnomalyBadge({ flagged }: { flagged: boolean }) {
  return flagged ? (
    <StatusTag color={STATUS_COLOR.critical} icon={<ExclamationCircleFilled />} label="Anomaly flagged" />
  ) : (
    <StatusTag color={STATUS_COLOR.neutral} icon={<MinusCircleFilled />} label="No anomaly" />
  );
}

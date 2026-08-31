import type { FastifyBaseLogger } from 'fastify';

import type { PersistedInversion } from './types.js';

/**
 * Notifies the user that an inversion finished. Always logs; additionally POSTs
 * the record to a webhook when ALERT_WEBHOOK_URL is configured (e.g. a Slack
 * incoming webhook or an internal notifications service).
 */
export interface Alerter {
  notify(record: PersistedInversion): Promise<void>;
}

export function createAlerter(
  webhookUrl: string | undefined,
  logger: FastifyBaseLogger,
): Alerter {
  return {
    async notify(record: PersistedInversion): Promise<void> {
      const summary =
        `Inversion ${record.jobId} (${record.dataType}) → ${record.status} ` +
        `[L2=${record.l2NormError ?? 'n/a'}, iters=${record.iterations}]`;

      if (record.status === 'converged') {
        logger.info({ jobId: record.jobId }, `✅ ${summary}`);
      } else {
        logger.warn({ jobId: record.jobId }, `⚠️ ${summary}`);
      }

      if (!webhookUrl) return;

      try {
        const res = await fetch(webhookUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: summary, record }),
        });
        if (!res.ok) {
          logger.warn({ status: res.status, jobId: record.jobId }, 'Alert webhook returned non-2xx');
        }
      } catch (err) {
        logger.error({ err: (err as Error).message, jobId: record.jobId }, 'Alert webhook failed');
      }
    },
  };
}

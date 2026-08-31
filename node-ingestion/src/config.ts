/**
 * Environment-driven configuration with sane defaults.
 */

export interface AppConfig {
  httpPort: number;
  agentWsUrl: string;
  reconnectBaseDelayMs: number;
  reconnectMaxDelayMs: number;
  maxBufferedJobs: number;
  /** Postgres connection string; persistence is disabled when unset. */
  databaseUrl: string | undefined;
  /** Optional HTTP endpoint POSTed with each finished inversion (user alert). */
  alertWebhookUrl: string | undefined;
}

function num(value: string | undefined, fallback: number): number {
  if (value === undefined) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export const config: AppConfig = {
  httpPort: num(process.env.HTTP_PORT, 3000),
  agentWsUrl: process.env.AGENT_WS_URL ?? 'ws://localhost:8000/ws/inversion-stream',
  reconnectBaseDelayMs: num(process.env.WS_RECONNECT_BASE_MS, 1000),
  reconnectMaxDelayMs: num(process.env.WS_RECONNECT_MAX_MS, 30000),
  maxBufferedJobs: num(process.env.MAX_BUFFERED_JOBS, 1000),
  databaseUrl: process.env.DATABASE_URL || undefined,
  alertWebhookUrl: process.env.ALERT_WEBHOOK_URL || undefined,
};

// From 'pg' (the runtime package), NOT '@types/pg' — an editor auto-import
// once resolved this to the .d.ts path, which typechecks fine (the class is
// declared there) but has no index.js, so the SERVER CRASHED ON STARTUP with
// ERR_MODULE_NOT_FOUND. `tsc --noEmit` cannot catch it; only running it can.
import { Pool } from 'pg';
import type { FastifyBaseLogger } from 'fastify';

import type { PersistedInversion } from './types.js';

/**
 * Persistence + read access for finished inversions. Two implementations:
 *   - PostgresRepository — real Postgres (when DATABASE_URL is set)
 *   - NullRepository     — no-op writes / empty reads (local dev without a DB;
 *                          the server serves the dashboard from its in-memory
 *                          store in that case)
 */
export interface Repository {
  readonly enabled: boolean;
  init(): Promise<void>;
  save(record: PersistedInversion): Promise<void>;
  list(limit: number): Promise<PersistedInversion[]>;
  get(jobId: string): Promise<PersistedInversion | null>;
  /** All results for one sensorId/site, most recent first — feeds the
   * multi-method Joint Interpretation capstone (POST /sites/:siteId/interpret). */
  listBySite(sensorId: string, limit: number): Promise<PersistedInversion[]>;
  close(): Promise<void>;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS inversion_results (
  id             SERIAL PRIMARY KEY,
  job_id         TEXT NOT NULL UNIQUE,
  sensor_id      TEXT NOT NULL,
  data_type      TEXT NOT NULL,
  status         TEXT NOT NULL,
  l2_norm_error  DOUBLE PRECISION,
  iterations     INTEGER NOT NULL,
  final_model    JSONB NOT NULL,
  message        TEXT,
  samples_used   INTEGER,
  dropped_count  INTEGER,
  observed       JSONB,
  predicted      JSONB,
  l2_history     JSONB,
  equivalent_models JSONB,
  interpretation JSONB,
  created_at     TIMESTAMPTZ NOT NULL,
  completed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
`;

// Additive migration for databases created before equivalent_models/interpretation
// existed — CREATE TABLE IF NOT EXISTS above won't add columns to an existing table.
const MIGRATE = `
ALTER TABLE inversion_results ADD COLUMN IF NOT EXISTS equivalent_models JSONB;
ALTER TABLE inversion_results ADD COLUMN IF NOT EXISTS interpretation JSONB;
CREATE INDEX IF NOT EXISTS idx_inversion_results_sensor_id_created_at
  ON inversion_results (sensor_id, created_at DESC);
`;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function rowToRecord(row: any): PersistedInversion {
  return {
    jobId: row.job_id,
    sensorId: row.sensor_id,
    dataType: row.data_type,
    status: row.status,
    l2NormError: row.l2_norm_error,
    iterations: row.iterations,
    finalModel: row.final_model ?? {},
    message: row.message ?? null,
    samplesUsed: row.samples_used ?? 0,
    droppedCount: row.dropped_count ?? 0,
    observed: row.observed ?? null,
    predicted: row.predicted ?? null,
    l2History: row.l2_history ?? [],
    equivalentModels: row.equivalent_models ?? [],
    interpretation: row.interpretation ?? null,
    createdAt: new Date(row.created_at).getTime(),
  };
}

class PostgresRepository implements Repository {
  readonly enabled = true;
  private readonly pool: Pool;

  constructor(connectionString: string, private readonly logger: FastifyBaseLogger) {
    this.pool = new Pool({ connectionString, max: 5 });
    this.pool.on('error', (err) => this.logger.error({ err: err.message }, 'Postgres pool error'));
  }

  async init(): Promise<void> {
    const attempts = 10;
    for (let i = 1; i <= attempts; i++) {
      try {
        await this.pool.query(SCHEMA);
        await this.pool.query(MIGRATE);
        this.logger.info('Postgres schema ready');
        return;
      } catch (err) {
        if (i === attempts) throw err;
        this.logger.warn({ attempt: i }, 'Postgres not ready — retrying');
        await delay(Math.min(1000 * i, 5000));
      }
    }
  }

  async save(record: PersistedInversion): Promise<void> {
    await this.pool.query(
      `INSERT INTO inversion_results
         (job_id, sensor_id, data_type, status, l2_norm_error, iterations,
          final_model, message, samples_used, dropped_count, observed, predicted, l2_history,
          equivalent_models, interpretation, created_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
       ON CONFLICT (job_id) DO NOTHING`,
      [
        record.jobId,
        record.sensorId,
        record.dataType,
        record.status,
        record.l2NormError,
        record.iterations,
        JSON.stringify(record.finalModel),
        record.message,
        record.samplesUsed,
        record.droppedCount,
        record.observed ? JSON.stringify(record.observed) : null,
        record.predicted ? JSON.stringify(record.predicted) : null,
        JSON.stringify(record.l2History),
        JSON.stringify(record.equivalentModels),
        record.interpretation ? JSON.stringify(record.interpretation) : null,
        new Date(record.createdAt).toISOString(),
      ],
    );
  }

  async list(limit: number): Promise<PersistedInversion[]> {
    const { rows } = await this.pool.query(
      'SELECT * FROM inversion_results ORDER BY created_at DESC LIMIT $1',
      [limit],
    );
    return rows.map(rowToRecord);
  }

  async get(jobId: string): Promise<PersistedInversion | null> {
    const { rows } = await this.pool.query('SELECT * FROM inversion_results WHERE job_id = $1', [jobId]);
    return rows[0] ? rowToRecord(rows[0]) : null;
  }

  async listBySite(sensorId: string, limit: number): Promise<PersistedInversion[]> {
    const { rows } = await this.pool.query(
      'SELECT * FROM inversion_results WHERE sensor_id = $1 ORDER BY created_at DESC LIMIT $2',
      [sensorId, limit],
    );
    return rows.map(rowToRecord);
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}

class NullRepository implements Repository {
  readonly enabled = false;

  constructor(private readonly logger: FastifyBaseLogger) {}

  async init(): Promise<void> {
    this.logger.warn('DATABASE_URL not set — persisting to memory only (dashboard still works)');
  }

  async save(): Promise<void> {
    /* no-op — the server keeps an in-memory store for the dashboard */
  }

  async list(): Promise<PersistedInversion[]> {
    return [];
  }

  async get(): Promise<PersistedInversion | null> {
    return null;
  }

  async listBySite(): Promise<PersistedInversion[]> {
    return [];
  }

  async close(): Promise<void> {
    /* no-op */
  }
}

export function createRepository(
  connectionString: string | undefined,
  logger: FastifyBaseLogger,
): Repository {
  return connectionString
    ? new PostgresRepository(connectionString, logger)
    : new NullRepository(logger);
}

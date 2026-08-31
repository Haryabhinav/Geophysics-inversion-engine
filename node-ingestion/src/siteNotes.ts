// From 'pg', the runtime package — never '@types/pg' (see db.ts).
import { Pool } from 'pg';
import type { FastifyBaseLogger } from 'fastify';

/**
 * Free-text site context (driller's log, geological note) keyed by sensorId,
 * forwarded to the Python agent's Interpretation Agent alongside each job for
 * that site. Same enabled/no-op-fallback shape as db.ts's Repository, kept as
 * a separate store since site notes are a distinct concern from inversion
 * results (one note can inform many jobs for the same sensor).
 */
export interface SiteNoteStore {
  readonly enabled: boolean;
  init(): Promise<void>;
  set(siteId: string, note: string): Promise<void>;
  get(siteId: string): Promise<string | null>;
  close(): Promise<void>;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS site_notes (
  site_id    TEXT PRIMARY KEY,
  note       TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
`;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

class PostgresSiteNoteStore implements SiteNoteStore {
  readonly enabled = true;
  private readonly pool: Pool;

  constructor(connectionString: string, private readonly logger: FastifyBaseLogger) {
    this.pool = new Pool({ connectionString, max: 2 });
    this.pool.on('error', (err) => this.logger.error({ err: err.message }, 'Postgres pool error (site notes)'));
  }

  async init(): Promise<void> {
    const attempts = 10;
    for (let i = 1; i <= attempts; i++) {
      try {
        await this.pool.query(SCHEMA);
        this.logger.info('Postgres site_notes schema ready');
        return;
      } catch (err) {
        if (i === attempts) throw err;
        this.logger.warn({ attempt: i }, 'Postgres not ready (site notes) — retrying');
        await delay(Math.min(1000 * i, 5000));
      }
    }
  }

  async set(siteId: string, note: string): Promise<void> {
    await this.pool.query(
      `INSERT INTO site_notes (site_id, note, updated_at) VALUES ($1, $2, now())
       ON CONFLICT (site_id) DO UPDATE SET note = $2, updated_at = now()`,
      [siteId, note],
    );
  }

  async get(siteId: string): Promise<string | null> {
    const { rows } = await this.pool.query('SELECT note FROM site_notes WHERE site_id = $1', [siteId]);
    return rows[0]?.note ?? null;
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}

class InMemorySiteNoteStore implements SiteNoteStore {
  readonly enabled = false;
  private readonly notes = new Map<string, string>();

  constructor(private readonly logger: FastifyBaseLogger) {}

  async init(): Promise<void> {
    this.logger.warn('DATABASE_URL not set — site notes kept in memory only (lost on restart)');
  }

  async set(siteId: string, note: string): Promise<void> {
    this.notes.set(siteId, note);
  }

  async get(siteId: string): Promise<string | null> {
    return this.notes.get(siteId) ?? null;
  }

  async close(): Promise<void> {
    /* no-op */
  }
}

export function createSiteNoteStore(
  connectionString: string | undefined,
  logger: FastifyBaseLogger,
): SiteNoteStore {
  return connectionString
    ? new PostgresSiteNoteStore(connectionString, logger)
    : new InMemorySiteNoteStore(logger);
}

// From 'pg', the runtime package — never '@types/pg' (see db.ts).
import { Pool } from 'pg';
import type { FastifyBaseLogger } from 'fastify';

/**
 * Persisted conversation turns for the per-site Chat Agent (see
 * app/agent/chat_agent.py). Same enabled/no-op-fallback shape as
 * db.ts's Repository and siteNotes.ts's SiteNoteStore, kept as its own
 * store since a chat transcript is a distinct concern from inversion
 * results (many turns per site, appended incrementally rather than
 * upserted).
 */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citedRuns: string[];
  createdAt: number;
}

export interface ChatHistoryStore {
  readonly enabled: boolean;
  init(): Promise<void>;
  append(siteId: string, message: ChatMessage): Promise<void>;
  listBySite(siteId: string, limit: number): Promise<ChatMessage[]>;
  close(): Promise<void>;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS chat_messages (
  id          SERIAL PRIMARY KEY,
  site_id     TEXT NOT NULL,
  role        TEXT NOT NULL,
  content     TEXT NOT NULL,
  cited_runs  JSONB NOT NULL DEFAULT '[]',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_site_id_created_at
  ON chat_messages (site_id, created_at ASC);
`;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function rowToMessage(row: any): ChatMessage {
  return {
    role: row.role,
    content: row.content,
    citedRuns: row.cited_runs ?? [],
    createdAt: new Date(row.created_at).getTime(),
  };
}

class PostgresChatHistoryStore implements ChatHistoryStore {
  readonly enabled = true;
  private readonly pool: Pool;

  constructor(connectionString: string, private readonly logger: FastifyBaseLogger) {
    this.pool = new Pool({ connectionString, max: 2 });
    this.pool.on('error', (err) => this.logger.error({ err: err.message }, 'Postgres pool error (chat history)'));
  }

  async init(): Promise<void> {
    const attempts = 10;
    for (let i = 1; i <= attempts; i++) {
      try {
        await this.pool.query(SCHEMA);
        this.logger.info('Postgres chat_messages schema ready');
        return;
      } catch (err) {
        if (i === attempts) throw err;
        this.logger.warn({ attempt: i }, 'Postgres not ready (chat history) — retrying');
        await delay(Math.min(1000 * i, 5000));
      }
    }
  }

  async append(siteId: string, message: ChatMessage): Promise<void> {
    await this.pool.query(
      `INSERT INTO chat_messages (site_id, role, content, cited_runs, created_at)
       VALUES ($1, $2, $3, $4, $5)`,
      [siteId, message.role, message.content, JSON.stringify(message.citedRuns), new Date(message.createdAt).toISOString()],
    );
  }

  async listBySite(siteId: string, limit: number): Promise<ChatMessage[]> {
    const { rows } = await this.pool.query(
      `SELECT * FROM (
         SELECT * FROM chat_messages WHERE site_id = $1 ORDER BY created_at DESC LIMIT $2
       ) sub ORDER BY created_at ASC`,
      [siteId, limit],
    );
    return rows.map(rowToMessage);
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}

class InMemoryChatHistoryStore implements ChatHistoryStore {
  readonly enabled = false;
  private readonly messages = new Map<string, ChatMessage[]>();

  constructor(private readonly logger: FastifyBaseLogger) {}

  async init(): Promise<void> {
    this.logger.warn('DATABASE_URL not set — chat history kept in memory only (lost on restart)');
  }

  async append(siteId: string, message: ChatMessage): Promise<void> {
    const existing = this.messages.get(siteId) ?? [];
    existing.push(message);
    this.messages.set(siteId, existing);
  }

  async listBySite(siteId: string, limit: number): Promise<ChatMessage[]> {
    const existing = this.messages.get(siteId) ?? [];
    return existing.slice(-limit);
  }

  async close(): Promise<void> {
    /* no-op */
  }
}

export function createChatHistoryStore(
  connectionString: string | undefined,
  logger: FastifyBaseLogger,
): ChatHistoryStore {
  return connectionString
    ? new PostgresChatHistoryStore(connectionString, logger)
    : new InMemoryChatHistoryStore(logger);
}

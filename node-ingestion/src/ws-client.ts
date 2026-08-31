import WebSocket from 'ws';
import type { FastifyBaseLogger } from 'fastify';

export interface AgentClientOptions {
  url: string;
  baseDelayMs: number;
  maxDelayMs: number;
  maxBuffered: number;
  logger: FastifyBaseLogger;
  /** Invoked with the raw text of each inbound message from the agent backend. */
  onResult?: (raw: string) => void;
}

export interface SendOutcome {
  /** true if the message was buffered because the backend was unavailable. */
  queued: boolean;
}

/**
 * A resilient WebSocket client to the FastAPI agent backend.
 *
 * Responsibilities:
 *  - Auto-reconnect with exponential backoff when the backend drops.
 *  - Buffer outbound jobs (bounded) while disconnected, then flush on connect.
 *  - Surface inbound inversion results via the logger.
 */
export class AgentClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private readonly buffer: string[] = [];
  private stopped = false;

  constructor(private readonly opts: AgentClientOptions) {}

  connect(): void {
    this.stopped = false;
    this.open();
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  get bufferedCount(): number {
    return this.buffer.length;
  }

  /**
   * Send a message, or buffer it if the backend is unavailable.
   * The buffer is bounded; when full, the oldest job is dropped.
   */
  send(message: string): SendOutcome {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(message);
      return { queued: false };
    }

    if (this.buffer.length >= this.opts.maxBuffered) {
      this.buffer.shift();
      this.opts.logger.warn(
        { maxBuffered: this.opts.maxBuffered },
        'Outbound buffer full — dropped oldest job',
      );
    }
    this.buffer.push(message);
    return { queued: true };
  }

  close(): void {
    this.stopped = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  private open(): void {
    const { url, logger } = this.opts;
    logger.info({ url }, 'Connecting to FastAPI agent backend');

    const ws = new WebSocket(url);
    this.ws = ws;

    ws.on('open', () => {
      this.reconnectAttempts = 0;
      logger.info('Connected to FastAPI agent backend');
      this.flush();
    });

    ws.on('message', (raw: WebSocket.RawData) => {
      const text = raw.toString();
      logger.info({ result: text }, 'Inversion result received from agent');
      this.opts.onResult?.(text);
    });

    ws.on('close', () => {
      if (this.stopped) return;
      logger.warn('Agent WS closed — scheduling reconnect');
      this.scheduleReconnect();
    });

    ws.on('error', (err: Error) => {
      // A failed connection emits 'error' then 'close'; reconnect is handled
      // in the 'close' handler so we don't schedule it twice here.
      logger.error({ err: err.message }, 'Agent WS error');
    });
  }

  private scheduleReconnect(): void {
    if (this.stopped || this.reconnectTimer) return;

    const { baseDelayMs, maxDelayMs, logger } = this.opts;
    const delay = Math.min(baseDelayMs * 2 ** this.reconnectAttempts, maxDelayMs);
    this.reconnectAttempts += 1;

    logger.info({ delayMs: delay, attempt: this.reconnectAttempts }, 'Reconnecting to agent backend');
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.open();
    }, delay);
  }

  private flush(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    if (this.buffer.length === 0) return;

    this.opts.logger.info({ count: this.buffer.length }, 'Flushing buffered jobs');
    while (this.buffer.length > 0 && this.ws.readyState === WebSocket.OPEN) {
      const message = this.buffer.shift();
      if (message !== undefined) this.ws.send(message);
    }
  }
}

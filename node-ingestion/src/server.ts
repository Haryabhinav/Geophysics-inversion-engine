import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import type { ServerResponse } from 'node:http';
import Fastify from 'fastify';
import type { FastifyBaseLogger } from 'fastify';
import fastifyStatic from '@fastify/static';

import { config } from './config.js';
import { AgentClient } from './ws-client.js';
import { sanitize } from './sanitize.js';
import { createRepository } from './db.js';
import { createSiteNoteStore } from './siteNotes.js';
import { createChatHistoryStore } from './chatHistory.js';
import { createSiteReportStore } from './siteReports.js';
import { createAlerter } from './alert.js';
import { METHOD_IDS, SIMULATORS, isMethodId, type MethodId } from './methods.js';
import { buildLithologyDemoJob } from './lithologyDemo.js';
import type {
  SensorPayload,
  AgentJobPayload,
  InversionResult,
  PendingJob,
  PersistedInversion,
  BoreholeClassificationJobPayload,
} from './types.js';

const fastify = Fastify({
  logger: {
    level: process.env.LOG_LEVEL ?? 'info',
  },
});

const repository = createRepository(config.databaseUrl, fastify.log);
const siteNotes = createSiteNoteStore(config.databaseUrl, fastify.log);
const chatHistory = createChatHistoryStore(config.databaseUrl, fastify.log);
const siteReports = createSiteReportStore(config.databaseUrl, fastify.log);
const alerter = createAlerter(config.alertWebhookUrl, fastify.log);

// ---------------------------------------------------------------------------
// In-flight + recent state (also feeds the dashboard when there is no database)
// ---------------------------------------------------------------------------
const pendingJobs = new Map<string, PendingJob>();
const MAX_PENDING = 10_000;

const recent: PersistedInversion[] = [];
const recentById = new Map<string, PersistedInversion>();
const MAX_RECENT = 200;

function remember(record: PersistedInversion): void {
  recent.unshift(record);
  recentById.set(record.jobId, record);
  if (recent.length > MAX_RECENT) {
    const dropped = recent.pop();
    if (dropped) recentById.delete(dropped.jobId);
  }
}

// ---------------------------------------------------------------------------
// Server-Sent Events — live push to the dashboard
// ---------------------------------------------------------------------------
const sseClients = new Set<ServerResponse>();

function broadcast(event: string, data: unknown): void {
  const frame = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const client of sseClients) {
    try {
      client.write(frame);
    } catch {
      sseClients.delete(client);
    }
  }
}

// ---------------------------------------------------------------------------
// Result handling: enrich → remember → persist → alert → push
// ---------------------------------------------------------------------------
async function handleResult(raw: string): Promise<void> {
  let parsed: Partial<InversionResult>;
  try {
    parsed = JSON.parse(raw) as Partial<InversionResult>;
  } catch {
    fastify.log.error('Could not parse agent message as JSON');
    return;
  }

  const jobId = parsed.jobId;
  if (!jobId) {
    fastify.log.warn({ message: parsed }, 'Agent message without jobId (ignored)');
    return;
  }

  const pending = pendingJobs.get(jobId);
  pendingJobs.delete(jobId);

  const record: PersistedInversion = {
    jobId,
    sensorId: pending?.sensorId ?? 'unknown',
    dataType: pending?.dataType ?? 'TDEM',
    status: parsed.status ?? 'error',
    l2NormError: parsed.l2_norm_error ?? null,
    iterations: parsed.iterations ?? 0,
    finalModel: parsed.final_model ?? {},
    message: parsed.message ?? null,
    samplesUsed: pending?.samplesUsed ?? 0,
    droppedCount: pending?.droppedCount ?? 0,
    createdAt: pending?.createdAt ?? Date.now(),
    observed: pending?.observed ?? null,
    predicted: parsed.predicted ?? null,
    l2History: parsed.l2_history ?? [],
    equivalentModels: parsed.equivalent_models ?? [],
    interpretation: parsed.interpretation ?? null,
  };

  remember(record);

  try {
    await repository.save(record);
  } catch (err) {
    fastify.log.error({ err: (err as Error).message, jobId }, 'Failed to persist inversion result');
  }

  await alerter.notify(record);
  broadcast('result', record);
}

const agent = new AgentClient({
  url: config.agentWsUrl,
  baseDelayMs: config.reconnectBaseDelayMs,
  maxDelayMs: config.reconnectMaxDelayMs,
  maxBuffered: config.maxBufferedJobs,
  logger: fastify.log,
  onResult: (raw) => void handleResult(raw),
});

// ---------------------------------------------------------------------------
// Job submission (shared by /ingest/field-data and /simulate)
// ---------------------------------------------------------------------------
type SubmitOutcome =
  | { ok: false; totalCount: number; droppedCount: number }
  | { ok: true; jobId: string; accepted: number; dropped: number; queued: boolean };

async function submitJob(payload: SensorPayload, log: FastifyBaseLogger): Promise<SubmitOutcome> {
  const { clean, totalCount, droppedCount } = sanitize(payload);
  if (clean.time.length === 0) {
    return { ok: false, totalCount, droppedCount };
  }

  const jobId = `job_${Date.now()}_${randomUUID().slice(0, 8)}`;
  const createdAt = Date.now();
  const siteNote = await siteNotes.get(payload.sensorId).catch(() => null);
  const job: AgentJobPayload = {
    jobId,
    sensorId: payload.sensorId,
    dataType: payload.dataType,
    data: clean,
    siteNote,
    auxData: payload.auxData,
  };

  if (pendingJobs.size < MAX_PENDING) {
    pendingJobs.set(jobId, {
      sensorId: payload.sensorId,
      dataType: payload.dataType,
      samplesUsed: clean.time.length,
      droppedCount,
      createdAt,
      observed: clean,
    });
  } else {
    log.warn('Pending-job map full — result will persist without metadata');
  }

  const { queued } = agent.send(JSON.stringify(job));
  broadcast('pending', {
    jobId,
    sensorId: payload.sensorId,
    dataType: payload.dataType,
    samplesUsed: clean.time.length,
    droppedCount,
    createdAt,
  });
  log.info({ jobId, kept: clean.time.length, droppedCount, queued }, 'Field-data batch accepted');

  return { ok: true, jobId, accepted: clean.time.length, dropped: droppedCount, queued };
}

/**
 * LITHOLOGY submission — a parallel path to submitJob(), not a branch
 * inside it: the payload shape (labeled train + unlabeled predict log
 * curves) doesn't go through sanitize() (there's no time/amplitude pair to
 * clean) and carries no `data`/`auxData`, so forcing it through the
 * SensorPayload-shaped function would need more special-casing than it's
 * worth. The result Python sends back is still an InversionResult (see
 * main.py's _handle_lithology_job), so handleResult() needs no changes.
 */
async function submitClassificationJob(
  job: BoreholeClassificationJobPayload,
  log: FastifyBaseLogger,
): Promise<{ ok: true; jobId: string; accepted: number }> {
  const createdAt = Date.now();
  const siteNote = await siteNotes.get(job.sensorId).catch(() => null);
  const jobWithNote = { ...job, siteNote };

  if (pendingJobs.size < MAX_PENDING) {
    pendingJobs.set(job.jobId, {
      sensorId: job.sensorId,
      dataType: 'LITHOLOGY',
      samplesUsed: job.predict.depth.length,
      droppedCount: 0,
      createdAt,
      observed: { time: job.predict.depth, amplitude: [] },
    });
  } else {
    log.warn('Pending-job map full — result will persist without metadata');
  }

  const { queued } = agent.send(JSON.stringify(jobWithNote));
  broadcast('pending', {
    jobId: job.jobId,
    sensorId: job.sensorId,
    dataType: 'LITHOLOGY',
    samplesUsed: job.predict.depth.length,
    droppedCount: 0,
    createdAt,
  });
  log.info(
    { jobId: job.jobId, train: job.train.depth.length, predict: job.predict.depth.length, queued },
    'Lithology classification job accepted',
  );

  return { ok: true, jobId: job.jobId, accepted: job.predict.depth.length };
}

/** HTTP base of the agent (derived from the WebSocket URL) for a mode probe. */
const agentHttpBase = (() => {
  try {
    const u = new URL(config.agentWsUrl);
    return `${u.protocol === 'wss:' ? 'https:' : 'http:'}//${u.host}`;
  } catch {
    return 'http://localhost:8000';
  }
})();

async function fetchAgentMode(): Promise<string> {
  try {
    const res = await fetch(`${agentHttpBase}/health`, { signal: AbortSignal.timeout(2000) });
    if (res.ok) {
      const health = (await res.json()) as { mode?: string };
      return health.mode ?? 'llm';
    }
  } catch {
    /* agent may be starting; default below */
  }
  return 'llm';
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------
const sensorPayloadSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['sensorId', 'dataType', 'timeSteps', 'amplitudes'],
  properties: {
    sensorId: { type: 'string', minLength: 1 },
    dataType: { type: 'string', enum: [...METHOD_IDS] },
    timeSteps: { type: 'array', items: { type: ['number', 'null'] } },
    amplitudes: { type: 'array', items: { type: ['number', 'null'] } },
  },
} as const;

fastify.get('/health', async () => ({
  status: 'ok',
  backendConnected: agent.connected,
  buffered: agent.bufferedCount,
  persistence: repository.enabled,
  pending: pendingJobs.size,
}));

fastify.post<{ Body: SensorPayload }>(
  '/ingest/field-data',
  { schema: { body: sensorPayloadSchema } },
  async (request, reply) => {
    const outcome = await submitJob(request.body, request.log);
    if (!outcome.ok) {
      return reply.status(422).send({
        status: 'rejected',
        reason: 'no_valid_samples',
        totalCount: outcome.totalCount,
        droppedCount: outcome.droppedCount,
      });
    }
    return reply.status(202).send({
      status: outcome.queued ? 'queued_awaiting_backend' : 'processing_initiated',
      jobId: outcome.jobId,
      accepted: outcome.accepted,
      dropped: outcome.dropped,
      backendConnected: agent.connected,
    });
  },
);

// Dashboard convenience: generate + submit a synthetic TDEM job. The dataset is
// chosen to match the active modeler: empymod physics for the Gemini agent,
// bi-exponential for the offline optimizer (so it converges with no API key).
// Dashboard convenience: generate + submit a synthetic job for any registered
// method. `method` defaults to TDEM so existing calls with no body keep
// working unchanged. The dataset is chosen to match the active modeler where
// relevant (empymod physics for the Gemini agent, bi-exponential for the
// offline optimizer — see methods.ts).
fastify.post<{ Body?: { method?: string } }>('/simulate', async (request, reply) => {
  const requested = request.body?.method ?? 'TDEM';

  if (requested === 'LITHOLOGY') {
    const jobId = `job_${Date.now()}_${randomUUID().slice(0, 8)}`;
    const job = buildLithologyDemoJob(jobId);
    const outcome = await submitClassificationJob(job, request.log);
    return reply.status(202).send({
      status: 'processing_initiated',
      jobId: outcome.jobId,
      method: 'LITHOLOGY',
      accepted: outcome.accepted,
      dropped: 0,
    });
  }

  if (!isMethodId(requested)) {
    return reply.status(400).send({ status: 'rejected', reason: 'unknown_method', method: requested });
  }
  const method: MethodId = requested;
  const mode = await fetchAgentMode();
  const payload = SIMULATORS[method](mode);
  const outcome = await submitJob(payload, request.log);
  // Synthetic data always has valid samples, so outcome.ok is true.
  if (!outcome.ok) return reply.status(500).send({ status: 'error' });
  return reply.status(202).send({
    status: 'processing_initiated',
    jobId: outcome.jobId,
    method,
    accepted: outcome.accepted,
    dropped: outcome.dropped,
  });
});

// Free-text site context (driller's log / geological note) for a sensorId.
// Looked up on every subsequent job for that sensor and forwarded to the
// Python agent's Interpretation Agent (see app/agent/interpreter.py).
const contextBodySchema = {
  type: 'object',
  additionalProperties: false,
  required: ['note'],
  properties: {
    note: { type: 'string', minLength: 1, maxLength: 4000 },
  },
} as const;

fastify.post<{ Params: { siteId: string }; Body: { note: string } }>(
  '/context/:siteId',
  { schema: { body: contextBodySchema } },
  async (request, reply) => {
    const { siteId } = request.params;
    await siteNotes.set(siteId, request.body.note);
    request.log.info({ siteId }, 'Site note recorded');
    return reply.status(200).send({ status: 'ok', siteId });
  },
);

fastify.get('/context/:siteId', async (request, reply) => {
  const { siteId } = request.params as { siteId: string };
  const note = await siteNotes.get(siteId);
  if (note === null) return reply.status(404).send({ status: 'not_found', siteId });
  return { siteId, note };
});

fastify.get('/results', async (request) => {
  const q = request.query as { limit?: string; sensorId?: string };
  const limit = Math.min(Number(q.limit ?? 50) || 50, MAX_RECENT);
  if (q.sensorId) {
    return repository.enabled ? await repository.listBySite(q.sensorId, limit) : recentBySite(q.sensorId, limit);
  }
  return repository.enabled ? await repository.list(limit) : recent.slice(0, limit);
});

fastify.get('/results/:jobId', async (request, reply) => {
  const { jobId } = request.params as { jobId: string };
  const record = repository.enabled ? await repository.get(jobId) : recentById.get(jobId) ?? null;
  if (!record) return reply.status(404).send({ status: 'not_found', jobId });
  return record;
});

/** In-memory fallback for Repository.listBySite when there's no database —
 * mirrors how `recent`/`recentById` already fall back for /results. */
function recentBySite(sensorId: string, limit: number): PersistedInversion[] {
  return recent.filter((r) => r.sensorId === sensorId).slice(0, limit);
}

// Multi-method Joint Interpretation capstone: gather this site's recent
// results (deduped to the latest successful run per method), fetch its site
// note, and ask the Python agent to synthesize them into one integrated report.
fastify.post('/sites/:siteId/interpret', async (request, reply) => {
  const { siteId } = request.params as { siteId: string };
  const q = request.query as { limit?: string };
  const limit = Math.min(Number(q.limit ?? 20) || 20, MAX_RECENT);

  const history = repository.enabled ? await repository.listBySite(siteId, limit) : recentBySite(siteId, limit);
  if (history.length === 0) {
    return reply.status(404).send({ status: 'not_found', siteId });
  }

  // Dedup to the most recent NON-ERROR run per dataType, so the prompt
  // stays compact and never has to reconcile a method against a stale
  // re-run of itself.
  const latestPerMethod = new Map<string, PersistedInversion>();
  for (const record of history) {
    if (record.status === 'error') continue;
    if (!latestPerMethod.has(record.dataType)) latestPerMethod.set(record.dataType, record);
  }
  if (latestPerMethod.size === 0) {
    return reply.status(404).send({ status: 'not_found', siteId, reason: 'no_successful_runs' });
  }

  const siteNote = await siteNotes.get(siteId).catch(() => null);
  const methodResults = [...latestPerMethod.values()].map((r) => ({
    jobId: r.jobId,
    dataType: r.dataType,
    status: r.status,
    finalModel: r.finalModel,
    l2NormError: r.l2NormError,
    interpretation: r.interpretation,
    createdAt: r.createdAt,
  }));

  let joint: unknown;
  try {
    const res = await fetch(`${agentHttpBase}/interpret/joint`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ siteId, siteNote, methodResults }),
      signal: AbortSignal.timeout(30_000),
    });
    if (!res.ok) {
      const body = await res.text();
      return reply.status(502).send({ status: 'error', siteId, message: `agent returned ${res.status}: ${body}` });
    }
    joint = await res.json();
  } catch (err) {
    return reply.status(502).send({ status: 'error', siteId, message: (err as Error).message });
  }

  broadcast('joint_interpretation', joint);
  return joint;
});

/** Gathers this site's run history (deduped to the latest non-error run per
 * method, mirroring /sites/:siteId/interpret) as the MethodResultInput
 * shape both /chat/query and /reports/site on the Python side expect. */
function siteMethodResults(history: PersistedInversion[]): unknown[] {
  const latestPerMethod = new Map<string, PersistedInversion>();
  for (const record of history) {
    if (record.status === 'error') continue;
    if (!latestPerMethod.has(record.dataType)) latestPerMethod.set(record.dataType, record);
  }
  return [...latestPerMethod.values()].map((r) => ({
    jobId: r.jobId,
    dataType: r.dataType,
    status: r.status,
    finalModel: r.finalModel,
    l2NormError: r.l2NormError,
    interpretation: r.interpretation,
    createdAt: r.createdAt,
  }));
}

// Site Chat Agent: answers a natural-language question about one site's own
// run/interpretation history. Gathers the same run history as
// /sites/:siteId/interpret, replays prior chat turns for continuity, proxies
// to Python's POST /chat/query, and persists both the question and answer.
const chatBodySchema = {
  type: 'object',
  additionalProperties: false,
  required: ['question'],
  properties: {
    question: { type: 'string', minLength: 1, maxLength: 2000 },
  },
} as const;

fastify.post<{ Params: { siteId: string }; Body: { question: string } }>(
  '/sites/:siteId/chat',
  { schema: { body: chatBodySchema } },
  async (request, reply) => {
    const { siteId } = request.params;
    const { question } = request.body;

    const history = repository.enabled ? await repository.listBySite(siteId, MAX_RECENT) : recentBySite(siteId, MAX_RECENT);
    const runHistory = siteMethodResults(history);
    const siteNote = await siteNotes.get(siteId).catch(() => null);
    const priorTurns = (await chatHistory.listBySite(siteId, 50)).map((m) => ({ role: m.role, content: m.content }));

    let parsed: { answer: string; citedRuns: string[]; confidence: string };
    try {
      const res = await fetch(`${agentHttpBase}/chat/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ siteId, question, history: priorTurns, runHistory, siteNote }),
        signal: AbortSignal.timeout(60_000),
      });
      const body = await res.json().catch(() => ({ status: 'error', message: 'invalid response from agent' }));
      if (!res.ok) return reply.status(res.status).send(body);
      parsed = body as typeof parsed;
    } catch (err) {
      return reply.status(502).send({ status: 'error', message: (err as Error).message });
    }

    const now = Date.now();
    await chatHistory.append(siteId, { role: 'user', content: question, citedRuns: [], createdAt: now });
    await chatHistory.append(siteId, {
      role: 'assistant',
      content: parsed.answer,
      citedRuns: parsed.citedRuns ?? [],
      createdAt: now + 1,
    });

    return { siteId, ...parsed };
  },
);

fastify.get('/sites/:siteId/chat', async (request) => {
  const { siteId } = request.params as { siteId: string };
  const messages = await chatHistory.listBySite(siteId, 200);
  return { siteId, messages };
});

// Site Report Generator: drafts a markdown report from a site's run history
// and, when available, its most recent joint interpretation. Persists the
// result and pushes it live over SSE, mirroring /sites/:siteId/interpret.
fastify.post('/sites/:siteId/report', async (request, reply) => {
  const { siteId } = request.params as { siteId: string };

  const history = repository.enabled ? await repository.listBySite(siteId, MAX_RECENT) : recentBySite(siteId, MAX_RECENT);
  if (history.length === 0) {
    return reply.status(404).send({ status: 'not_found', siteId });
  }
  const runHistory = siteMethodResults(history);
  if (runHistory.length === 0) {
    return reply.status(404).send({ status: 'not_found', siteId, reason: 'no_successful_runs' });
  }
  const siteNote = await siteNotes.get(siteId).catch(() => null);

  let report: { markdown: string; summary: string };
  try {
    const res = await fetch(`${agentHttpBase}/reports/site`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ siteId, runHistory, siteNote, jointInterpretation: null }),
      signal: AbortSignal.timeout(60_000),
    });
    const body = await res.json().catch(() => ({ status: 'error', message: 'invalid response from agent' }));
    if (!res.ok) return reply.status(res.status).send(body);
    report = body as typeof report;
  } catch (err) {
    return reply.status(502).send({ status: 'error', message: (err as Error).message });
  }

  const record = { siteId, markdown: report.markdown, summary: report.summary, createdAt: Date.now() };
  try {
    await siteReports.save(record);
  } catch (err) {
    fastify.log.error({ err: (err as Error).message, siteId }, 'Failed to persist site report');
  }

  broadcast('site_report', record);
  return record;
});

fastify.get('/sites/:siteId/reports', async (request) => {
  const { siteId } = request.params as { siteId: string };
  const reports = await siteReports.listBySite(siteId, 50);
  return { siteId, reports };
});

// Raw-data Cleaning Agent (dashboard Upload page only — see
// dashboard/pages/upload.tsx). A plain proxy to Python's POST /clean,
// mirroring /sites/:siteId/interpret's forward-and-relay-errors shape. The
// CLEANED result still goes through the normal /ingest/field-data path —
// this route never itself creates a job or touches persistence.
const cleanBodySchema = {
  type: 'object',
  additionalProperties: false,
  required: ['dataType', 'fileName', 'rawText'],
  properties: {
    dataType: { type: 'string', minLength: 1 },
    fileName: { type: 'string', minLength: 1 },
    rawText: { type: 'string', minLength: 1, maxLength: 50_000 },
  },
} as const;

fastify.post<{ Body: { dataType: string; fileName: string; rawText: string } }>(
  '/clean/raw-data',
  { schema: { body: cleanBodySchema } },
  async (request, reply) => {
    try {
      const res = await fetch(`${agentHttpBase}/clean`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request.body),
        // Generous: a single LLM call plus Gemini's own 429 retry/backoff
        // (llm_client.py) can legitimately take a while.
        signal: AbortSignal.timeout(60_000),
      });
      const body = await res.json().catch(() => ({ status: 'error', message: 'invalid response from agent' }));
      return reply.status(res.status).send(body);
    } catch (err) {
      return reply.status(502).send({ status: 'error', message: (err as Error).message });
    }
  },
);

fastify.get('/events', (request, reply) => {
  reply.hijack();
  reply.raw.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  });
  reply.raw.write(': connected\n\n');
  sseClients.add(reply.raw);
  request.raw.on('close', () => sseClients.delete(reply.raw));
});

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
async function start(): Promise<void> {
  await fastify.register(fastifyStatic, {
    root: fileURLToPath(new URL('../public', import.meta.url)),
    prefix: '/',
  });

  try {
    await repository.init();
  } catch (err) {
    fastify.log.error({ err: (err as Error).message }, 'Repository init failed — continuing without persistence');
  }

  try {
    await siteNotes.init();
  } catch (err) {
    fastify.log.error({ err: (err as Error).message }, 'Site-note store init failed — continuing without it');
  }

  try {
    await chatHistory.init();
  } catch (err) {
    fastify.log.error({ err: (err as Error).message }, 'Chat history store init failed — continuing without it');
  }

  try {
    await siteReports.init();
  } catch (err) {
    fastify.log.error({ err: (err as Error).message }, 'Site report store init failed — continuing without it');
  }

  agent.connect();
  try {
    await fastify.listen({ port: config.httpPort, host: '0.0.0.0' });
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}

async function shutdown(signal: string): Promise<void> {
  fastify.log.info({ signal }, 'Shutting down');
  agent.close();
  for (const client of sseClients) client.end();
  await repository.close();
  await siteNotes.close();
  await chatHistory.close();
  await siteReports.close();
  await fastify.close();
  process.exit(0);
}

process.on('SIGINT', () => void shutdown('SIGINT'));
process.on('SIGTERM', () => void shutdown('SIGTERM'));

void start();

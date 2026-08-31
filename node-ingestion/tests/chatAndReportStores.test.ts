import { describe, it, expect } from 'vitest';
import type { FastifyBaseLogger } from 'fastify';

import { createChatHistoryStore } from '../src/chatHistory';
import { createSiteReportStore } from '../src/siteReports';

// Minimal stand-in — these stores only call .warn()/.error() on their logger.
const nullLogger = { warn: () => {}, error: () => {} } as unknown as FastifyBaseLogger;

describe('createChatHistoryStore (no DATABASE_URL -> in-memory fallback)', () => {
  it('is disabled and keeps turns per site, oldest first', async () => {
    const store = createChatHistoryStore(undefined, nullLogger);
    expect(store.enabled).toBe(false);
    await store.init();

    await store.append('site-1', { role: 'user', content: 'Q1', citedRuns: [], createdAt: 1 });
    await store.append('site-1', { role: 'assistant', content: 'A1', citedRuns: ['job-1'], createdAt: 2 });
    await store.append('site-2', { role: 'user', content: 'other site', citedRuns: [], createdAt: 3 });

    const history = await store.listBySite('site-1', 50);
    expect(history.map((m) => m.content)).toEqual(['Q1', 'A1']);
    expect(history[1].citedRuns).toEqual(['job-1']);
  });

  it('caps results to the requested limit, keeping the most recent', async () => {
    const store = createChatHistoryStore(undefined, nullLogger);
    for (let i = 0; i < 5; i++) {
      await store.append('site-1', { role: 'user', content: `Q${i}`, citedRuns: [], createdAt: i });
    }
    const history = await store.listBySite('site-1', 2);
    expect(history.map((m) => m.content)).toEqual(['Q3', 'Q4']);
  });
});

describe('createSiteReportStore (no DATABASE_URL -> in-memory fallback)', () => {
  it('is disabled and returns saved reports newest first', async () => {
    const store = createSiteReportStore(undefined, nullLogger);
    expect(store.enabled).toBe(false);
    await store.init();

    await store.save({ siteId: 'site-1', markdown: '# First', summary: 'first', createdAt: 1 });
    await store.save({ siteId: 'site-1', markdown: '# Second', summary: 'second', createdAt: 2 });

    const reports = await store.listBySite('site-1', 50);
    expect(reports.map((r) => r.summary)).toEqual(['second', 'first']);
  });

  it('keeps reports scoped per site', async () => {
    const store = createSiteReportStore(undefined, nullLogger);
    await store.save({ siteId: 'site-1', markdown: '# A', summary: 'a', createdAt: 1 });
    await store.save({ siteId: 'site-2', markdown: '# B', summary: 'b', createdAt: 2 });

    expect((await store.listBySite('site-1', 50)).map((r) => r.summary)).toEqual(['a']);
    expect((await store.listBySite('site-2', 50)).map((r) => r.summary)).toEqual(['b']);
  });
});

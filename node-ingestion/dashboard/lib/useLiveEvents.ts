import { useEffect } from 'react';

import { API_BASE_URL } from '@lib/http';
import { queryClient } from '@lib/react-query';
import { useLiveStore } from '@store/useLiveStore';
import type { PendingEvent, PersistedInversion, SiteReportEvent } from '@types_/api';

/**
 * Subscribes once (mounted from _app) to node-ingestion's `/events` SSE
 * stream and fans updates into the Zustand live store, plus invalidates the
 * relevant React Query caches so any page showing a results list picks up
 * the new job without a manual refresh.
 */
export function useLiveEvents(): void {
  const pushPending = useLiveStore((s) => s.pushPending);
  const pushResult = useLiveStore((s) => s.pushResult);
  const setConnected = useLiveStore((s) => s.setConnected);

  useEffect(() => {
    const source = new EventSource(`${API_BASE_URL}/events`);

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    source.addEventListener('pending', (evt) => {
      const payload = JSON.parse((evt as MessageEvent).data) as PendingEvent;
      pushPending(payload);
      queryClient.invalidateQueries({ queryKey: ['results'] });
    });

    source.addEventListener('result', (evt) => {
      const payload = JSON.parse((evt as MessageEvent).data) as PersistedInversion;
      pushResult(payload);
      queryClient.invalidateQueries({ queryKey: ['results'] });
      queryClient.invalidateQueries({ queryKey: ['result', payload.jobId] });
      queryClient.invalidateQueries({ queryKey: ['siteHistory', payload.sensorId] });
    });

    source.addEventListener('site_report', (evt) => {
      const payload = JSON.parse((evt as MessageEvent).data) as SiteReportEvent;
      queryClient.invalidateQueries({ queryKey: ['reports', payload.siteId] });
    });

    return () => source.close();
  }, [pushPending, pushResult, setConnected]);
}

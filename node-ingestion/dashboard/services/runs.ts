import { http } from '@lib/http';
import type { PersistedInversion, SimulateResponse } from '@types_/api';

export interface IngestResponse {
  status: string;
  jobId: string;
  accepted: number;
  dropped: number;
  backendConnected: boolean;
}

/** Submits one parsed curve as a real field-data job — the same endpoint
 * hardware POSTs to (`spec.md` §3, `server.ts`'s `/ingest/field-data`). */
export async function ingestFieldData(payload: {
  sensorId: string;
  dataType: string;
  timeSteps: (number | null)[];
  amplitudes: (number | null)[];
}): Promise<IngestResponse> {
  const { data } = await http.post<IngestResponse>('/ingest/field-data', payload);
  return data;
}

export async function listResults(limit = 50): Promise<PersistedInversion[]> {
  const { data } = await http.get<PersistedInversion[]>('/results', { params: { limit } });
  return data;
}

export async function getResult(jobId: string): Promise<PersistedInversion> {
  const { data } = await http.get<PersistedInversion>(`/results/${encodeURIComponent(jobId)}`);
  return data;
}

export async function simulate(method: string): Promise<SimulateResponse> {
  const { data } = await http.post<SimulateResponse>('/simulate', { method });
  return data;
}

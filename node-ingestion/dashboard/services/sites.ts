import { ApiError, http } from '@lib/http';
import type { JointInterpretationResult, PersistedInversion, SiteNoteResponse } from '@types_/api';

export async function listSiteHistory(sensorId: string, limit = 50): Promise<PersistedInversion[]> {
  const { data } = await http.get<PersistedInversion[]>('/results', { params: { sensorId, limit } });
  return data;
}

export async function getSiteNote(siteId: string): Promise<string | null> {
  try {
    const { data } = await http.get<SiteNoteResponse>(`/context/${encodeURIComponent(siteId)}`);
    return data.note;
  } catch (err) {
    if (err instanceof ApiError && err.statusCode === 404) return null;
    throw err;
  }
}

export async function setSiteNote(siteId: string, note: string): Promise<void> {
  await http.post(`/context/${encodeURIComponent(siteId)}`, { note });
}

export async function requestJointInterpretation(
  siteId: string,
  limit = 20,
): Promise<JointInterpretationResult> {
  const { data } = await http.post<JointInterpretationResult>(
    `/sites/${encodeURIComponent(siteId)}/interpret`,
    undefined,
    { params: { limit } },
  );
  return data;
}

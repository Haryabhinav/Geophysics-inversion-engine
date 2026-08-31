import { http } from '@lib/http';
import type { SiteReport, SiteReportsResponse } from '@types_/api';

/**
 * Site Report Generator: drafts an LLM-authored markdown report from a
 * site's run history (`POST /sites/:siteId/report` -> python-agent's
 * `POST /reports/site`). Node persists every generated report, so
 * `getReports` returns the full history (newest first).
 */
export async function getReports(siteId: string): Promise<SiteReportsResponse> {
  const { data } = await http.get<SiteReportsResponse>(`/sites/${encodeURIComponent(siteId)}/reports`);
  return data;
}

export async function generateReport(siteId: string): Promise<SiteReport> {
  const { data } = await http.post<SiteReport>(`/sites/${encodeURIComponent(siteId)}/report`);
  return data;
}

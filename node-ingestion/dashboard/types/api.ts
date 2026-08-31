/**
 * Wire types mirroring node-ingestion's src/types.ts and the JSON shapes it
 * proxies from python-agent. Kept as a hand-written mirror (not a shared
 * package) since the two are small and independently versioned services.
 */

export type Confidence = 'high' | 'medium' | 'low';
export type InversionStatus = 'converged' | 'max_iterations_reached' | 'error';
export type Corroboration = 'consistent' | 'conflicting' | 'inconclusive';

export interface CleanSeries {
  time: number[];
  amplitude: number[];
}

export interface InterpretationResult {
  siteId: string;
  summary: string;
  confidence: Confidence;
  flagged_anomaly: boolean;
  reasoning: string;
}

export interface EquivalentModel {
  model: Record<string, unknown>;
  l2_norm_error: number;
}

export interface PersistedInversion {
  jobId: string;
  sensorId: string;
  dataType: string;
  status: InversionStatus | 'rejected';
  l2NormError: number | null;
  iterations: number;
  finalModel: Record<string, unknown>;
  message: string | null;
  samplesUsed: number;
  droppedCount: number;
  createdAt: number;
  observed: CleanSeries | null;
  predicted: number[] | null;
  l2History: number[];
  equivalentModels: EquivalentModel[];
  interpretation: InterpretationResult | null;
}

export interface MethodContribution {
  jobId: string;
  dataType: string;
  contributesTo: string;
  singleMethodConfidence: Confidence | null;
  corroboration: Corroboration;
}

export interface JointInterpretationResult {
  siteId: string;
  summary: string;
  confidence: Confidence;
  flagged_anomaly: boolean;
  reasoning: string;
  corroboration: Corroboration;
  methodContributions: MethodContribution[];
  methodsConsidered: string[];
  conflicts: string[];
}

export interface SimulateResponse {
  status: string;
  jobId: string;
  method: string;
  accepted: number;
  dropped: number;
}

export interface HealthResponse {
  status: string;
  backendConnected: boolean;
  buffered: number;
  persistence: boolean;
  pending: number;
}

export interface SiteNoteResponse {
  siteId: string;
  note: string;
}

/** A `pending` SSE event — a job was just submitted, not yet resolved. */
export interface PendingEvent {
  jobId: string;
  sensorId: string;
  dataType: string;
  samplesUsed: number;
  droppedCount: number;
  createdAt: number;
}

export type ApiErrorBody = {
  status: string;
  reason?: string;
  message?: string;
  [key: string]: unknown;
};

/** What the Cleaning Agent (POST /clean/raw-data) hands back — see
 * python-agent's app/schemas_cleaning.py.CleaningResult. */
export interface CleaningResult {
  timeSteps: number[];
  amplitudes: number[];
  originalCount: number;
  droppedCount: number;
  summary: string;
  actions: string[];
}

/** A stored turn from the Site Chat Agent (GET/POST /sites/:siteId/chat) —
 * see node-ingestion's src/chatHistory.ts.ChatMessage. */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citedRuns: string[];
  createdAt: number;
}

export interface ChatHistoryResponse {
  siteId: string;
  messages: ChatMessage[];
}

/** POST /sites/:siteId/chat's response — the freshly-appended answer, plus
 * which stored runs it drew on. See python-agent's app/schemas_chat.py. */
export interface ChatAnswer {
  siteId: string;
  answer: string;
  citedRuns: string[];
  confidence: Confidence;
}

/** A generated site report — see node-ingestion's src/siteReports.ts.SiteReport
 * and python-agent's app/schemas_report.py.ReportResult. */
export interface SiteReport {
  siteId: string;
  markdown: string;
  summary: string;
  createdAt: number;
}

export interface SiteReportsResponse {
  siteId: string;
  reports: SiteReport[];
}

/** A `site_report` SSE event — a report finished generating and was persisted. */
export type SiteReportEvent = SiteReport;

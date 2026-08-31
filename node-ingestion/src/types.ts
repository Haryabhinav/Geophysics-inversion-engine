/**
 * Shared wire types for the ingestion layer.
 */
import type { MethodId } from './methods.js';

/** A registered geophysical method id — see methods.ts's METHOD_IDS, the
 * single source of truth (mirrors the Python METHOD_REGISTRY) — PLUS
 * 'LITHOLOGY', the one method that's a classification problem rather than
 * a curve fit, so it's deliberately excluded from METHOD_IDS/SIMULATORS
 * (which are typed around SensorPayload's single time/amplitude curve
 * shape) and handled via its own BoreholeClassificationJobPayload instead. */
export type DataType = MethodId | 'LITHOLOGY';

/** One named well-log curve (e.g. gamma ray, resistivity) — mirrors
 * Python's schemas_classification.LogCurve. */
export interface LogCurvePayload {
  name: string;
  unit: string;
  values: number[];
}

/** Depth-indexed log curves — mirrors WellLogSeries. */
export interface WellLogSeriesPayload {
  depth: number[];
  curves: LogCurvePayload[];
}

/** A WellLogSeriesPayload with a known lithology label per depth sample —
 * mirrors LabeledWellLogSeries. */
export interface LabeledWellLogSeriesPayload extends WellLogSeriesPayload {
  labels: string[];
}

/** The payload streamed over the WebSocket for the LITHOLOGY method —
 * mirrors Python's BoreholeClassificationJob. `predict` carries features
 * only; `predictTrueLabels` is for demo/test scoring only (see Python's
 * docstring) and is never forwarded into the sandbox on the Python side. */
export interface BoreholeClassificationJobPayload {
  jobId: string;
  sensorId: string;
  dataType: 'LITHOLOGY';
  train: LabeledWellLogSeriesPayload;
  predict: WellLogSeriesPayload;
  classes: string[];
  siteNote?: string | null;
  predictTrueLabels?: string[] | null;
}

/**
 * Raw payload as delivered by field hardware.
 *
 * `timeSteps` / `amplitudes` are declared as `(number | null)[]` rather than
 * `number[]` because real sensor streams contain dropped/corrupt samples.
 * JSON cannot represent NaN, so bad samples arrive as `null` (or as
 * non-finite values) and are removed by the sanitizer before streaming.
 */
export interface SensorPayload {
  sensorId: string;
  dataType: DataType;
  timeSteps: Array<number | null>;
  amplitudes: Array<number | null>;
  /** Fixed, non-curve metadata a method may need (e.g. station coordinates
   * for EARTHQUAKE_LOCATION). Only set by methods whose forward model needs
   * geometry beyond the timeSteps/amplitudes curve. */
  auxData?: Record<string, number[]>;
}

/** A cleaned, index-aligned time/amplitude series. */
export interface CleanSeries {
  time: number[];
  amplitude: number[];
}

/** The payload streamed over the WebSocket to the FastAPI agent backend. */
export interface AgentJobPayload {
  jobId: string;
  sensorId: string;
  dataType: DataType;
  data: CleanSeries;
  /** Free-text site context (driller's log / geological note), if recorded
   * via POST /context/:siteId for this sensorId. */
  siteNote?: string | null;
  auxData?: Record<string, number[]>;
}

/** Terminal status of an inversion run (mirrors the Python `InversionResult`). */
export type InversionStatus = 'converged' | 'max_iterations_reached' | 'error';

/** A geological interpretation produced by the Python Interpretation Agent
 * (mirrors Python's `InterpretationResult`). */
export interface InterpretationResult {
  siteId: string;
  summary: string;
  confidence: 'high' | 'medium' | 'low';
  flagged_anomaly: boolean;
  reasoning: string;
}

/** One of several distinct models whose misfit is nearly tied with the best
 * one found ("equivalence" — EM inversion is famously non-unique). */
export interface EquivalentModel {
  model: Record<string, unknown>;
  l2_norm_error: number;
}

/** The result streamed back from FastAPI (snake_case, as Pydantic serializes it). */
export interface InversionResult {
  jobId: string;
  status: InversionStatus;
  final_model: Record<string, unknown>;
  l2_norm_error: number | null;
  iterations: number;
  message?: string | null;
  predicted?: number[] | null;
  l2_history?: number[];
  equivalent_models?: EquivalentModel[];
  interpretation?: InterpretationResult | null;
}

/** Metadata Node keeps for an in-flight job so results can be enriched on return. */
export interface PendingJob {
  sensorId: string;
  dataType: DataType;
  samplesUsed: number;
  droppedCount: number;
  createdAt: number; // epoch ms
  observed: CleanSeries; // the sanitized data sent to the agent (for the UI)
}

/** A fully-enriched record ready to persist / alert on / show in the dashboard. */
export interface PersistedInversion {
  jobId: string;
  sensorId: string;
  dataType: DataType;
  status: string;
  l2NormError: number | null;
  iterations: number;
  finalModel: Record<string, unknown>;
  message: string | null;
  samplesUsed: number;
  droppedCount: number;
  createdAt: number; // epoch ms
  observed: CleanSeries | null;
  predicted: number[] | null;
  l2History: number[];
  equivalentModels: EquivalentModel[];
  interpretation: InterpretationResult | null;
}

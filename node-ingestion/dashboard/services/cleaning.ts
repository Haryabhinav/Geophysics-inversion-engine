import { http } from '@lib/http';
import type { CleaningResult } from '@types_/api';

/**
 * Sends RAW, unparsed file text to the Data Cleaning Agent
 * (`POST /clean/raw-data` -> python-agent's `POST /clean`). The result still
 * needs to be submitted through `ingestFieldData` (services/runs.ts) — this
 * call only produces a cleaned {timeSteps, amplitudes} pair, it doesn't
 * create a job.
 */
export async function cleanRawData(payload: {
  dataType: string;
  fileName: string;
  rawText: string;
}): Promise<CleaningResult> {
  const { data } = await http.post<CleaningResult>('/clean/raw-data', payload);
  return data;
}

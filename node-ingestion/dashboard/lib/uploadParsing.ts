/**
 * Client-side parsing for user-supplied field data (CSV / JSON / zip of
 * either). Runs entirely in the browser — nothing here talks to the network.
 * The output feeds POST /ingest/field-data unchanged (server.ts's
 * `sensorPayloadSchema`), so parsing only needs to produce
 * `{ timeSteps, amplitudes }`; sensorId/dataType are chosen in the UI.
 */
import JSZip from 'jszip';

export interface ParsedCurve {
  /** Filename this curve came from (zip member name, or the uploaded file's own name). */
  sourceName: string;
  timeSteps: (number | null)[];
  amplitudes: (number | null)[];
}

export interface ParseError {
  sourceName: string;
  message: string;
}

export interface ParseOutcome {
  curves: ParsedCurve[];
  errors: ParseError[];
}

const MAX_FILES = 200;
const MAX_ROWS_PER_FILE = 200_000;

/** Accepts a raw number token, `null`/empty (bad sample), or throws. */
function parseCell(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === '' || trimmed.toLowerCase() === 'null' || trimmed.toLowerCase() === 'nan') return null;
  const n = Number(trimmed);
  if (!Number.isFinite(n)) throw new Error(`"${trimmed}" is not a number`);
  return n;
}

/**
 * Two-column CSV: time,amplitude (optionally more columns — extras ignored).
 * A non-numeric first row is treated as a header and skipped. Supports `,`
 * or `;` as the delimiter (common in exported/regional data).
 */
export function parseCsv(text: string, sourceName: string): ParsedCurve {
  const lines = text.split(/\r\n|\r|\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) throw new Error('empty file');
  if (lines.length - 1 > MAX_ROWS_PER_FILE) {
    throw new Error(`too many rows (${lines.length - 1}) — over the ${MAX_ROWS_PER_FILE} limit`);
  }

  const delimiter = lines[0].includes(';') && !lines[0].includes(',') ? ';' : ',';
  let start = 0;
  const firstCells = lines[0].split(delimiter);
  if (firstCells.length < 2) throw new Error('expected at least 2 columns (time, amplitude)');
  // A header must have EVERY cell non-numeric, not just one. An `.every(...)`-
  // not-`.some(...)` check matters: a real first data row with one corrupted
  // cell (e.g. "1,abc") has ONE numeric cell, so it must NOT be treated as a
  // header — that would silently discard the whole row as "just labels"
  // instead of surfacing the bad cell as a parse error on that row.
  const looksLikeHeader = firstCells.every((cell) => !Number.isFinite(Number(cell.trim())) && cell.trim() !== '');
  if (looksLikeHeader) start = 1;

  const timeSteps: (number | null)[] = [];
  const amplitudes: (number | null)[] = [];
  for (let i = start; i < lines.length; i++) {
    const cells = lines[i].split(delimiter);
    if (cells.length < 2) throw new Error(`row ${i + 1}: expected 2+ columns, got ${cells.length}`);
    try {
      timeSteps.push(parseCell(cells[0]));
      amplitudes.push(parseCell(cells[1]));
    } catch (err) {
      throw new Error(`row ${i + 1}: ${(err as Error).message}`);
    }
  }
  return { sourceName, timeSteps, amplitudes };
}

/**
 * JSON shapes accepted:
 *   1. `{ timeSteps: [...], amplitudes: [...] }` (or the full ingest payload —
 *      sensorId/dataType fields are simply ignored, chosen in the UI instead)
 *   2. `[{ time, amplitude }, ...]` — an array of point objects
 *   3. `{ time: [...], amplitude: [...] }` — singular key names
 */
export function parseJson(text: string, sourceName: string): ParsedCurve {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (err) {
    throw new Error(`invalid JSON: ${(err as Error).message}`);
  }

  if (Array.isArray(data)) {
    const timeSteps: (number | null)[] = [];
    const amplitudes: (number | null)[] = [];
    for (const [i, row] of data.entries()) {
      if (typeof row !== 'object' || row === null) throw new Error(`row ${i}: not an object`);
      const r = row as Record<string, unknown>;
      const t = r.time ?? r.timeStep ?? r.t;
      const a = r.amplitude ?? r.value ?? r.d;
      timeSteps.push(typeof t === 'number' ? t : null);
      amplitudes.push(typeof a === 'number' ? a : null);
    }
    return { sourceName, timeSteps, amplitudes };
  }

  if (typeof data === 'object' && data !== null) {
    const r = data as Record<string, unknown>;
    const timeSteps = (r.timeSteps ?? r.time) as unknown;
    const amplitudes = (r.amplitudes ?? r.amplitude) as unknown;
    if (!Array.isArray(timeSteps) || !Array.isArray(amplitudes)) {
      throw new Error('expected "timeSteps"/"time" and "amplitudes"/"amplitude" arrays');
    }
    return {
      sourceName,
      timeSteps: timeSteps.map((v) => (typeof v === 'number' ? v : null)),
      amplitudes: amplitudes.map((v) => (typeof v === 'number' ? v : null)),
    };
  }

  throw new Error('expected a JSON object or array');
}

function parseByExtension(text: string, name: string): ParsedCurve {
  const lower = name.toLowerCase();
  if (lower.endsWith('.json')) return parseJson(text, name);
  if (lower.endsWith('.csv') || lower.endsWith('.txt')) return parseCsv(text, name);
  throw new Error('unsupported file type — use .csv, .txt, or .json');
}

/** Top-level entry point: a File that may itself be a .zip of many files. */
export async function parseUploadedFile(file: File): Promise<ParseOutcome> {
  const curves: ParsedCurve[] = [];
  const errors: ParseError[] = [];

  if (file.name.toLowerCase().endsWith('.zip')) {
    // Load from an ArrayBuffer, not the raw File: JSZip's Blob-input path
    // depends on runtime Blob-support detection that varies by environment,
    // while ArrayBuffer input is unambiguous everywhere.
    const zip = await JSZip.loadAsync(await file.arrayBuffer());
    const members = Object.values(zip.files).filter(
      (f) => !f.dir && /\.(csv|txt|json)$/i.test(f.name) && !f.name.startsWith('__MACOSX/'),
    );
    if (members.length === 0) throw new Error('zip contains no .csv/.txt/.json files');
    if (members.length > MAX_FILES) throw new Error(`zip has ${members.length} data files — over the ${MAX_FILES} limit`);

    for (const member of members) {
      try {
        const text = await member.async('text');
        curves.push(parseByExtension(text, member.name));
      } catch (err) {
        errors.push({ sourceName: member.name, message: (err as Error).message });
      }
    }
    return { curves, errors };
  }

  try {
    const text = await file.text();
    curves.push(parseByExtension(text, file.name));
  } catch (err) {
    errors.push({ sourceName: file.name, message: (err as Error).message });
  }
  return { curves, errors };
}

/** A sensorId derived from a filename: strip extension, keep it URL-safe. */
export function sensorIdFromFilename(name: string): string {
  const base = name
    .replace(/\.(csv|txt|json)$/i, '')
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return base.slice(0, 64) || 'uploaded';
}

import {
  CheckCircleFilled,
  CloseCircleFilled,
  InboxOutlined,
  RobotOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { Alert, App, Button, Card, Input, List, Progress, Switch, Tag, Tooltip, Typography, Upload } from 'antd';
import type { UploadProps } from 'antd';
import Link from 'next/link';
import { useState } from 'react';

import { EmptyState } from '@components/common/EmptyState';
import { PageHeader } from '@components/common/PageHeader';
import { CleaningReportCard } from '@components/upload/CleaningReportCard';
import { UploadMethodSelect } from '@components/upload/UploadMethodSelect';
import { BRAND, STATUS_COLOR } from '@lib/theme/tokens';
import {
  parseUploadedFile,
  sensorIdFromFilename,
  type ParseError,
  type ParsedCurve,
} from '@lib/uploadParsing';
import { cleanRawData } from '@services/cleaning';
import { ingestFieldData } from '@services/runs';
import type { CleaningResult } from '@types_/api';

type SubmissionState = 'pending' | 'submitting' | 'submitted' | 'failed';

interface Submission {
  sourceName: string;
  timeSteps: (number | null)[];
  amplitudes: (number | null)[];
  state: SubmissionState;
  jobId?: string;
  accepted?: number;
  dropped?: number;
  message?: string;
}

export default function UploadPage() {
  const { message: toast } = App.useApp();

  const [fileName, setFileName] = useState<string | null>(null);
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [isZip, setIsZip] = useState(false);
  const [curves, setCurves] = useState<ParsedCurve[]>([]);
  const [parseErrors, setParseErrors] = useState<ParseError[]>([]);
  const [parsing, setParsing] = useState(false);
  const [sensorId, setSensorId] = useState('');
  const [dataType, setDataType] = useState<string | null>(null);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // AI cleaning is opt-in, single-file-only (see UploadMethodSelect/
  // CleaningReportCard) — the Cleaning Agent has no offline fallback, so it
  // needs GEMINI_API_KEY configured server-side, and it's kept separate from
  // the always-available deterministic CSV/JSON/zip parser below.
  const [aiClean, setAiClean] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [cleaningResult, setCleaningResult] = useState<CleaningResult | null>(null);
  const [cleaningError, setCleaningError] = useState<string | null>(null);

  const resetForNewFile = () => {
    setCurves([]);
    setParseErrors([]);
    setSubmissions([]);
    setCleaningResult(null);
    setCleaningError(null);
  };

  const parseDeterministically = (file: File) => {
    setParsing(true);
    parseUploadedFile(file)
      .then((outcome) => {
        setCurves(outcome.curves);
        setParseErrors(outcome.errors);
        if (outcome.curves.length === 0) {
          toast.error('No usable curves found in that file.');
        }
      })
      .catch((err: Error) => {
        setParseErrors([{ sourceName: file.name, message: err.message }]);
        toast.error(err.message);
      })
      .finally(() => setParsing(false));
  };

  const handleFile: UploadProps['beforeUpload'] = (file) => {
    const zip = file.name.toLowerCase().endsWith('.zip');
    setFileName(file.name);
    setRawFile(file);
    setIsZip(zip);
    setSensorId(sensorIdFromFilename(file.name));
    resetForNewFile();

    if (aiClean && !zip) {
      // Defer parsing: the Cleaning Agent needs the target method (to know
      // what x/y quantities to expect) before it can do anything useful, and
      // that's chosen in the card below, not here.
      return false;
    }
    parseDeterministically(file);
    return false; // prevent antd's default XHR upload — we handle it ourselves
  };

  const runCleaning = async () => {
    if (!rawFile || !dataType) return;
    setCleaning(true);
    setCleaningError(null);
    try {
      const rawText = await rawFile.text();
      const result = await cleanRawData({ dataType, fileName: rawFile.name, rawText });
      setCleaningResult(result);
      setCurves([{ sourceName: rawFile.name, timeSteps: result.timeSteps, amplitudes: result.amplitudes }]);
    } catch (err) {
      setCleaningError((err as Error).message);
    } finally {
      setCleaning(false);
    }
  };

  const useStandardParsingInstead = () => {
    if (!rawFile) return;
    setAiClean(false);
    resetForNewFile();
    parseDeterministically(rawFile);
  };

  const canSubmit = curves.length > 0 && !!dataType && sensorId.trim().length > 0 && !submitting;
  const awaitingAiClean = aiClean && !isZip && curves.length === 0 && !cleaningError;

  const submit = async () => {
    if (!dataType) return;
    setSubmitting(true);
    const multi = curves.length > 1;
    const initial: Submission[] = curves.map((c) => ({
      sourceName: c.sourceName,
      timeSteps: c.timeSteps,
      amplitudes: c.amplitudes,
      state: 'pending',
    }));
    setSubmissions(initial);

    for (let i = 0; i < curves.length; i++) {
      const curve = curves[i];
      const thisSensorId = multi ? `${sensorId}-${sensorIdFromFilename(curve.sourceName)}` : sensorId;
      setSubmissions((prev) =>
        prev.map((s, idx) => (idx === i ? { ...s, state: 'submitting' } : s)),
      );
      try {
        const res = await ingestFieldData({
          sensorId: thisSensorId,
          dataType,
          timeSteps: curve.timeSteps,
          amplitudes: curve.amplitudes,
        });
        setSubmissions((prev) =>
          prev.map((s, idx) =>
            idx === i
              ? { ...s, state: 'submitted', jobId: res.jobId, accepted: res.accepted, dropped: res.dropped }
              : s,
          ),
        );
      } catch (err) {
        setSubmissions((prev) =>
          prev.map((s, idx) => (idx === i ? { ...s, state: 'failed', message: (err as Error).message } : s)),
        );
      }
    }
    setSubmitting(false);
  };

  const submittedCount = submissions.filter((s) => s.state === 'submitted').length;
  const failedCount = submissions.filter((s) => s.state === 'failed').length;

  return (
    <div>
      <PageHeader
        title="Upload Data"
        description="Submit your own field data — CSV, JSON, or a zip of either — through the real ingestion pipeline (POST /ingest/field-data), the same endpoint hardware uses."
      />

      <Alert
        className="mb-4"
        type="info"
        showIcon
        message="Expected shape"
        description={
          <span>
            <strong>CSV/TXT:</strong> two columns, <code>time,amplitude</code> (an optional header row
            is detected automatically). <strong>JSON:</strong>{' '}
            <code>{'{ "timeSteps": [...], "amplitudes": [...] }'}</code> or an array of{' '}
            <code>{'{ "time": ..., "amplitude": ... }'}</code> points. <strong>Zip:</strong> any mix of the
            above — each file becomes its own job. Bad/missing samples can be left blank or{' '}
            <code>null</code>; the server sanitizer drops them and reports how many.{' '}
            <strong>LITHOLOGY</strong> isn&apos;t supported here — it&apos;s a classification job, not a
            curve, and has no matching ingest route yet.
          </span>
        }
      />

      <Card size="small" className="shadow-card mb-4" style={{ borderRadius: 12 }}>
        <div className="mb-4 flex items-center justify-between gap-3 rounded-lg px-3 py-2" style={{ background: 'var(--page-bg)' }}>
          <div>
            <div className="flex items-center gap-2 text-sm font-medium">
              <RobotOutlined style={{ color: BRAND }} />
              Let AI clean this data
            </div>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Handles outlier spikes, unlabeled/misordered columns, baseline drift, and unit
              mismatches — the things the deterministic parser above can&apos;t judge. One file at a
              time; requires a Gemini key configured on the server.
            </div>
          </div>
          <Tooltip title={isZip ? "Not available for zip archives — each file inside will be parsed normally." : undefined}>
            <Switch checked={aiClean} disabled={isZip} onChange={setAiClean} />
          </Tooltip>
        </div>

        <Upload.Dragger
          accept=".csv,.txt,.json,.zip"
          multiple={false}
          showUploadList={false}
          beforeUpload={handleFile}
          disabled={parsing || cleaning}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">Click or drag a .csv, .json, or .zip file here</p>
          <p className="ant-upload-hint" style={{ color: 'var(--text-muted)' }}>
            {aiClean
              ? 'Read locally in your browser, then sent to the Cleaning Agent only once you pick a method below.'
              : 'Parsing happens entirely in your browser — nothing is sent until you submit.'}
          </p>
        </Upload.Dragger>

        {fileName && (
          <div className="mt-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
            {parsing ? (
              <span>Parsing {fileName}…</span>
            ) : awaitingAiClean ? (
              <span>
                <strong>{fileName}</strong> — ready for AI cleaning
              </span>
            ) : (
              <span>
                <strong>{fileName}</strong> — {curves.length} curve{curves.length === 1 ? '' : 's'} parsed
                {parseErrors.length > 0 && `, ${parseErrors.length} file(s) failed`}
              </span>
            )}
          </div>
        )}

        {aiClean && isZip && (
          <Alert
            className="mt-3"
            type="warning"
            showIcon
            message="AI cleaning isn't available for zip archives — this file was parsed with standard CSV/JSON parsing instead."
          />
        )}

        {parseErrors.length > 0 && (
          <List
            className="mt-2"
            size="small"
            dataSource={parseErrors}
            renderItem={(e) => (
              <List.Item>
                <CloseCircleFilled style={{ color: STATUS_COLOR.critical, marginRight: 8 }} />
                <code className="text-xs">{e.sourceName}</code>: {e.message}
              </List.Item>
            )}
          />
        )}
      </Card>

      {fileName && (curves.length > 0 || awaitingAiClean) && (
        <Card size="small" className="shadow-card mb-4" style={{ borderRadius: 12 }}>
          <div className="flex flex-col gap-4">
            <div>
              <Typography.Text strong>Method</Typography.Text>
              <div className="mt-1">
                <UploadMethodSelect value={dataType} onChange={setDataType} />
              </div>
            </div>
            <div>
              <Typography.Text strong>
                {curves.length > 1 ? 'Site id prefix' : 'Site id'}
              </Typography.Text>
              <Input
                className="mt-1"
                size="large"
                value={sensorId}
                onChange={(e) => setSensorId(e.target.value)}
                placeholder="e.g. field-site-1"
              />
              {curves.length > 1 && (
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  {curves.length} files → {curves.length} jobs, each site id suffixed with its filename.
                </div>
              )}
            </div>

            {cleaningError && (
              <Alert
                type="error"
                showIcon
                message="AI cleaning failed"
                description={cleaningError}
                action={
                  <Button size="small" onClick={useStandardParsingInstead}>
                    Use standard parsing instead
                  </Button>
                }
              />
            )}

            <div>
              {awaitingAiClean ? (
                <Button
                  type="primary"
                  size="large"
                  icon={<RobotOutlined />}
                  loading={cleaning}
                  disabled={!dataType}
                  onClick={runCleaning}
                >
                  {cleaning ? 'Cleaning…' : 'Clean with AI'}
                </Button>
              ) : (
                <Button
                  type="primary"
                  size="large"
                  icon={<UploadOutlined />}
                  loading={submitting}
                  disabled={!canSubmit}
                  onClick={submit}
                >
                  {submitting
                    ? 'Submitting…'
                    : `Submit ${curves.length} job${curves.length === 1 ? '' : 's'}`}
                </Button>
              )}
            </div>
          </div>
        </Card>
      )}

      {cleaningResult && (
        <div className="mb-4">
          <CleaningReportCard result={cleaningResult} />
          <div className="mt-2 flex justify-end">
            <Button type="link" size="small" onClick={useStandardParsingInstead}>
              Not right? Use standard parsing instead
            </Button>
          </div>
        </div>
      )}

      {submissions.length > 0 && (
        <Card
          size="small"
          className="shadow-card"
          style={{ borderRadius: 12 }}
          title="Submission status"
          extra={
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {submittedCount}/{submissions.length} submitted
              {failedCount > 0 && `, ${failedCount} failed`}
            </span>
          }
        >
          {submitting && (
            <Progress
              className="mb-3"
              percent={Math.round(((submittedCount + failedCount) / submissions.length) * 100)}
              showInfo={false}
            />
          )}
          <List
            size="small"
            dataSource={submissions}
            renderItem={(s) => (
              <List.Item>
                <div className="flex w-full items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {s.state === 'submitted' && <CheckCircleFilled style={{ color: STATUS_COLOR.good }} />}
                    {s.state === 'failed' && <CloseCircleFilled style={{ color: STATUS_COLOR.critical }} />}
                    <code className="text-xs">{s.sourceName}</code>
                    {s.state === 'submitted' && (
                      <Tag>
                        {s.accepted} accepted{s.dropped ? `, ${s.dropped} dropped` : ''}
                      </Tag>
                    )}
                    {s.state === 'failed' && (
                      <span className="text-xs" style={{ color: STATUS_COLOR.critical }}>
                        {s.message}
                      </span>
                    )}
                  </div>
                  {s.jobId && (
                    <Link href={`/runs?jobId=${encodeURIComponent(s.jobId)}`} className="text-xs" style={{ color: BRAND }}>
                      View run →
                    </Link>
                  )}
                </div>
              </List.Item>
            )}
          />
        </Card>
      )}

      {!fileName && (
        <EmptyState
          title="No file selected"
          description="Drop a CSV, JSON, or zip file above to get started."
        />
      )}
    </div>
  );
}

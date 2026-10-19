// Typer och anrop mot backendens REST-API (/api/*).

export type Severity = "error" | "warning";

export interface Issue {
  severity: Severity;
  code: string;
  message: string;
  count: number;
  examples: string[];
}

export interface ValidationReport {
  ok: boolean;
  bars: number;
  start: string | null;
  end: string | null;
  timeframe_minutes: number | null;
  duplicates_removed: number;
  sorted: boolean;
  gaps: number;
  largest_gap_hours: number;
  issues: Issue[];
}

export interface Dataset {
  id: number;
  name: string;
  source: string;
  sha256: string;
  synthetic: boolean;
  symbol: string;
  timeframe_minutes: number | null;
  bars: number;
  start: string;
  end: string;
  validation: ValidationReport;
  created_at: string;
}

export interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface BarsResponse {
  dataset_id: number;
  synthetic: boolean;
  bars_in_range: number;
  aggregated: boolean;
  bars: Bar[];
}

export type DataScope = "train" | "validation" | "test" | "full";

export interface Experiment {
  id: number;
  kind: string;
  name: string;
  status: string;
  dataset_id: number | null;
  data_hash: string | null;
  data_scope: DataScope;
  synthetic_data: boolean;
  code_version: string;
  params: Record<string, unknown>;
  seed: number | null;
  metrics: Record<string, unknown>;
  decision: "approved" | "rejected" | null;
  decision_reason: string | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface AuditEntry {
  id: number;
  ts: string;
  actor: string;
  action: string;
  details: Record<string, unknown>;
}

export interface SystemInfo {
  version: string;
  code_version: string;
  live_trading_enabled: boolean;
  milestone: string;
  max_upload_mb: number;
}

export interface IncomingFile {
  filename: string;
  size_bytes: number;
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public report?: ValidationReport) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`;
    throw new ApiError(detail, res.status, body.report ?? undefined);
  }
  return body as T;
}

const postJson = <T>(path: string, data: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

export interface ImportResult {
  dataset: Dataset;
  created: boolean;
}

export const api = {
  system: () => request<SystemInfo>("/system"),
  datasets: () => request<Dataset[]>("/datasets"),
  incoming: () => request<IncomingFile[]>("/datasets/incoming"),
  bars: (id: number, maxPoints = 2000) => request<BarsResponse>(`/datasets/${id}/bars?max_points=${maxPoints}`),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportResult>("/datasets/upload", { method: "POST", body: form });
  },
  importIncoming: (filename: string) => postJson<ImportResult>("/datasets/import", { filename }),
  synthetic: (n_bars: number, seed: number) => postJson<ImportResult>("/datasets/synthetic", { n_bars, seed }),
  experiments: () => request<Experiment[]>("/experiments"),
  audit: () => request<AuditEntry[]>("/audit"),
};

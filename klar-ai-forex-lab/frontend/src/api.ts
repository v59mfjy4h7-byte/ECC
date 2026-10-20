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

export interface ParamSpec {
  name: string;
  kind: "int" | "float";
  default: number;
  low: number;
  high: number;
  description: string;
}

export interface StrategyInfo {
  key: string;
  title: string;
  description: string;
  params: ParamSpec[];
}

export interface LabConfig {
  account: { starting_capital: number; currency: string; usd_to_account: number };
  costs: {
    spread_pips: number;
    slippage_pips: number;
    commission_usd_per_100k: number;
    swap_long_pips_per_night: number;
    swap_short_pips_per_night: number;
  };
  risk: Record<string, number>;
}

export interface ConfigResponse {
  config: LabConfig | null;
  status: { source: "default" | "signed" | "invalid"; signed_by?: string | null; signed_at?: string | null };
  error: string | null;
  ceilings: Record<string, number>;
  floors: Record<string, number>;
  kill_switch_active: boolean;
}

export interface BacktestMetrics {
  trades: number;
  low_sample: boolean;
  win_rate: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  expectancy: number | null;
  total_return: number | null;
  max_drawdown: number | null;
  profit_factor: number | null;
  sharpe: number | null;
  return_to_maxdd: number | null;
  est_costs: number | null;
  swap: number | null;
  net_pnl: number | null;
  halted: boolean;
  rejected_orders: number;
}

export interface Trade {
  direction: string;
  entry_time: string;
  exit_time: string;
  entry: number;
  exit: number;
  units: number;
  planned_risk: number;
  pnl: number;
  r_multiple: number;
  swap: number;
  exit_reason: string;
}

export interface OrderDecision {
  time: string;
  strategy: string;
  direction: string;
  approved: boolean;
  reason: string;
  units: number;
  planned_rr: number;
}

export interface EquityPoint {
  time: string;
  equity: number;
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
  strategies: () => request<StrategyInfo[]>("/strategies"),
  config: () => request<ConfigResponse>("/config"),
  runBaseline: (dataset_id: number) => postJson<Experiment[]>("/backtests", { dataset_id }),
  openTest: (dataset_id: number, key: string) =>
    postJson<Experiment[]>("/backtests", {
      dataset_id,
      strategies: [{ key }],
      periods: ["test"],
      confirm_test_access: true,
    }),
  testAccess: (dataset_id: number) => request<Record<string, boolean>>(`/backtests/test-access?dataset_id=${dataset_id}`),
  trades: (id: number) => request<Trade[]>(`/experiments/${id}/artifacts/trades`),
  decisions: (id: number) => request<OrderDecision[]>(`/experiments/${id}/artifacts/decisions`),
  equity: (id: number) => request<EquityPoint[]>(`/experiments/${id}/artifacts/equity`),
  setKillSwitch: (active: boolean) => postJson<{ kill_switch_active: boolean }>("/kill-switch", { active, confirm: !active }),
};

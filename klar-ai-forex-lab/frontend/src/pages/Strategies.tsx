import { useMemo, useState } from "react";
import { api, type BacktestMetrics, type DataScope, type Experiment } from "../api";
import { Card, ErrorBox, ScopeBadge } from "../components/Common";
import { EquityChart } from "../components/EquityChart";
import { METRIC_HEADERS, MetricCells } from "../components/Metrics";
import { useLab } from "../context";
import { useAsync } from "../hooks";

const PERIODS: DataScope[] = ["train", "validation", "test"];

/** Senaste körningen per (strategi, konfiguration, period) för datasetet. */
function latestRuns(exps: Experiment[], datasetId: number) {
  const seen = new Map<string, Experiment>();
  for (const e of exps) {
    if (e.kind !== "backtest" || e.dataset_id !== datasetId || e.status !== "finished") continue;
    const key = `${e.params.strategy}|${e.params.config_hash}|${e.data_scope}`;
    if (!seen.has(key)) seen.set(key, e); // listan är sorterad nyast först
  }
  return [...seen.values()];
}

export default function Strategies() {
  const { active, dark } = useLab();
  const strategies = useAsync(api.strategies);
  const exps = useAsync(api.experiments);
  const access = useAsync(() => (active ? api.testAccess(active.id) : Promise.resolve({} as Record<string, boolean>)), [active?.id]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Experiment | null>(null);

  const runs = useMemo(() => (active && exps.data ? latestRuns(exps.data, active.id) : []), [exps.data, active]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      exps.reload();
      access.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function openTest(key: string) {
    if (!active) return;
    const ok = window.confirm(
      `Öppna den låsta testperioden för ${key}?\n\nDet kan bara göras EN gång per strategikonfiguration och dataset. ` +
        "Strategin får inte justeras efteråt utifrån testresultatet. Öppningen loggas.",
    );
    if (ok) act(() => api.openTest(active.id, key));
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Strategier</h1>
      {!active && <ErrorBox message="Välj eller importera ett dataset under Marknad & data först." />}
      {error && <ErrorBox message={error} />}

      <Card
        title="Agent A–D"
        right={
          active && (
            <button className="btn" disabled={busy} onClick={() => act(() => api.runBaseline(active.id))}>
              {busy ? "Kör…" : "Kör backtest (träning + validering)"}
            </button>
          )
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          {strategies.data?.map((s) => (
            <div key={s.key} className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
              <div className="font-medium">{s.title}</div>
              <p className="text-slate-600 dark:text-slate-400">{s.description}</p>
              <p className="mt-1 font-mono text-xs text-slate-500 dark:text-slate-400">
                {s.params.map((p) => `${p.name}=${p.default}`).join(" · ")}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
          Standardparametrar från prototypen; inga parametrar är optimerade. Alla belopp är netto efter spread, slippage, provision och swap.
        </p>
      </Card>

      {PERIODS.map((period) => {
        const rows = runs.filter((r) => r.data_scope === period);
        if (period !== "test" && rows.length === 0) return null;
        return (
          <Card key={period} title={`Resultat – ${period === "train" ? "träning" : period === "validation" ? "validering" : "test"}`} right={<ScopeBadge scope={period} />}>
            {active?.synthetic && <p className="mb-2 text-xs font-semibold text-amber-700 dark:text-amber-400">Syntetisk testdata – inte verkliga resultat.</p>}
            {period === "test" && (
              <div className="mb-3 space-y-2 text-sm">
                <p className="text-slate-600 dark:text-slate-400">
                  Testperioden är låst. Öppna den bara för en färdig kandidat – en gång per konfiguration. M3 lägger till befordringstrappan som avgör när det är motiverat.
                </p>
                <div className="flex flex-wrap gap-2">
                  {strategies.data?.map((s) => (
                    <button key={s.key} className="btn-secondary" disabled={busy || !active || access.data?.[s.key]} onClick={() => openTest(s.key)}>
                      {access.data?.[s.key] ? `${s.key}: redan öppnad` : `Öppna test: ${s.key}`}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {rows.length > 0 && (
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Strategi</th>
                      {METRIC_HEADERS.map((h) => <th key={h}>{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((e) => (
                      <tr key={e.id} onClick={() => setSelected(e)} className={`cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 ${selected?.id === e.id ? "bg-sky-50 dark:bg-sky-950/40" : ""}`}>
                        <td className="whitespace-nowrap">{String(e.params.strategy)}</td>
                        <MetricCells m={e.metrics as unknown as BacktestMetrics} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        );
      })}

      {runs.length > 0 && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          ⚠ = färre än 30 affärer (för svagt underlag). ■ = kontot stoppat vid 20 % nedgång. Förväntat/affär &gt; 0 och profit factor &gt; 1 i alla perioder är ett minimikrav, inte ett bevis.
          Fler testade konfigurationer ökar risken att något ser lönsamt ut av slump.
        </p>
      )}

      {selected && <RunDetail exp={selected} dark={dark} />}
    </div>
  );
}

function RunDetail({ exp, dark }: { exp: Experiment; dark: boolean }) {
  const equity = useAsync(() => api.equity(exp.id), [exp.id]);
  const trades = useAsync(() => api.trades(exp.id), [exp.id]);
  const decisions = useAsync(() => api.decisions(exp.id), [exp.id]);

  const rejected = useMemo(() => {
    const counts = new Map<string, number>();
    for (const d of decisions.data ?? []) if (!d.approved) counts.set(d.reason, (counts.get(d.reason) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [decisions.data]);

  return (
    <Card title={`${String(exp.params.strategy)} – experiment #${exp.id}`} right={<ScopeBadge scope={exp.data_scope} />}>
      {equity.data && equity.data.length > 0 && <EquityChart points={equity.data} dark={dark} />}
      <div className="mt-3 grid gap-4 lg:grid-cols-3">
        <div className="text-sm">
          <div className="mb-1 font-medium">Avvisade order (riskmotorn)</div>
          {rejected.length === 0 ? (
            <p className="text-slate-500 dark:text-slate-400">Inga.</p>
          ) : (
            <ul>{rejected.map(([reason, n]) => <li key={reason} className="font-mono text-xs">{reason}: {n}</li>)}</ul>
          )}
          <div className="mt-3 break-all font-mono text-xs text-slate-500 dark:text-slate-400">
            config {String(exp.params.config_hash)} · data {exp.data_hash?.slice(0, 12)} · kod {exp.code_version}
          </div>
        </div>
        <div className="overflow-x-auto lg:col-span-2">
          <div className="mb-1 text-sm font-medium">Affärer {trades.data && `(${trades.data.length}, senaste 50 visas)`}</div>
          <table className="table text-xs">
            <thead>
              <tr><th>In (UTC)</th><th>Riktning</th><th>Enheter</th><th>Utfall</th><th>R</th><th>Swap</th><th>Orsak</th></tr>
            </thead>
            <tbody>
              {trades.data?.slice(-50).reverse().map((t) => (
                <tr key={t.entry_time}>
                  <td className="whitespace-nowrap">{t.entry_time.replace("T", " ").slice(0, 16)}</td>
                  <td>{t.direction}</td>
                  <td className="tabular-nums">{t.units}</td>
                  <td className={`tabular-nums ${t.pnl >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}`}>{t.pnl.toFixed(0)}</td>
                  <td className="tabular-nums">{t.r_multiple.toFixed(2)}</td>
                  <td className="tabular-nums">{t.swap.toFixed(1)}</td>
                  <td>{t.exit_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}

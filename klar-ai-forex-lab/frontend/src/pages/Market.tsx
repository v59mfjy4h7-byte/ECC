import { useState } from "react";
import { ApiError, api, type ValidationReport } from "../api";
import { Card, ErrorBox, ScopeBadge, fmtDate, fmtInt } from "../components/Common";
import { PriceChart } from "../components/PriceChart";
import { ValidationView } from "../components/ValidationView";
import { useLab } from "../context";
import { useAsync } from "../hooks";

export default function Market() {
  const { active, datasets, setActiveId, reloadDatasets, dark } = useLab();
  const bars = useAsync(() => (active ? api.bars(active.id) : Promise.resolve(null)), [active?.id]);
  const incoming = useAsync(api.incoming);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<{ message: string; report?: ValidationReport } | null>(null);
  const [seed, setSeed] = useState(42);
  const [nBars, setNBars] = useState(30000);

  async function run(action: () => Promise<{ dataset: { id: number; name: string }; created: boolean }>) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const res = await action();
      setMessage(res.created ? `Importerat: ${res.dataset.name}` : `Samma data fanns redan (dataset #${res.dataset.id}).`);
      setActiveId(res.dataset.id);
      reloadDatasets();
    } catch (e) {
      const err = e as ApiError;
      setError({ message: err.message, report: err.report });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Marknad & data</h1>

      <Card title="EUR/USD" right={<ScopeBadge scope="full" />}>
        {!active && <p className="text-sm">Inget dataset valt.</p>}
        {bars.error && <ErrorBox message={bars.error} />}
        {bars.data && (
          <>
            <PriceChart bars={bars.data.bars} dark={dark} />
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              {fmtInt(bars.data.bars_in_range)} staplar
              {bars.data.aggregated && `, visas sammanslagna till ${fmtInt(bars.data.bars.length)} ljus (OHLC bevaras)`}. Signaler, affärer och regim visas från M2/M4.
            </p>
          </>
        )}
      </Card>

      <Card title="Dataset">
        {datasets.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">Inga dataset ännu.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr><th>#</th><th>Namn</th><th>Typ</th><th>Staplar</th><th>Period</th><th>SHA-256</th><th /></tr>
              </thead>
              <tbody>
                {datasets.map((d) => (
                  <tr key={d.id} className={d.id === active?.id ? "bg-sky-50 dark:bg-sky-950/40" : ""}>
                    <td>{d.id}</td>
                    <td>{d.name}</td>
                    <td>{d.synthetic ? <span className="font-semibold text-amber-700 dark:text-amber-400">Syntetisk</span> : "Importerad"}</td>
                    <td className="tabular-nums">{fmtInt(d.bars)}</td>
                    <td className="whitespace-nowrap">{fmtDate(d.start)} → {fmtDate(d.end)}</td>
                    <td className="font-mono text-xs">{d.sha256.slice(0, 12)}…</td>
                    <td>{d.id !== active?.id && <button className="btn-secondary" onClick={() => setActiveId(d.id)}>Visa</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {active && (
        <Card title={`Valideringsrapport: ${active.name}`}>
          <ValidationView report={active.validation} />
        </Card>
      )}

      <Card title="Importera data">
        <div className="space-y-4 text-sm">
          <div>
            <p className="mb-1 font-medium">Ladda upp CSV</p>
            <p className="mb-2 text-slate-500 dark:text-slate-400">Kolumner time,open,high,low,close (UTC) eller MT4/MT5-export med Date/Time. H1 rekommenderas.</p>
            <input type="file" accept=".csv,text/csv" disabled={busy}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) run(() => api.upload(f)); e.target.value = ""; }} />
          </div>
          <div>
            <p className="mb-1 font-medium">Från mappen data/incoming/</p>
            {incoming.data && incoming.data.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {incoming.data.map((f) => (
                  <button key={f.filename} className="btn-secondary" disabled={busy} onClick={() => run(() => api.importIncoming(f.filename))}>
                    {f.filename} ({(f.size_bytes / 1e6).toFixed(1)} MB)
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-slate-500 dark:text-slate-400">Inga CSV-filer i data/incoming/.</p>
            )}
          </div>
          <div>
            <p className="mb-1 font-medium">Syntetisk testdata</p>
            <p className="mb-2 text-slate-500 dark:text-slate-400">Endast för att prova systemet. Märks tydligt överallt.</p>
            <div className="flex flex-wrap items-center gap-2">
              <label>Staplar <input className="input w-24" type="number" min={1000} max={200000} value={nBars} onChange={(e) => setNBars(Number(e.target.value))} /></label>
              <label>Seed <input className="input w-20" type="number" min={0} value={seed} onChange={(e) => setSeed(Number(e.target.value))} /></label>
              <button className="btn" disabled={busy} onClick={() => run(() => api.synthetic(nBars, seed))}>Skapa</button>
            </div>
          </div>
          {busy && <p>Validerar…</p>}
          {message && <p className="text-emerald-700 dark:text-emerald-400">{message}</p>}
          {error && (
            <div className="space-y-2">
              <ErrorBox message={`Avvisad: ${error.message}`} />
              {error.report && <ValidationView report={error.report} />}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

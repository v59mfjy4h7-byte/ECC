import { api } from "../api";
import { Card, ErrorBox, ScopeBadge, fmtDate } from "../components/Common";
import { useAsync } from "../hooks";

export default function Research() {
  const exps = useAsync(api.experiments);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Forskning</h1>
      <Card title="Experimentregister" right={<button className="btn-secondary" onClick={exps.reload}>Uppdatera</button>}>
        <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
          Varje experiment sparar data-hash, kodversion, parametrar, slumpfrö, mått och beslut. Avslutade experiment kan inte ändras.
          Optuna, walk-forward och robusthetstester kommer i M3.
        </p>
        {exps.error && <ErrorBox message={exps.error} />}
        {exps.data && exps.data.length === 0 && <p className="text-sm">Inga experiment ännu.</p>}
        {exps.data && exps.data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr><th>#</th><th>Typ</th><th>Namn</th><th>Period</th><th>Status</th><th>Beslut</th><th>Data-hash</th><th>Kodversion</th><th>Tid</th></tr>
              </thead>
              <tbody>
                {exps.data.map((e) => (
                  <tr key={e.id}>
                    <td>{e.id}</td>
                    <td>{e.kind}</td>
                    <td>{e.name}{e.synthetic_data && <span className="ml-1 text-xs font-semibold text-amber-700 dark:text-amber-400">(syntetisk)</span>}</td>
                    <td><ScopeBadge scope={e.data_scope} /></td>
                    <td>{e.status}</td>
                    <td title={e.decision_reason ?? ""}>
                      {e.decision ? (e.decision === "approved" ? "Godkänd" : "Avvisad") : "–"}
                      {e.decision_reason && <span className="block text-xs text-slate-500 dark:text-slate-400">{e.decision_reason}</span>}
                    </td>
                    <td className="font-mono text-xs">{e.data_hash ? `${e.data_hash.slice(0, 12)}…` : "–"}</td>
                    <td className="font-mono text-xs">{e.code_version}</td>
                    <td className="whitespace-nowrap">{fmtDate(e.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

import { api } from "../api";
import { Card, ErrorBox, fmtDate } from "../components/Common";
import { KillSwitch } from "../components/KillSwitch";
import { useAsync } from "../hooks";

export default function Audit() {
  const log = useAsync(api.audit);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Risk & logg</h1>
      <Card title="Nödstopp">
        <KillSwitch />
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Samma effekt som att skapa filen <code>data/STOP</code>. Avvisade order per körning visas under Strategier.</p>
      </Card>
      <Card title="Revisionslogg" right={<button className="btn-secondary" onClick={log.reload}>Uppdatera</button>}>
        <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
          Loggen kan bara utökas, aldrig ändras.
        </p>
        {log.error && <ErrorBox message={log.error} />}
        {log.data && log.data.length === 0 && <p className="text-sm">Loggen är tom.</p>}
        {log.data && log.data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Tid (UTC)</th><th>Aktör</th><th>Händelse</th><th>Detaljer</th></tr></thead>
              <tbody>
                {log.data.map((a) => (
                  <tr key={a.id}>
                    <td className="whitespace-nowrap">{fmtDate(a.ts)}</td>
                    <td>{a.actor}</td>
                    <td>{a.action}</td>
                    <td className="break-all font-mono text-xs">{JSON.stringify(a.details)}</td>
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

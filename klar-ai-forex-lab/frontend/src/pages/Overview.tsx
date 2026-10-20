import { Link } from "react-router-dom";
import { api } from "../api";
import { KillSwitch } from "../components/KillSwitch";
import { Card, ErrorBox, ScopeBadge, Stat, fmtDate, fmtInt } from "../components/Common";
import { useLab } from "../context";
import { useAsync } from "../hooks";

export default function Overview() {
  const { active, datasets } = useLab();
  const sys = useAsync(api.system);
  const exps = useAsync(api.experiments);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Översikt</h1>
      <Card title="System">
        {sys.error && <ErrorBox message={sys.error} />}
        {sys.data && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Livehandel" value={sys.data.live_trading_enabled ? "PÅ (fel!)" : "Avstängd"} hint="Hårdkodad, verifieras av test" />
            <Stat label="Milstolpe" value={sys.data.milestone} />
            <Stat label="Version" value={sys.data.version} />
            <Stat label="Kodversion" value={<span className="break-all text-sm">{sys.data.code_version}</span>} />
          </div>
        )}
      </Card>
      <Card title="Aktivt dataset" right={active && <ScopeBadge scope="full" />}>
        {active ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Namn" value={<span className="text-sm">{active.name}</span>} hint={active.synthetic ? "Syntetisk testdata" : "Importerad data"} />
            <Stat label="Staplar" value={fmtInt(active.bars)} hint={`${active.timeframe_minutes ?? "?"} min/stapel`} />
            <Stat label="Period" value={<span className="text-sm">{fmtDate(active.start)} → {fmtDate(active.end)}</span>} />
            <Stat label="Validering" value={active.validation.ok ? "Godkänd" : "Underkänd"} hint={`${active.validation.issues.length} anmärkningar`} />
          </div>
        ) : (
          <p className="text-sm">
            Inget dataset laddat. Gå till <Link className="text-sky-700 underline dark:text-sky-400" to="/marknad">Marknad & data</Link> för att importera EUR/USD-data eller skapa märkt testdata.
          </p>
        )}
        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">{datasets.length} dataset totalt.</p>
      </Card>
      <Card title="Risk">
        <KillSwitch />
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
          Gränser: 1 % risk per affär, netto-RR ≥ 2, 3 % daglig förlustgräns, permanent stopp vid 20 % nedgång (se Inställningar).
          Virtuellt paper-konto med equity och öppen position kommer i M5.
        </p>
      </Card>
      <Card title="Senaste experiment">
        {exps.data && exps.data.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {exps.data.slice(0, 5).map((e) => (
              <li key={e.id}>
                #{e.id} {e.name} – {e.status}
                {e.decision && ` (${e.decision === "approved" ? "godkänd" : "avvisad"})`}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">Inga experiment ännu.</p>
        )}
      </Card>
    </div>
  );
}

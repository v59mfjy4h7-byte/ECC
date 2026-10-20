import { api } from "../api";
import { Card, ErrorBox } from "../components/Common";
import { useAsync } from "../hooks";

const LABELS: Record<string, string> = {
  starting_capital: "Startkapital", currency: "Valuta", usd_to_account: "Växelkurs (konto per USD)",
  spread_pips: "Spread (pips)", slippage_pips: "Slippage (pips/order)", commission_usd_per_100k: "Provision (USD/100k, round-turn)",
  swap_long_pips_per_night: "Swap long (pips/natt, kostnad)", swap_short_pips_per_night: "Swap short (pips/natt, kostnad)",
  risk_per_trade: "Risk per affär", min_reward_risk: "Min netto-RR", max_daily_loss: "Daglig förlustgräns",
  max_drawdown: "Max nedgång (permanent stopp)", max_leverage: "Max hävstång (exponering)", max_open_positions: "Max öppna positioner",
  min_stop_pips: "Min stop (pips)", max_stop_pips: "Max stop (pips)", lot_step: "Lotsteg (enheter)", min_units: "Min storlek (enheter)",
  max_bar_gap_hours: "Föråldrad data efter (h)", price_min: "Lägsta rimliga pris", price_max: "Högsta rimliga pris",
};

export default function Settings() {
  const cfg = useAsync(api.config);
  const data = cfg.data;
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Inställningar</h1>
      {cfg.error && <ErrorBox message={cfg.error} />}
      {data?.error && <ErrorBox message={`Riskkonfigurationen är ogiltig – backtester är spärrade: ${data.error}`} />}
      {data && (
        <Card title="Kostnader, konto och riskgränser">
          <p className="mb-3 text-sm">
            Källa:{" "}
            <strong>
              {data.status.source === "signed" ? `signerad fil (av ${data.status.signed_by ?? "?"}, ${data.status.signed_at ?? "?"})` : data.status.source === "default" ? "standardvärden" : "ogiltig"}
            </strong>
            . Värdena kan inte ändras här: riskgränser ändras bara av en människa via signerad konfiguration, aldrig av AI eller UI.
          </p>
          {data.config && (
            <div className="grid gap-4 md:grid-cols-3">
              {(["account", "costs", "risk"] as const).map((section) => (
                <div key={section}>
                  <div className="mb-1 text-sm font-medium">{section === "account" ? "Konto" : section === "costs" ? "Kostnader (antaganden)" : "Risk"}</div>
                  <table className="table text-xs">
                    <tbody>
                      {Object.entries(data.config![section]).map(([k, v]) => (
                        <tr key={k}>
                          <td>{LABELS[k] ?? k}</td>
                          <td className="text-right tabular-nums">
                            {String(v)}
                            {k in data.ceilings && <span className="ml-1 text-slate-500" title="Specifikationens tak">(≤ {data.ceilings[k]})</span>}
                            {k in data.floors && <span className="ml-1 text-slate-500" title="Specifikationens golv">(≥ {data.floors[k]})</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
      <Card title="Så ändras gränserna">
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>Sätt en hemlig nyckel (minst 16 tecken) i <code>.env</code>: <code>KLAR_RISK_SIGNING_KEY=…</code></li>
          <li>Skriv en JSON med de värden som ska ändras, t.ex. <code>{'{"risk": {"risk_per_trade": 0.005}}'}</code></li>
          <li>Signera i <code>backend/</code>: <code>python -m klar_lab.risk.signing min.json --by "Namn"</code></li>
          <li>Starta om backend. Ändringen syns här och sparas i varje experiment.</li>
        </ol>
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          Även en signerad fil får bara skärpa specifikationens gränser (1 % risk, netto-RR ≥ 2, 3 % daglig förlust, 20 % nedgång, hävstång ≤ 10). En ändrad fil utan giltig signatur spärrar alla backtester.
        </p>
      </Card>
    </div>
  );
}

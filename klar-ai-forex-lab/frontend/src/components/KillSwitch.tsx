import { useState } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import { ErrorBox } from "./Common";

/** Nödstopp: aktivering sker direkt, avaktivering kräver bekräftelse. */
export function KillSwitch() {
  const cfg = useAsync(api.config);
  const [error, setError] = useState<string | null>(null);
  const active = cfg.data?.kill_switch_active ?? false;

  async function toggle() {
    if (active && !window.confirm("Avaktivera kill switch? Nya affärer tillåts igen (inom riskgränserna).")) return;
    try {
      await api.setKillSwitch(!active);
      cfg.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className={`rounded px-2 py-1 text-sm font-semibold ${active ? "bg-rose-600 text-white" : "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/50 dark:text-emerald-100"}`}>
        Kill switch: {active ? "AKTIV – inga nya affärer" : "av"}
      </span>
      <button className={active ? "btn-secondary" : "rounded-lg bg-rose-600 px-3 py-2 text-sm font-medium text-white hover:bg-rose-700"} onClick={toggle} disabled={cfg.loading}>
        {active ? "Avaktivera" : "STOPPA all ny handel"}
      </button>
      {error && <ErrorBox message={error} />}
    </div>
  );
}

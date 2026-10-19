import { useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { ErrorBox, SyntheticBanner } from "./components/Common";
import { Lab } from "./context";
import { readStored, useAsync, writeStored } from "./hooks";
import Audit from "./pages/Audit";
import Market from "./pages/Market";
import Overview from "./pages/Overview";
import Placeholder from "./pages/Placeholder";
import Research from "./pages/Research";

const NAV = [
  { to: "/", label: "Översikt" },
  { to: "/marknad", label: "Marknad & data" },
  { to: "/strategier", label: "Strategier" },
  { to: "/forskning", label: "Forskning" },
  { to: "/paper", label: "Paper trading" },
  { to: "/risk", label: "Risk & logg" },
  { to: "/installningar", label: "Inställningar" },
];

function initialDark(): boolean {
  const stored = readStored("klar-theme");
  if (stored) return stored === "dark";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export default function App() {
  const [dark, setDark] = useState(initialDark);
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeId, setActiveIdState] = useState<number | null>(() => Number(readStored("klar-dataset")) || null);
  const ds = useAsync(api.datasets);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    writeStored("klar-theme", dark ? "dark" : "light");
  }, [dark]);

  const datasets = ds.data ?? [];
  const active = datasets.find((d) => d.id === activeId) ?? datasets[0] ?? null;
  const ctx = useMemo(
    () => ({
      dark,
      datasets,
      active,
      setActiveId: (id: number) => {
        setActiveIdState(id);
        writeStored("klar-dataset", String(id));
      },
      reloadDatasets: ds.reload,
    }),
    [dark, datasets, active, ds.reload],
  );

  return (
    <Lab.Provider value={ctx}>
      <div className="min-h-screen md:flex">
        <aside className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 md:w-56 md:shrink-0 md:border-b-0 md:border-r">
          <div className="flex items-center justify-between px-4 py-3">
            <div>
              <div className="font-semibold">Klar AI Forex Lab</div>
              <div className="text-xs text-slate-500 dark:text-slate-400">EUR/USD · låtsaspengar</div>
            </div>
            <button className="btn-secondary md:hidden" onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen}>
              Meny
            </button>
          </div>
          <nav className={`${menuOpen ? "block" : "hidden"} px-2 pb-3 md:block`}>
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  `block rounded-lg px-3 py-2 text-sm ${
                    isActive ? "bg-sky-100 font-medium text-sky-900 dark:bg-sky-900/50 dark:text-sky-100" : "hover:bg-slate-100 dark:hover:bg-slate-800"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
            <button className="btn-secondary mt-3 w-full" onClick={() => setDark(!dark)}>
              {dark ? "Ljust läge" : "Mörkt läge"}
            </button>
          </nav>
        </aside>
        <main className="min-w-0 flex-1 space-y-4 p-4 md:p-6">
          <div className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs text-slate-100 dark:bg-slate-800">
            Simulering: ingen livehandel finns i systemet. Historiska resultat garanterar inte framtida resultat.
          </div>
          {active?.synthetic && <SyntheticBanner />}
          {ds.error && <ErrorBox message={`Kunde inte nå backend: ${ds.error}`} />}
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/marknad" element={<Market />} />
            <Route path="/strategier" element={<Placeholder title="Strategier" milestone="M2" text="Agent A–D (trend, momentum, mean reversion, breakout) portas från prototypen tillsammans med backtest- och riskmotorn." />} />
            <Route path="/forskning" element={<Research />} />
            <Route path="/paper" element={<Placeholder title="Paper trading" milestone="M5" text="Virtuellt konto mot live-data med samma risk- och kostnadsmodell som backtest, inklusive drift-övervakning." />} />
            <Route path="/risk" element={<Audit />} />
            <Route path="/installningar" element={<Placeholder title="Inställningar" milestone="M2" text="Kostnader, kapital och riskgränser. Ändringar av riskgränser kräver signerad konfiguration av en människa och loggas." />} />
            <Route path="*" element={<Placeholder title="Sidan finns inte" text="Välj en sida i menyn." />} />
          </Routes>
        </main>
      </div>
    </Lab.Provider>
  );
}

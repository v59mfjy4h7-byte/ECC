import type { ReactNode } from "react";
import type { DataScope } from "../api";

export function SyntheticBanner() {
  return (
    <div role="alert" className="rounded-lg border border-amber-400 bg-amber-100 px-3 py-2 text-sm font-medium text-amber-900 dark:border-amber-500/60 dark:bg-amber-900/40 dark:text-amber-100">
      SYNTETISK TESTDATA – påhittad data. Resultat på den säger ingenting om verklig lönsamhet.
    </div>
  );
}

const SCOPE_LABEL: Record<DataScope, string> = {
  train: "In-sample (träning)",
  validation: "Validering",
  test: "Test (låst period)",
  full: "Hela datasetet (ej uppdelat)",
};

const SCOPE_STYLE: Record<DataScope, string> = {
  train: "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100",
  validation: "bg-violet-200 text-violet-900 dark:bg-violet-900/60 dark:text-violet-100",
  test: "bg-rose-200 text-rose-900 dark:bg-rose-900/60 dark:text-rose-100",
  full: "bg-sky-100 text-sky-900 dark:bg-sky-900/50 dark:text-sky-100",
};

/** Visar vilken dataperiod en graf eller tabell bygger på. */
export function ScopeBadge({ scope }: { scope: DataScope }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${SCOPE_STYLE[scope]}`}>{SCOPE_LABEL[scope]}</span>;
}

export function Card({ title, right, children }: { title?: string; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || right) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-900 dark:border-rose-700 dark:bg-rose-950/50 dark:text-rose-100">
      {message}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      {hint && <div className="text-xs text-slate-500 dark:text-slate-400">{hint}</div>}
    </div>
  );
}

export const fmtDate = (iso: string) => iso.replace("T", " ").slice(0, 16);
export const fmtInt = (n: number) => n.toLocaleString("sv-SE");

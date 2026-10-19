import type { ValidationReport } from "../api";
import { fmtInt } from "./Common";

export function ValidationView({ report }: { report: ValidationReport }) {
  return (
    <div className="space-y-2 text-sm">
      <p>
        <span className={report.ok ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}>
          {report.ok ? "Godkänd" : "Underkänd"}
        </span>{" "}
        · {fmtInt(report.bars)} staplar · tidsram {report.timeframe_minutes ?? "?"} min · {report.gaps} luckor utöver helger
        {report.largest_gap_hours > 0 && ` (största ${report.largest_gap_hours} h)`} · {report.duplicates_removed} dubbletter borttagna
      </p>
      {report.issues.length === 0 ? (
        <p className="text-slate-500 dark:text-slate-400">Inga anmärkningar.</p>
      ) : (
        <ul className="space-y-1">
          {report.issues.map((i) => (
            <li key={i.code} className="flex gap-2">
              <span
                className={`shrink-0 rounded px-1.5 text-xs font-semibold uppercase ${
                  i.severity === "error"
                    ? "bg-rose-200 text-rose-900 dark:bg-rose-900 dark:text-rose-100"
                    : "bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100"
                }`}
              >
                {i.severity === "error" ? "fel" : "varning"}
              </span>
              <span>
                {i.message}
                {i.count > 0 && ` (${fmtInt(i.count)})`}
                {i.examples.length > 0 && (
                  <span className="block text-xs text-slate-500 dark:text-slate-400">t.ex. {i.examples.join(", ")}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

import type { BacktestMetrics } from "../api";

const num = (x: number | null | undefined, digits = 0) => (x == null ? "n/a" : x.toLocaleString("sv-SE", { maximumFractionDigits: digits, minimumFractionDigits: digits }));
const pct = (x: number | null | undefined) => (x == null ? "n/a" : `${num(x * 100, 1)} %`);

const tone = (x: number | null | undefined) =>
  x == null ? "" : x > 0 ? "text-emerald-700 dark:text-emerald-400" : x < 0 ? "text-rose-700 dark:text-rose-400" : "";

export const METRIC_HEADERS = ["Affärer", "Vinst%", "Förväntat/affär", "Avkastning", "Max DD", "Profit factor", "Sharpe", "Kostnader", "Avvisade"];

/** Celler för en resultatrad. Alla belopp i kontovaluta, netto efter kostnader. */
export function MetricCells({ m }: { m: BacktestMetrics }) {
  return (
    <>
      <td className="tabular-nums">
        {m.trades}
        {m.low_sample && <span title="Färre än 30 affärer – för svagt underlag" className="ml-1 text-amber-600">⚠</span>}
      </td>
      <td className="tabular-nums">{pct(m.win_rate)}</td>
      <td className={`tabular-nums ${tone(m.expectancy)}`}>{num(m.expectancy, 1)}</td>
      <td className={`tabular-nums ${tone(m.total_return)}`}>{pct(m.total_return)}</td>
      <td className="tabular-nums">{pct(m.max_drawdown)}</td>
      <td className="tabular-nums">{num(m.profit_factor, 2)}</td>
      <td className="tabular-nums">{num(m.sharpe, 2)}</td>
      <td className="tabular-nums">{num(m.est_costs)}</td>
      <td className="tabular-nums">{m.rejected_orders}{m.halted && <span className="ml-1 text-rose-600" title="Kontot stoppades vid max nedgång">■</span>}</td>
    </>
  );
}

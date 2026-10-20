import { createChart, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { EquityPoint } from "../api";

/** Kontots värde över tid (mark-to-market, netto efter kostnader). */
export function EquityChart({ points, dark }: { points: EquityPoint[]; dark: boolean }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: dark ? "#cbd5e1" : "#334155" },
      grid: {
        vertLines: { color: dark ? "#1e293b" : "#e2e8f0" },
        horzLines: { color: dark ? "#1e293b" : "#e2e8f0" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      localization: { locale: "sv-SE", priceFormatter: (p: number) => p.toFixed(0) },
    });
    const series = chart.addLineSeries({ color: dark ? "#38bdf8" : "#0369a1", lineWidth: 2 });
    series.setData(
      points.map((p) => ({ time: (Date.parse(p.time.replace(" ", "T") + "Z") / 1000) as UTCTimestamp, value: p.equity })),
    );
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [points, dark]);

  return <div ref={ref} className="h-64 w-full" aria-label="Equity-kurva" />;
}

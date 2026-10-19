import { createChart, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { Bar } from "../api";

/** Candlestick-graf för EUR/USD. Följer mörkt/ljust läge. */
export function PriceChart({ bars, dark }: { bars: Bar[]; dark: boolean }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      autoSize: true,
      layout: {
        background: { color: "transparent" },
        textColor: dark ? "#cbd5e1" : "#334155",
      },
      grid: {
        vertLines: { color: dark ? "#1e293b" : "#e2e8f0" },
        horzLines: { color: dark ? "#1e293b" : "#e2e8f0" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      localization: { locale: "sv-SE", priceFormatter: (p: number) => p.toFixed(5) },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#059669",
      downColor: "#e11d48",
      wickUpColor: "#059669",
      wickDownColor: "#e11d48",
      borderVisible: false,
    });
    series.setData(bars.map((b) => ({ ...b, time: b.time as UTCTimestamp })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars, dark]);

  return <div ref={ref} className="h-80 w-full sm:h-96" aria-label="EUR/USD-graf" />;
}

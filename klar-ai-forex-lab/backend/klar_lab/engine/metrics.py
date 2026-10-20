"""Resultatmått. Alla är netto efter spread, slippage, provision och swap."""
import math

import numpy as np
import pandas as pd

MIN_TRADES_FOR_CONCLUSION = 30


def _clean(x: float) -> float | None:
    """NaN/inf -> None så att måtten kan sparas som JSON."""
    return None if x is None or not math.isfinite(x) else float(x)


def compute_metrics(trades: list[dict], equity: pd.Series, start_capital: float) -> dict:
    n = len(trades)
    pnl = np.array([t["pnl"] for t in trades], dtype=float)
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    peak = equity.cummax()
    max_dd = float(((peak - equity) / peak).max()) if len(equity) else 0.0
    total_ret = float(equity.iloc[-1] / start_capital - 1) if len(equity) else 0.0
    daily = equity.resample("D").last().dropna().pct_change().dropna()
    sharpe = float(daily.mean() / daily.std() * np.sqrt(252)) if len(daily) > 2 and daily.std() > 0 else math.nan
    gross_loss = abs(losses.sum())
    return {k: _clean(v) if isinstance(v, float) else v for k, v in {
        "trades": n,
        "low_sample": n < MIN_TRADES_FOR_CONCLUSION,
        "win_rate": len(wins) / n if n else math.nan,
        "avg_win": float(wins.mean()) if len(wins) else math.nan,
        "avg_loss": float(losses.mean()) if len(losses) else math.nan,
        "expectancy": float(pnl.mean()) if n else math.nan,
        "total_return": total_ret,
        "max_drawdown": max_dd,
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else math.nan,
        "sharpe": sharpe,
        "return_to_maxdd": total_ret / max_dd if max_dd > 0 else math.nan,
        "est_costs": float(sum(t["cost_estimate"] for t in trades)),
        "swap": float(sum(t["swap"] for t in trades)),
        "net_pnl": float(pnl.sum()),
    }.items()}

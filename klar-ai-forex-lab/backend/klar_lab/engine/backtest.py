"""Backtestmotor (portad från prototypen + swap och dubbelorderskydd).

Regler:
- Signal på stapel i -> riskkontroll och order på öppningen av stapel i+1 (ingen lookahead).
- Max en position per strategi; varje strategi har ett eget konto med samma startkapital.
- Nås både stop och TP i samma stapel antas stop (konservativt).
- Gap förbi stop fylls på öppningen (sämre än stop), gap förbi TP fylls på TP (inte bättre).
- Swap dras vid varje rollover 22:00 UTC (onsdag ×3) medan positionen är öppen.
"""
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..risk import PIP, AccountState, LabConfig, RiskManager

ROLLOVER_HOUR_UTC = 22


@dataclass
class BacktestResult:
    strategy: str
    trades: list[dict]
    decisions: list[dict]
    equity: pd.Series
    halted: bool


def rollover_nights(t0: pd.Timestamp, t1: pd.Timestamp) -> int:
    """Antal swapnätter för rollovers i (t0, t1]. Onsdagens rollover räknas tre gånger (helgen)."""
    nights = 0
    day = t0.normalize()
    while day <= t1:
        roll = day + timedelta(hours=ROLLOVER_HOUR_UTC)
        if t0 < roll <= t1:
            nights += 3 if roll.dayofweek == 2 else 1
        day += timedelta(days=1)
    return nights


def run_backtest(df: pd.DataFrame, strategy, cfg: LabConfig, start: int, end: int,
                 kill_switch_file: Path | None = None) -> BacktestResult:
    """Kör strategin på staplarna [start, end). strategy.prepare(df) måste ha körts på hela df."""
    rm = RiskManager(cfg, kill_switch_file)
    fx = cfg.account.usd_to_account
    spread, slip = cfg.costs.spread, cfg.costs.slippage
    swap_pips = {1: cfg.costs.swap_long_pips_per_night, -1: cfg.costs.swap_short_pips_per_night}
    comm_unit = rm.commission_per_unit()
    state = AccountState.new(cfg.account.starting_capital)

    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    times = df.index
    pos, pending = None, None
    trades, decisions = [], []
    equity = np.empty(end - start)

    def close_position(i, price, reason):
        nonlocal pos
        d, units = pos["dir"], pos["units"]
        gross = (price - pos["entry"]) * d * units * fx
        pnl = gross - units * comm_unit - pos["swap"]
        cost_price = spread + slip + (slip if reason == "stop_loss" else 0.0)
        state.apply_pnl(pnl)
        state.open_positions = 0
        trades.append({
            "strategy": strategy.name, "direction": "long" if d == 1 else "short",
            "entry_time": pos["time"].isoformat(), "exit_time": times[i].isoformat(),
            "entry": round(pos["entry"], 6), "exit": round(price, 6), "stop": round(pos["sl"], 6),
            "take_profit": round(pos["tp"], 6), "units": units, "planned_risk": round(pos["risk"], 4),
            "planned_rr": round(pos["rr"], 3), "pnl": round(pnl, 4), "r_multiple": round(pnl / pos["risk"], 3),
            "swap": round(pos["swap"], 4),
            "cost_estimate": round(units * cost_price * fx + units * comm_unit + pos["swap"], 4),
            "exit_reason": reason, "balance_after": round(state.balance, 2),
        })
        pos = None

    for i in range(start, end):
        t = times[i]
        if state.day != t.date():
            state.roll_day(t.date())

        # Swap för natten/nätterna sedan föregående stapel
        if pos is not None and i > start:
            nights = rollover_nights(times[i - 1], t)
            if nights:
                pos["swap"] += nights * swap_pips[pos["dir"]] * PIP * pos["units"] * fx

        # 1) Order från föregående stapels signal
        if pending is not None and pos is None:
            sig, sig_idx = pending
            gap_h = (t - times[sig_idx]).total_seconds() / 3600
            dec = rm.evaluate(o[i], sig.stop_distance, sig.take_profit_distance, state, gap_h,
                              order_id=f"{strategy.name}:{times[sig_idx].isoformat()}")
            decisions.append({"time": t.isoformat(), "strategy": strategy.name,
                              "direction": "long" if sig.direction == 1 else "short",
                              "approved": dec.approved, "reason": dec.reason, "units": dec.units,
                              "planned_risk": round(dec.risk_amount, 4), "planned_rr": round(dec.reward_risk, 3)})
            if dec.approved:
                d = sig.direction
                state.open_positions = 1
                pos = {"dir": d, "entry": o[i] + spread + slip if d == 1 else o[i] - slip, "time": t,
                       "units": dec.units, "risk": dec.risk_amount, "rr": dec.reward_risk, "swap": 0.0,
                       "sl": o[i] - sig.stop_distance if d == 1 else o[i] + sig.stop_distance,
                       "tp": o[i] + sig.take_profit_distance if d == 1 else o[i] - sig.take_profit_distance}
        pending = None

        # 2) Hantera öppen position (även på ingångsstapeln)
        if pos is not None:
            if pos["dir"] == 1:
                if lo[i] <= pos["sl"]:
                    close_position(i, min(pos["sl"], o[i]) - slip, "stop_loss")
                elif h[i] >= pos["tp"]:
                    close_position(i, pos["tp"], "take_profit")
            else:
                if h[i] >= pos["sl"]:
                    close_position(i, max(pos["sl"], o[i]) + spread + slip, "stop_loss")
                elif lo[i] <= pos["tp"]:
                    close_position(i, pos["tp"] + spread, "take_profit")

        # 3) Stäng vid periodens slut
        if i == end - 1 and pos is not None:
            close_position(i, c[i] if pos["dir"] == 1 else c[i] + spread, "end_of_period")

        # 4) Mark-to-market (inklusive upplupen swap)
        unreal = 0.0
        if pos is not None:
            px = c[i] if pos["dir"] == 1 else c[i] + spread
            unreal = (px - pos["entry"]) * pos["dir"] * pos["units"] * fx - pos["swap"]
        equity[i - start] = state.balance + unreal

        # 5) Ny signal vid stapelslut (utförs nästa stapel)
        if pos is None and not state.halted and i + 1 < end:
            sig = strategy.signal(i)
            if sig is not None:
                pending = (sig, i)

    return BacktestResult(strategy.name, trades, decisions, pd.Series(equity, index=times[start:end]), state.halted)

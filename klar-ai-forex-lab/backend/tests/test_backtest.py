"""Backtestmotorns regler: ingen lookahead, kostnader, stop-före-TP, gap, swap."""
import dataclasses

import pandas as pd
import pytest

from klar_lab.engine import compute_metrics, rollover_nights, run_backtest, split_periods
from klar_lab.risk import PIP, LabConfig
from klar_lab.strategies import Signal, Strategy

NO_SWAP = LabConfig(costs=dataclasses.replace(LabConfig().costs, swap_long_pips_per_night=0,
                                              swap_short_pips_per_night=0))


class OneShot(Strategy):
    key = "oneshot"

    def __init__(self, direction, sl=0.0020, tp=0.0050, at=1):
        self.direction, self.sl, self.tp, self.at = direction, sl, tp, at

    @property
    def name(self):
        return "oneshot"

    def prepare(self, df):
        pass

    def signal(self, i):
        return Signal(self.direction, self.sl, self.tp) if i == self.at else None


FLAT = (1.1, 1.1005, 1.0995, 1.1)


def bars(bar2, n=6, start="2024-01-01 00:00"):
    idx = pd.date_range(start, periods=n, freq="h")
    rows = [FLAT, FLAT, bar2] + [FLAT] * (n - 3)
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def test_long_take_profit_net_of_costs_and_no_lookahead():
    df = bars((1.1000, 1.1060, 1.0995, 1.1050))
    t = run_backtest(df, OneShot(1), NO_SWAP, 0, 6).trades[0]
    assert t["exit_reason"] == "take_profit"
    c = NO_SWAP.costs
    assert t["pnl"] == pytest.approx(t["units"] * (0.0050 - c.spread - c.slippage) * 9.5, abs=0.1)
    assert t["entry_time"] == df.index[2].isoformat()   # signal på stapel 1 -> order på stapel 2


def test_long_stop_loss_equals_planned_risk():
    t = run_backtest(bars((1.1000, 1.1010, 1.0970, 1.0990)), OneShot(1), NO_SWAP, 0, 6).trades[0]
    assert t["exit_reason"] == "stop_loss"
    assert t["pnl"] == pytest.approx(-t["planned_risk"], abs=0.01) and -t["pnl"] <= 100.01


def test_both_hit_in_same_bar_assumes_stop():
    t = run_backtest(bars((1.1000, 1.1030, 1.0940, 1.1000)), OneShot(-1), NO_SWAP, 0, 6).trades[0]
    assert t["exit_reason"] == "stop_loss" and t["pnl"] == pytest.approx(-t["planned_risk"], abs=0.01)


def test_gap_through_stop_fills_at_open_worse_than_planned():
    df = bars(FLAT)
    df.iloc[3] = (1.0950, 1.0960, 1.0940, 1.0950)    # öppnar 30 pips under stop
    t = run_backtest(df, OneShot(1), NO_SWAP, 0, 6).trades[0]
    assert t["exit_reason"] == "stop_loss" and t["exit"] == pytest.approx(1.0950 - NO_SWAP.costs.slippage)
    assert -t["pnl"] > t["planned_risk"]              # verklig förlust > planerad: gap-risk redovisas


def test_gap_through_take_profit_is_not_better_than_tp():
    df = bars(FLAT)
    df.iloc[3] = (1.1100, 1.1110, 1.1090, 1.1100)
    t = run_backtest(df, OneShot(1), NO_SWAP, 0, 6).trades[0]
    assert t["exit_reason"] == "take_profit" and t["exit"] == pytest.approx(1.1050)


def test_rejected_trade_is_logged_not_executed():
    res = run_backtest(bars((1.1, 1.1, 1.1, 1.1)), OneShot(1, 0.0020, 0.0030), NO_SWAP, 0, 6)
    assert res.trades == [] and not res.decisions[0]["approved"]


def test_position_closed_at_period_end():
    res = run_backtest(bars(FLAT), OneShot(1), NO_SWAP, 0, 6)
    assert res.trades[0]["exit_reason"] == "end_of_period"
    assert res.equity.iloc[-1] == pytest.approx(10_000 + res.trades[0]["pnl"])


def test_signal_on_last_bar_is_not_executed():
    res = run_backtest(bars(FLAT), OneShot(1, at=5), NO_SWAP, 0, 6)
    assert res.decisions == [] and res.trades == []


def test_rollover_nights():
    ts = pd.Timestamp
    assert rollover_nights(ts("2024-01-01 21:00"), ts("2024-01-01 22:00")) == 1      # måndag
    assert rollover_nights(ts("2024-01-03 21:00"), ts("2024-01-03 23:00")) == 3      # onsdag ×3
    assert rollover_nights(ts("2024-01-01 22:00"), ts("2024-01-01 23:00")) == 0
    assert rollover_nights(ts("2024-01-01 12:00"), ts("2024-01-03 12:00")) == 2


def test_swap_is_charged_overnight():
    cfg = LabConfig()
    df = bars(FLAT, n=10, start="2024-01-01 18:00")    # måndag 18:00 -> rollover 22:00
    t = run_backtest(df, OneShot(1), cfg, 0, 10).trades[0]
    expected = cfg.costs.swap_long_pips_per_night * PIP * t["units"] * 9.5
    assert t["swap"] == pytest.approx(expected, abs=0.01)
    t0 = run_backtest(df, OneShot(1), NO_SWAP, 0, 10).trades[0]
    assert t["pnl"] == pytest.approx(t0["pnl"] - expected, abs=0.01)


def test_metrics_are_json_safe():
    df = bars(FLAT)
    m = compute_metrics([], pd.Series([10_000.0] * 6, index=df.index), 10_000)
    assert m["trades"] == 0 and m["win_rate"] is None and m["low_sample"]


def test_split_is_chronological_and_disjoint():
    p = split_periods(1_000)
    assert p["train"].end == p["validation"].start and p["validation"].end == p["test"].start
    assert p["test"].end == 1_000 and p["train"].start == 250


def test_parity_with_prototype_on_validation_period():
    """Samma data och kostnader (utan swap) ger exakt prototypens validerings-/testresultat."""
    from klar_lab.data import SyntheticFeed
    from klar_lab.strategies import baseline

    df = SyntheticFeed(30_000, 42).load().bars
    p = split_periods(len(df))["validation"]
    expected = {"A_trend": (13, -8.8), "B_momentum": (56, -18.2), "C_mean_reversion": (69, -11.7),
                "D_breakout": (50, -14.9)}   # från prototypens results/report.md
    for s in baseline():
        s.prepare(df)
        r = run_backtest(df, s, NO_SWAP, p.start, p.end)
        m = compute_metrics(r.trades, r.equity, 10_000)
        assert (m["trades"], round(m["total_return"] * 100, 1)) == expected[s.key], s.key

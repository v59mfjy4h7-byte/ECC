"""Agent A–D, portade från prototypen med samma standardvärden."""
from .base import Param, Strategy
from .indicators import atr, cross_up, ema, first_bar, rsi


class TrendStrategy(Strategy):
    key = "A_trend"
    title = "A – Trend"
    description = "Snabb/långsam EMA-korsning i riktning mot bas-EMA, med trendstyrkefilter (efficiency ratio)."
    own_params = (
        Param("fast", "int", 20, 5, 100), Param("slow", "int", 50, 10, 200), Param("base", "int", 200, 50, 400),
        Param("er_period", "int", 30, 10, 100), Param("er_min", "float", 0.2, 0.0, 0.8),
    )

    def compute(self, df):
        p, c = self.params, df["close"]
        fast, slow, base = ema(c, p["fast"]), ema(c, p["slow"]), ema(c, p["base"])
        n = p["er_period"]
        er = (c - c.shift(n)).abs() / c.diff().abs().rolling(n).sum()
        strong = er > p["er_min"]
        return cross_up(fast, slow) & (c > base) & strong, cross_up(slow, fast) & (c < base) & strong


class MomentumStrategy(Strategy):
    key = "B_momentum"
    title = "B – Momentum"
    description = "RSI korsar övre/undre nivå i samma riktning som prisförändringen över roc_period staplar."
    defaults = {"sl_atr_mult": 1.5}
    own_params = (
        Param("rsi_period", "int", 14, 5, 50), Param("upper", "float", 55, 50, 80), Param("lower", "float", 45, 20, 50),
        Param("roc_period", "int", 10, 2, 100),
    )

    def compute(self, df):
        p, c = self.params, df["close"]
        r, roc = rsi(c, p["rsi_period"]), c.pct_change(p["roc_period"])
        long_ = (r > p["upper"]) & (r.shift(1) <= p["upper"]) & (roc > 0)
        short_ = (r < p["lower"]) & (r.shift(1) >= p["lower"]) & (roc < 0)
        return long_, short_


class MeanReversionStrategy(Strategy):
    key = "C_mean_reversion"
    title = "C – Mean reversion"
    description = "Pris utanför Bollingerband samtidigt som RSI är översåld/överköpt (första stapeln)."
    own_params = (
        Param("bb_period", "int", 20, 10, 100), Param("bb_std", "float", 2.0, 1.0, 4.0),
        Param("rsi_period", "int", 14, 5, 50), Param("rsi_low", "float", 30, 5, 45), Param("rsi_high", "float", 70, 55, 95),
    )

    def compute(self, df):
        p, c = self.params, df["close"]
        mid, sd = c.rolling(p["bb_period"]).mean(), c.rolling(p["bb_period"]).std()
        r = rsi(c, p["rsi_period"])
        lo = (c < mid - p["bb_std"] * sd) & (r < p["rsi_low"])
        hi = (c > mid + p["bb_std"] * sd) & (r > p["rsi_high"])
        return first_bar(lo), first_bar(hi)


class BreakoutStrategy(Strategy):
    key = "D_breakout"
    title = "D – Breakout"
    description = "Slutkurs bryter högsta/lägsta över lookback staplar, endast när volatiliteten är över sitt snitt."
    own_params = (Param("lookback", "int", 40, 10, 200), Param("vol_period", "int", 100, 20, 400))

    def compute(self, df):
        p, c = self.params, df["close"]
        hh = df["high"].rolling(p["lookback"]).max().shift(1)
        ll = df["low"].rolling(p["lookback"]).min().shift(1)
        a = atr(df, self.params["atr_period"])
        vol_ok = a > a.rolling(p["vol_period"]).mean()
        long_ = (c > hh) & (c.shift(1) <= hh.shift(1)) & vol_ok
        short_ = (c < ll) & (c.shift(1) >= ll.shift(1)) & vol_ok
        return long_, short_


STRATEGIES: dict[str, type[Strategy]] = {
    s.key: s for s in (TrendStrategy, MomentumStrategy, MeanReversionStrategy, BreakoutStrategy)
}


def build(key: str, params: dict | None = None) -> Strategy:
    if key not in STRATEGIES:
        raise ValueError(f"Okänd strategi: {key}")
    return STRATEGIES[key](**(params or {}))


def baseline() -> list[Strategy]:
    return [cls() for cls in STRATEGIES.values()]


__all__ = ["STRATEGIES", "build", "baseline"]

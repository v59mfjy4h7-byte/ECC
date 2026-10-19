"""Syntetisk H1-testdata med växlande trend-/range-regimer (portad från prototypen).

Är INTE verklig marknadsdata. Allt som byggs på den märks som syntetiskt i DB och UI.
"""
import numpy as np
import pandas as pd


def generate_synthetic(n_bars: int = 30_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sigma = 0.00055
    close = np.empty(n_bars)
    price, anchor, drift = 1.10, 1.10, 0.0
    regime, left = "range", 0
    for i in range(n_bars):
        if left <= 0:
            regime = rng.choice(["trend", "range"])
            left = int(rng.integers(150, 900))
            drift = rng.choice([-1, 1]) * rng.uniform(0.5, 1.5) * 0.00006
            anchor = price
        left -= 1
        if regime == "trend":
            price += drift + sigma * rng.standard_normal()
        else:
            price += 0.03 * (anchor - price) + sigma * rng.standard_normal()
        price = min(max(price, 0.8), 1.5)
        close[i] = price
    opn = np.concatenate([[1.10], close[:-1]])
    wick = np.abs(rng.standard_normal((n_bars, 2))) * sigma * 0.5
    high = np.maximum(opn, close) + wick[:, 0]
    low = np.minimum(opn, close) - wick[:, 1]
    idx = pd.date_range("2019-01-01", periods=int(n_bars * 7 / 5) + 48, freq=pd.Timedelta(hours=1))
    idx = idx[idx.dayofweek < 5][:n_bars]
    df = pd.DataFrame({"open": opn, "high": high, "low": low, "close": close}, index=idx).round(5)
    df.index.name = "time"
    return df

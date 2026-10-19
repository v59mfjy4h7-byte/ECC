import pandas as pd


def h1_bars(n: int = 1_200, start: str = "2024-01-01", price: float = 1.10) -> pd.DataFrame:
    """Enkla, giltiga H1-staplar endast på vardagar."""
    idx = pd.date_range(start, periods=n * 2, freq="h")
    idx = idx[idx.dayofweek < 5][:n]
    close = pd.Series([price + 0.0001 * ((i % 20) - 10) for i in range(n)], index=idx)
    opn = close.shift(1).fillna(price)
    df = pd.DataFrame({"open": opn, "close": close})
    df["high"] = df[["open", "close"]].max(axis=1) + 0.0002
    df["low"] = df[["open", "close"]].min(axis=1) - 0.0002
    df.index.name = "time"
    return df[["open", "high", "low", "close"]]


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv().encode("utf-8")

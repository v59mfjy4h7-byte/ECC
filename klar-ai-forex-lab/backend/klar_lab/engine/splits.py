"""Kronologisk uppdelning i train / validation / test (60/20/20 som i prototypen)."""
from dataclasses import dataclass

import pandas as pd

TRAIN_FRAC = 0.60
VAL_FRAC = 0.20
WARMUP_BARS = 250   # indikatorer behöver historik; första perioden startar efter uppvärmning


@dataclass(frozen=True)
class Period:
    name: str      # train | validation | test
    start: int     # index i datasetet (inklusive)
    end: int       # (exklusive)


def split_periods(n_bars: int) -> dict[str, Period]:
    i_train = int(n_bars * TRAIN_FRAC)
    i_val = int(n_bars * (TRAIN_FRAC + VAL_FRAC))
    return {
        "train": Period("train", min(WARMUP_BARS, i_train), i_train),
        "validation": Period("validation", i_train, i_val),
        "test": Period("test", i_val, n_bars),
    }


def describe(periods: dict[str, Period], index: pd.DatetimeIndex) -> dict[str, dict]:
    return {p.name: {"start": index[p.start].isoformat(), "end": index[p.end - 1].isoformat(),
                     "bars": p.end - p.start} for p in periods.values()}

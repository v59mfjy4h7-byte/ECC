"""Datakällor bakom ett gemensamt gränssnitt.

M1 innehåller CsvFeed (historik) och SyntheticFeed (uttryckligen märkt testdata).
PaperLiveFeed (M5) implementerar samma gränssnitt så att källan kan bytas.
"""
import hashlib
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .synthetic import generate_synthetic
from .validation import DataValidationError, ValidationConfig, ValidationReport, validate_bars

TIME_COLUMNS = ("time", "timestamp", "datetime", "date")


@dataclass
class MarketData:
    bars: pd.DataFrame          # index: UTC-tid (naiv), kolumner open/high/low/close
    report: ValidationReport
    source: str
    synthetic: bool

    @property
    def sha256(self) -> str:
        return dataset_hash(self.bars)


class DataFeed(ABC):
    """Gränssnitt för alla datakällor. load() returnerar validerade staplar eller kastar fel."""

    @abstractmethod
    def load(self) -> MarketData:
        ...


def dataset_hash(bars: pd.DataFrame) -> str:
    """SHA-256 av den normaliserade CSV-representationen: samma data ger samma hash
    oavsett ursprunglig filformatering."""
    return hashlib.sha256(to_canonical_csv(bars).encode("utf-8")).hexdigest()


def to_canonical_csv(bars: pd.DataFrame) -> str:
    out = bars[["open", "high", "low", "close"]].copy()
    out.index = out.index.strftime("%Y-%m-%dT%H:%M:%S")
    out.index.name = "time"
    return out.to_csv(float_format="%.6f", lineterminator="\n")


def parse_csv(content: bytes | str | Path) -> pd.DataFrame:
    """Läser CSV med time/timestamp/datetime/date (eller separata Date+Time, t.ex. MT4/MT5)
    samt open/high/low/close. Kolumnnamn är skiftlägesokänsliga; <OPEN> fungerar också."""
    try:
        if isinstance(content, Path):
            raw = pd.read_csv(content, sep=None, engine="python")
        else:
            text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
            raw = pd.read_csv(io.StringIO(text), sep=None, engine="python")
    except FileNotFoundError:
        raise DataValidationError(f"Datafilen '{content}' finns inte.")
    except Exception as exc:
        raise DataValidationError(f"Kunde inte läsa CSV: {exc}")

    raw.columns = [str(c).strip().lower().strip("<>") for c in raw.columns]
    if "date" in raw.columns and "time" in raw.columns:
        stamp = raw["date"].astype(str) + " " + raw["time"].astype(str)
    else:
        tcol = next((c for c in TIME_COLUMNS if c in raw.columns), None)
        if tcol is None:
            raise DataValidationError("Hittar ingen tidskolumn (time/timestamp/datetime/date).")
        stamp = raw[tcol]
    missing = [c for c in ("open", "high", "low", "close") if c not in raw.columns]
    if missing:
        raise DataValidationError(f"Saknade kolumner: {missing}")

    df = raw[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    try:
        idx = pd.to_datetime(stamp, errors="raise", utc=True)
    except Exception as exc:
        raise DataValidationError(f"Ogiltiga tidsstämplar: {exc}")
    df.index = pd.DatetimeIndex(idx).tz_convert("UTC").tz_localize(None).as_unit("ns")
    df.index.name = "time"
    return df


class CsvFeed(DataFeed):
    def __init__(self, source: Path | bytes, name: str | None = None,
                 cfg: ValidationConfig = ValidationConfig()):
        self.source = source
        self.name = name or (source.name if isinstance(source, Path) else "upload.csv")
        self.cfg = cfg

    def load(self) -> MarketData:
        bars, report = validate_bars(parse_csv(self.source), self.cfg)
        return MarketData(bars, report, self.name, synthetic=False)


class SyntheticFeed(DataFeed):
    """Syntetisk TESTDATA. Resultat på den säger ingenting om verklig lönsamhet."""

    def __init__(self, n_bars: int = 30_000, seed: int = 42, cfg: ValidationConfig = ValidationConfig()):
        self.n_bars, self.seed, self.cfg = n_bars, seed, cfg

    def load(self) -> MarketData:
        bars, report = validate_bars(generate_synthetic(self.n_bars, self.seed), self.cfg)
        return MarketData(bars, report, f"SYNTETISK TESTDATA (seed {self.seed}, {self.n_bars} staplar)",
                          synthetic=True)

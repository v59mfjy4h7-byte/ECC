"""Validering av EUR/USD-staplar.

Två allvarlighetsgrader:
  error   – datan är inte tillförlitlig; datasetet avvisas (inga resultat byggs på den)
  warning – datan används, men problemet redovisas i rapporten och i UI

Tider antas vara UTC. Tidszonsmärkta tider konverteras till UTC.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

OHLC = ["open", "high", "low", "close"]


class DataValidationError(Exception):
    """Datan saknas eller är inte tillförlitlig."""

    def __init__(self, message: str, report: "ValidationReport | None" = None):
        super().__init__(message)
        self.report = report


@dataclass(frozen=True)
class ValidationConfig:
    price_min: float = 0.5               # rimligt EUR/USD-intervall
    price_max: float = 2.0
    min_bars: int = 1_000
    max_abs_return: float = 0.02         # |log-avkastning| per stapel över detta = misstänkt spik (varning)
    max_gap_days: float = 7.0            # lucka längre än så (utöver helg) = fel
    max_flat_bar_share: float = 0.05     # andel staplar med O=H=L=C över detta = misstänkt fryst feed
    weekend_max_hours: float = 72.0      # helgstängning fre→sön ryms inom detta


@dataclass
class Issue:
    severity: str        # "error" | "warning"
    code: str
    message: str
    count: int = 0
    examples: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    ok: bool = True
    bars: int = 0
    start: str | None = None
    end: str | None = None
    timeframe_minutes: float | None = None
    duplicates_removed: int = 0
    sorted: bool = False
    gaps: int = 0
    largest_gap_hours: float = 0.0
    issues: list[Issue] = field(default_factory=list)

    def add(self, severity: str, code: str, message: str, count: int = 0, examples=None) -> None:
        shown = [str(e) for e in list(examples if examples is not None else [])[:5]]
        self.issues.append(Issue(severity, code, message, count, shown))
        if severity == "error":
            self.ok = False

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    def to_dict(self) -> dict:
        return asdict(self)


def _is_weekend_gap(t0: pd.Timestamp, t1: pd.Timestamp, max_hours: float) -> bool:
    """FX-marknaden är stängd ungefär fredag kväll → söndag kväll (UTC)."""
    hours = (t1 - t0).total_seconds() / 3600
    return hours <= max_hours and t0.dayofweek in (4, 5) and t1.dayofweek in (6, 0)


def validate_bars(df: pd.DataFrame, cfg: ValidationConfig = ValidationConfig()) -> tuple[pd.DataFrame, ValidationReport]:
    """Kontrollerar och normaliserar staplar. Returnerar (rensad df, rapport).

    Kastar DataValidationError om något fel av graden "error" hittas.
    """
    rep = ValidationReport()
    missing = [c for c in OHLC if c not in df.columns]
    if missing:
        rep.add("error", "missing_columns", f"Saknade kolumner: {missing}")
        raise DataValidationError(rep.issues[-1].message, rep)
    df = df[OHLC].astype(float)

    nan_rows = df.isna().any(axis=1)
    if nan_rows.any():
        rep.add("error", "nan_prices", "Saknade/ogiltiga prisvärden (NaN).", int(nan_rows.sum()),
                df.index[nan_rows][:5])
    nonpos = (df <= 0).any(axis=1)
    if nonpos.any():
        rep.add("error", "non_positive_prices", "Priser <= 0.", int(nonpos.sum()), df.index[nonpos][:5])
    bad_hl = (df["high"] < df[["open", "close", "low"]].max(axis=1) - 1e-12) | (
        df["low"] > df[["open", "close", "high"]].min(axis=1) + 1e-12)
    if bad_hl.any():
        rep.add("error", "inconsistent_high_low", "Staplar där high/low inte omsluter open/close.",
                int(bad_hl.sum()), df.index[bad_hl][:5])
    out_of_range = ((df["low"] < cfg.price_min) | (df["high"] > cfg.price_max)) & ~nan_rows
    if out_of_range.any():
        rep.add("error", "price_out_of_range",
                f"Priser utanför rimligt EUR/USD-intervall ({cfg.price_min}–{cfg.price_max}). Rätt valutapar?",
                int(out_of_range.sum()), df.index[out_of_range][:5])

    # Dubbletter: identiska rader tas bort (varning); motstridiga värden för samma tid = fel.
    dup_mask = df.index.duplicated(keep=False)
    if dup_mask.any():
        dups = df[dup_mask]
        conflicting = dups.groupby(level=0).nunique().gt(1).any(axis=1)
        if conflicting.any():
            rep.add("error", "conflicting_duplicates", "Samma tidsstämpel med olika priser.",
                    int(conflicting.sum()), conflicting.index[conflicting][:5])
        n_removed = int(df.index.duplicated(keep="first").sum())
        df = df[~df.index.duplicated(keep="first")]
        rep.duplicates_removed = n_removed
        rep.add("warning", "duplicates_removed", "Identiska dubblettstaplar togs bort.", n_removed)

    if not df.index.is_monotonic_increasing:
        df = df.sort_index()
        rep.sorted = True
        rep.add("warning", "unsorted", "Staplarna var inte i tidsordning och sorterades.")

    if len(df) < cfg.min_bars:
        rep.add("error", "too_few_bars", f"För få staplar ({len(df)}); minst {cfg.min_bars} krävs.", len(df))

    if len(df) >= 2:
        diffs = df.index.to_series().diff().dropna()
        step = diffs.median()
        rep.timeframe_minutes = step.total_seconds() / 60
        gap_idx = np.flatnonzero(diffs.to_numpy() > step.to_numpy() * 1.5)
        times = df.index
        unexpected = [(times[k], times[k + 1]) for k in gap_idx
                      if not _is_weekend_gap(times[k], times[k + 1], cfg.weekend_max_hours)]
        rep.gaps = len(unexpected)
        if unexpected:
            hours = [(b - a).total_seconds() / 3600 for a, b in unexpected]
            rep.largest_gap_hours = round(max(hours), 2)
            long_ = [f"{a} → {b}" for (a, b), h in zip(unexpected, hours) if h > cfg.max_gap_days * 24]
            if long_:
                rep.add("error", "long_gap", f"Luckor längre än {cfg.max_gap_days:g} dagar.", len(long_), long_)
            rep.add("warning", "gaps", "Luckor utöver normal helgstängning (t.ex. helgdagar eller saknad data).",
                    len(unexpected), [f"{a} → {b}" for a, b in unexpected])

        with np.errstate(invalid="ignore", divide="ignore"):  # ogiltiga priser är redan rapporterade
            logret = np.log(df["close"]).diff().abs()
        spikes = logret > cfg.max_abs_return
        if spikes.any():
            rep.add("warning", "price_spikes",
                    f"Stapel-till-stapel-rörelser över {cfg.max_abs_return:.1%} (kontrollera mot annan källa).",
                    int(spikes.sum()), df.index[spikes][:5])

    flat = (df["high"] == df["low"])
    if len(df) and flat.mean() > cfg.max_flat_bar_share:
        rep.add("warning", "flat_bars", "Ovanligt många staplar utan rörelse (fryst eller gles datakälla?).",
                int(flat.sum()))

    rep.bars = len(df)
    if len(df):
        rep.start, rep.end = str(df.index[0]), str(df.index[-1])
    if not rep.ok:
        raise DataValidationError("; ".join(i.message for i in rep.errors), rep)
    return df, rep


def check_staleness(last_bar_time: datetime, now: datetime, max_age: timedelta) -> bool:
    """True om senaste stapeln är äldre än max_age (då ska handel pausas).

    Används av live-/paper-flöden. Under helgstängning förväntas äldre data och
    anroparen ansvarar för att ange ett lämpligt max_age.
    """
    return now - last_bar_time > max_age

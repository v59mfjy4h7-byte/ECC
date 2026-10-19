"""Import, lagring och läsning av dataset."""
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .data import MarketData, to_canonical_csv
from .models import Dataset
from .registry import audit, finish_experiment, start_experiment
from .settings import Settings


def store_dataset(session: Session, settings: Settings, data: MarketData, name: str,
                  actor: str = "human") -> tuple[Dataset, bool]:
    """Sparar ett validerat dataset. Returnerar (dataset, skapat). Samma data (samma hash)
    lagras bara en gång."""
    sha = data.sha256
    existing = session.scalar(select(Dataset).where(Dataset.sha256 == sha))
    if existing:
        return existing, False

    settings.ensure_dirs()
    path = settings.datasets_dir / f"{sha}.csv"
    path.write_text(to_canonical_csv(data.bars), encoding="utf-8")

    rep = data.report
    ds = Dataset(
        name=name, source=data.source, sha256=sha, synthetic=data.synthetic,
        timeframe_minutes=rep.timeframe_minutes, bars=rep.bars,
        start=data.bars.index[0].to_pydatetime(), end=data.bars.index[-1].to_pydatetime(),
        validation=rep.to_dict(),
    )
    session.add(ds)
    session.flush()
    audit(session, actor, "dataset_imported", dataset_id=ds.id, sha256=sha, synthetic=data.synthetic,
          bars=rep.bars, source=data.source)

    exp = start_experiment(session, kind="data_validation", name=f"Validering: {name}", dataset=ds,
                           params={"source": data.source}, actor=actor)
    warnings = [i.code for i in rep.issues if i.severity == "warning"]
    finish_experiment(session, exp, metrics={"bars": rep.bars, "gaps": rep.gaps,
                                             "duplicates_removed": rep.duplicates_removed, "warnings": warnings},
                      decision="approved",
                      decision_reason="Inga valideringsfel" + (f"; varningar: {', '.join(warnings)}" if warnings else ""),
                      actor=actor)
    return ds, True


def dataset_path(settings: Settings, ds: Dataset) -> Path:
    return settings.datasets_dir / f"{ds.sha256}.csv"


@lru_cache(maxsize=4)
def _read_bars(path: str) -> pd.DataFrame:
    return pd.read_csv(path, index_col="time", parse_dates=["time"])


def load_bars(settings: Settings, ds: Dataset) -> pd.DataFrame:
    path = dataset_path(settings, ds)
    if not path.exists():
        raise FileNotFoundError(f"Datafilen för dataset {ds.id} saknas: {path}")
    return _read_bars(str(path))


def downsample_ohlc(bars: pd.DataFrame, max_points: int) -> pd.DataFrame:
    """Slår ihop k på varandra följande staplar till en (open=första, high=max, low=min, close=sista)
    så att grafen aldrig får fler än max_points punkter. Ändrar aldrig prisnivåer."""
    if max_points <= 0 or len(bars) <= max_points:
        return bars
    k = -(-len(bars) // max_points)
    group = pd.Series(range(len(bars)), index=bars.index) // k
    agg = bars.groupby(group.to_numpy()).agg(open=("open", "first"), high=("high", "max"),
                                            low=("low", "min"), close=("close", "last"))
    agg.index = bars.index[::k][: len(agg)]
    return agg

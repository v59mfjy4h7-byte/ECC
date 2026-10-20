"""Kör strategier som backtester och registrerar varje körning som ett experiment.

Testperioden är låst: den körs bara på uttrycklig begäran av en människa och högst en gång
per (strategikonfiguration, dataset). Öppningen loggas i revisionsloggen.
"""
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..engine import compute_metrics, describe, run_backtest, split_periods
from ..models import Dataset, Experiment
from ..registry import RegistryError, audit, fail_experiment, finish_experiment, start_experiment
from ..risk import LabConfig
from ..strategies import Strategy

OPEN_PERIODS = ("train", "validation")
EQUITY_POINTS = 2_000


class LockedPeriodError(Exception):
    pass


def is_test_period_used(session: Session, dataset: Dataset, config_hash: str) -> bool:
    rows = session.scalars(select(Experiment).where(
        Experiment.kind == "backtest", Experiment.data_scope == "test", Experiment.data_hash == dataset.sha256))
    return any(e.params.get("config_hash") == config_hash for e in rows)


def _save_artifacts(run_dir: Path, result, equity: pd.Series) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(result.trades).to_csv(run_dir / "trades.csv", index=False)
    pd.DataFrame(result.decisions).to_csv(run_dir / "decisions.csv", index=False)
    step = max(1, -(-len(equity) // EQUITY_POINTS))
    sampled = equity.iloc[::step]
    if len(equity) and sampled.index[-1] != equity.index[-1]:
        sampled = pd.concat([sampled, equity.iloc[[-1]]])
    sampled.rename("equity").to_frame().to_csv(run_dir / "equity.csv", index_label="time")


def run_strategies(session: Session, *, bars: pd.DataFrame, dataset: Dataset, strategies: list[Strategy],
                   cfg: LabConfig, cfg_status: dict, runs_dir: Path, periods: tuple[str, ...] = OPEN_PERIODS,
                   kill_switch_file: Path | None = None, actor: str = "human") -> list[Experiment]:
    split = split_periods(len(bars))
    unknown = set(periods) - set(split)
    if unknown:
        raise ValueError(f"Okända perioder: {sorted(unknown)}")
    if "test" in periods:
        for s in strategies:
            if is_test_period_used(session, dataset, s.config_hash):
                raise LockedPeriodError(f"Testperioden har redan öppnats för {s.key} ({s.config_hash}) på detta dataset.")
        if actor != "human":
            raise LockedPeriodError("Bara en människa kan öppna testperioden.")

    period_info = describe(split, bars.index)
    experiments = []
    for s in strategies:
        s.prepare(bars)
        for period in periods:
            p = split[period]
            if period == "test":
                audit(session, actor, "test_period_opened", strategy=s.key, config_hash=s.config_hash,
                      dataset_id=dataset.id)
            exp = start_experiment(
                session, kind="backtest", name=f"{s.key} · {period}", dataset=dataset, data_scope=period,
                params={**s.config, "config_hash": s.config_hash, "period": period_info[period],
                        "lab_config": cfg.to_dict(), "lab_config_source": cfg_status.get("source")},
                actor=actor)
            try:
                result = run_backtest(bars, s, cfg, p.start, p.end, kill_switch_file)
                metrics = compute_metrics(result.trades, result.equity, cfg.account.starting_capital)
                metrics["halted"] = result.halted
                metrics["rejected_orders"] = sum(1 for d in result.decisions if not d["approved"])
                _save_artifacts(runs_dir / str(exp.id), result, result.equity)
                finish_experiment(session, exp, metrics=metrics, actor=actor)
            except RegistryError:
                raise
            except Exception as exc:  # experimentet sparas som misslyckat i stället för att försvinna
                fail_experiment(session, exp, f"{type(exc).__name__}: {exc}", actor=actor)
            experiments.append(exp)
    return experiments


def read_artifact(runs_dir: Path, experiment_id: int, name: str) -> list[dict]:
    path = runs_dir / str(experiment_id) / f"{name}.csv"
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []
    return json.loads(df.to_json(orient="records"))

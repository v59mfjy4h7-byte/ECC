"""API för strategier, backtester, riskkonfiguration och kill switch (M2)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..datasets import load_bars
from ..models import Experiment
from ..registry import audit
from ..research import OPEN_PERIODS, LockedPeriodError, is_test_period_used, read_artifact, run_strategies
from ..risk.signing import CEILINGS, FLOORS
from ..strategies import STRATEGIES, build
from .deps import db, get_dataset
from .serializers import experiment_out

router = APIRouter(prefix="/api")

ARTIFACTS = {"trades", "decisions", "equity"}


class StrategySpec(BaseModel):
    key: str
    params: dict[str, float] = Field(default_factory=dict)


class BacktestRequest(BaseModel):
    dataset_id: int
    strategies: list[StrategySpec] | None = None      # None = A–D med standardparametrar
    periods: list[str] = Field(default_factory=lambda: list(OPEN_PERIODS))
    confirm_test_access: bool = False


class KillSwitchRequest(BaseModel):
    active: bool
    confirm: bool = False


def _lab_config(request: Request):
    state = request.app.state
    if state.lab_config is None:
        raise HTTPException(503, f"Riskkonfigurationen är ogiltig; inga backtester körs. {state.lab_config_error}")
    return state.lab_config, state.lab_config_status


@router.get("/strategies")
def strategies():
    return [cls.describe() for cls in STRATEGIES.values()]


@router.get("/config")
def config(request: Request):
    state = request.app.state
    return {
        "config": state.lab_config.to_dict() if state.lab_config else None,
        "status": state.lab_config_status, "error": state.lab_config_error,
        "ceilings": CEILINGS, "floors": FLOORS,
        "kill_switch_active": state.settings.kill_switch_file.exists(),
    }


@router.post("/backtests")
def backtest(req: BacktestRequest, request: Request, session: Session = Depends(db)):
    cfg, cfg_status = _lab_config(request)
    settings = request.app.state.settings
    if "test" in req.periods and not req.confirm_test_access:
        raise HTTPException(400, "Testperioden är låst. Den kan öppnas en gång per strategikonfiguration "
                                 "och kräver confirm_test_access=true.")
    try:
        strategies = [build(s.key, s.params) for s in req.strategies] if req.strategies else \
            [cls() for cls in STRATEGIES.values()]
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    ds = get_dataset(session, req.dataset_id)
    bars = load_bars(settings, ds)
    try:
        exps = run_strategies(session, bars=bars, dataset=ds, strategies=strategies, cfg=cfg, cfg_status=cfg_status,
                              runs_dir=settings.runs_dir, periods=tuple(req.periods),
                              kill_switch_file=settings.kill_switch_file)
    except LockedPeriodError as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return [experiment_out(e) for e in exps]


@router.get("/backtests/test-access")
def test_access(dataset_id: int, request: Request, session: Session = Depends(db)):
    """Vilka standardstrategier som redan har förbrukat sin testperiod på datasetet."""
    ds = get_dataset(session, dataset_id)
    return {cls.key: is_test_period_used(session, ds, cls().config_hash) for cls in STRATEGIES.values()}


@router.get("/experiments/{experiment_id}/artifacts/{name}")
def artifact(experiment_id: int, name: str, request: Request, session: Session = Depends(db)):
    if name not in ARTIFACTS:
        raise HTTPException(404, f"Okänd artefakt: {name}")
    if session.get(Experiment, experiment_id) is None:
        raise HTTPException(404, f"Experiment {experiment_id} finns inte.")
    return read_artifact(request.app.state.settings.runs_dir, experiment_id, name)


@router.post("/kill-switch")
def kill_switch(req: KillSwitchRequest, request: Request, session: Session = Depends(db)):
    """Aktivering sker direkt. Avaktivering kräver uttrycklig bekräftelse."""
    path = request.app.state.settings.kill_switch_file
    if req.active:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Kill switch aktiverad från UI\n", encoding="utf-8")
    else:
        if not req.confirm:
            raise HTTPException(400, "Avaktivering kräver confirm=true.")
        path.unlink(missing_ok=True)
    audit(session, "human", "kill_switch_on" if req.active else "kill_switch_off")
    return {"kill_switch_active": path.exists()}

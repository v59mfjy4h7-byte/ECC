"""FastAPI-app. Starta med: uvicorn klar_lab.api.main:app --reload (i backend/)."""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import settings as settings_module
from ..data import CsvFeed, DataValidationError, SyntheticFeed
from ..datasets import downsample_ohlc, load_bars, store_dataset
from ..db import make_engine, make_sessionmaker, run_migrations
from ..models import AuditLog, Dataset, Experiment
from ..registry import code_version, list_experiments
from ..risk import RiskConfigError, load_lab_config
from ..settings import APP_VERSION, Settings
from .deps import db, get_dataset
from .serializers import audit_out, dataset_out, experiment_out
from .lab import router as lab_router


class SyntheticRequest(BaseModel):
    n_bars: int = Field(30_000, ge=1_000, le=200_000)
    seed: int = Field(42, ge=0)


class ImportRequest(BaseModel):
    filename: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        assert settings_module.LIVE_TRADING_ENABLED is False, "Livehandel får inte vara aktiverad."
        settings.ensure_dirs()
        run_migrations(settings.db_url)
        engine = make_engine(settings.db_url)
        app.state.sessionmaker = make_sessionmaker(engine)
        app.state.settings = settings
        try:
            app.state.lab_config, app.state.lab_config_status = load_lab_config(
                settings.config_dir / "risk_limits.json")
            app.state.lab_config_error = None
        except RiskConfigError as exc:  # systemet startar men vägrar köra backtester
            app.state.lab_config, app.state.lab_config_status = None, {"source": "invalid"}
            app.state.lab_config_error = str(exc)
        yield
        engine.dispose()

    app = FastAPI(title="Klar AI Forex Lab", version=APP_VERSION, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.exception_handler(DataValidationError)
    async def _validation_error(_req, exc: DataValidationError):
        return JSONResponse(status_code=422, content={
            "detail": str(exc), "report": exc.report.to_dict() if exc.report else None})

    def _save(session: Session, data, name: str) -> dict:
        ds, created = store_dataset(session, settings, data, name)
        return {"dataset": dataset_out(ds), "created": created}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": APP_VERSION, "live_trading_enabled": settings_module.LIVE_TRADING_ENABLED}

    @app.get("/api/system")
    def system():
        return {
            "version": APP_VERSION, "code_version": code_version(),
            "live_trading_enabled": settings_module.LIVE_TRADING_ENABLED,
            "milestone": "M2", "max_upload_mb": settings.max_upload_mb,
        }

    @app.get("/api/datasets")
    def datasets(session: Session = Depends(db)):
        return [dataset_out(d) for d in session.scalars(select(Dataset).order_by(Dataset.id.desc()))]

    @app.get("/api/datasets/incoming")
    def incoming_files():
        """CSV-filer i data/incoming/ som kan importeras utan uppladdning."""
        settings.ensure_dirs()
        return [{"filename": p.name, "size_bytes": p.stat().st_size}
                for p in sorted(settings.incoming_dir.glob("*.csv")) if p.is_file()]

    @app.get("/api/datasets/{dataset_id}")
    def dataset(dataset_id: int, session: Session = Depends(db)):
        return dataset_out(get_dataset(session, dataset_id))

    @app.get("/api/datasets/{dataset_id}/bars")
    def bars(dataset_id: int, start: datetime | None = None, end: datetime | None = None,
             max_points: int = Query(2_000, ge=10, le=20_000), session: Session = Depends(db)):
        ds = get_dataset(session, dataset_id)
        try:
            df = load_bars(settings, ds)
        except FileNotFoundError as exc:
            raise HTTPException(500, str(exc))
        if start is not None:
            df = df[df.index >= start.replace(tzinfo=None)]
        if end is not None:
            df = df[df.index <= end.replace(tzinfo=None)]
        sampled = downsample_ohlc(df, max_points)
        return {
            "dataset_id": ds.id, "synthetic": ds.synthetic, "bars_in_range": len(df),
            "aggregated": len(sampled) < len(df),
            "bars": [{"time": int(t.timestamp()), "open": o, "high": h, "low": lo, "close": c}
                     for t, o, h, lo, c in zip(sampled.index, sampled["open"], sampled["high"],
                                               sampled["low"], sampled["close"])],
        }

    @app.post("/api/datasets/upload")
    async def upload(file: UploadFile, session: Session = Depends(db)):
        limit = settings.max_upload_mb * 1024 * 1024
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise HTTPException(413, f"Filen är större än {settings.max_upload_mb} MB. "
                                     "Lägg den i data/incoming/ och importera därifrån.")
        name = file.filename or "upload.csv"
        return _save(session, CsvFeed(content, name=name).load(), name)

    @app.post("/api/datasets/import")
    def import_incoming(req: ImportRequest, session: Session = Depends(db)):
        incoming = settings.incoming_dir.resolve()
        path = (incoming / req.filename).resolve()
        if path.parent != incoming or path.suffix.lower() != ".csv" or not path.is_file():
            raise HTTPException(400, "Ogiltigt filnamn: endast .csv-filer direkt i data/incoming/ kan importeras.")
        return _save(session, CsvFeed(path).load(), path.name)

    @app.post("/api/datasets/synthetic")
    def synthetic(req: SyntheticRequest, session: Session = Depends(db)):
        return _save(session, SyntheticFeed(req.n_bars, req.seed).load(),
                     f"SYNTETISK seed={req.seed} n={req.n_bars}")

    @app.get("/api/experiments")
    def experiments(session: Session = Depends(db)):
        return [experiment_out(e) for e in list_experiments(session)]

    @app.get("/api/experiments/{experiment_id}")
    def experiment(experiment_id: int, session: Session = Depends(db)):
        e = session.get(Experiment, experiment_id)
        if e is None:
            raise HTTPException(404, f"Experiment {experiment_id} finns inte.")
        return experiment_out(e)

    @app.get("/api/audit")
    def audit_log(limit: int = Query(200, ge=1, le=1_000), session: Session = Depends(db)):
        rows = session.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))
        return [audit_out(a) for a in rows]

    app.include_router(lab_router)
    return app


app = create_app()

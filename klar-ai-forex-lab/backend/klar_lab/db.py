"""Databasanslutning och migrationer (Alembic körs automatiskt vid start)."""
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker

from .settings import BACKEND_DIR


def make_engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


def make_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def run_migrations(url: str) -> None:
    cfg = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(BACKEND_DIR / "alembic")))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

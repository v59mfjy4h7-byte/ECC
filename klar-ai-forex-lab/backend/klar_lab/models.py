"""Databasmodeller. Schemat ändras endast via Alembic-migrationer (alembic/versions)."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    """Ett validerat dataset. Staplarna ligger som normaliserad CSV i data/datasets/<sha256>.csv."""
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    synthetic: Mapped[bool] = mapped_column(Boolean)
    symbol: Mapped[str] = mapped_column(String(16), default="EURUSD")
    timeframe_minutes: Mapped[float | None] = mapped_column()
    bars: Mapped[int] = mapped_column(Integer)
    start: Mapped[datetime] = mapped_column(DateTime)
    end: Mapped[datetime] = mapped_column(DateTime)
    validation: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Experiment(Base):
    """Experimentregister: allt som behövs för att reproducera och granska en körning.

    När status är avslutad (finished/failed/cancelled) får posten inte ändras.
    """
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    data_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_scope: Mapped[str] = mapped_column(String(16), default="full")  # train|validation|test|full
    synthetic_data: Mapped[bool] = mapped_column(Boolean, default=False)
    code_version: Mapped[str] = mapped_column(String(128))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)  # approved|rejected
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    """Revisionslogg som bara tillåter tillägg."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(32))     # human|system|agent:<namn>
    action: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

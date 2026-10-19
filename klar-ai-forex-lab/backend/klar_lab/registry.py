"""Experimentregister och revisionslogg.

Varje experiment sparar data-hash, kodversion, parametrar, slumpfrö, mått och beslut.
Ett avslutat experiment kan inte ändras – nya slutsatser kräver ett nytt experiment.
"""
import hashlib
import os
from pathlib import Path

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from .models import AuditLog, Dataset, Experiment, utcnow
from .settings import APP_VERSION, PACKAGE_DIR

FINAL_STATUSES = {"finished", "failed", "cancelled"}
DECISIONS = {"approved", "rejected"}
SCOPES = {"train", "validation", "test", "full"}


class RegistryError(Exception):
    pass


def code_version(package_dir: Path = PACKAGE_DIR) -> str:
    """Version + hash av all Python-källkod i paketet (fungerar även utan git, t.ex. i Docker).
    GIT_SHA kan anges som miljövariabel för spårbarhet mot commit."""
    h = hashlib.sha256()
    for path in sorted(package_dir.rglob("*.py")):
        h.update(str(path.relative_to(package_dir)).encode())
        h.update(path.read_bytes())
    git = os.environ.get("GIT_SHA", "").strip()
    return f"{APP_VERSION}+src.{h.hexdigest()[:12]}" + (f".git.{git[:12]}" if git else "")


def audit(session: Session, actor: str, action: str, **details) -> AuditLog:
    entry = AuditLog(actor=actor, action=action, details=details)
    session.add(entry)
    return entry


def start_experiment(session: Session, *, kind: str, name: str, params: dict | None = None,
                     seed: int | None = None, dataset: Dataset | None = None, data_scope: str = "full",
                     actor: str = "system") -> Experiment:
    if data_scope not in SCOPES:
        raise RegistryError(f"Okänd dataperiod: {data_scope}")
    exp = Experiment(
        kind=kind, name=name, status="running", params=params or {}, seed=seed, metrics={},
        dataset_id=dataset.id if dataset else None, data_hash=dataset.sha256 if dataset else None,
        synthetic_data=bool(dataset and dataset.synthetic), data_scope=data_scope, code_version=code_version(),
    )
    session.add(exp)
    session.flush()
    audit(session, actor, "experiment_started", experiment_id=exp.id, kind=kind, name=name)
    return exp


def finish_experiment(session: Session, exp: Experiment, *, metrics: dict, decision: str | None = None,
                      decision_reason: str | None = None, actor: str = "system") -> Experiment:
    _ensure_open(exp)
    if decision is not None and decision not in DECISIONS:
        raise RegistryError(f"Okänt beslut: {decision}")
    if decision is not None and not decision_reason:
        raise RegistryError("Ett beslut måste ha en motivering.")
    exp.metrics, exp.decision, exp.decision_reason = metrics, decision, decision_reason
    exp.status, exp.finished_at = "finished", utcnow()
    audit(session, actor, "experiment_finished", experiment_id=exp.id, decision=decision)
    return exp


def fail_experiment(session: Session, exp: Experiment, error: str, actor: str = "system") -> Experiment:
    _ensure_open(exp)
    exp.status, exp.error, exp.finished_at = "failed", error, utcnow()
    audit(session, actor, "experiment_failed", experiment_id=exp.id, error=error)
    return exp


def list_experiments(session: Session, limit: int = 200) -> list[Experiment]:
    return list(session.scalars(select(Experiment).order_by(Experiment.id.desc()).limit(limit)))


def _ensure_open(exp: Experiment) -> None:
    if exp.status in FINAL_STATUSES:
        raise RegistryError(f"Experiment {exp.id} är redan avslutat ({exp.status}) och kan inte ändras.")


@event.listens_for(Session, "before_flush")
def _guard_immutable(session: Session, _ctx, _instances) -> None:
    """Spärr på ORM-nivå: revisionsloggen och avslutade experiment får inte ändras eller raderas."""
    for obj in session.deleted:
        if isinstance(obj, (AuditLog, Experiment)):
            raise RegistryError(f"{type(obj).__name__} får inte raderas.")
    for obj in session.dirty:
        if not session.is_modified(obj):
            continue
        if isinstance(obj, AuditLog):
            raise RegistryError("Revisionsloggen får inte ändras.")
        if isinstance(obj, Experiment):
            hist = inspect(obj).attrs.status.history
            previous = hist.deleted[0] if hist.deleted else obj.status
            if previous in FINAL_STATUSES:
                raise RegistryError(f"Experiment {obj.id} är avslutat och kan inte ändras.")

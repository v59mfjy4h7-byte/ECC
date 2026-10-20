"""JSON-representation av databasobjekt."""
from ..models import AuditLog, Dataset, Experiment


def dataset_out(ds: Dataset) -> dict:
    return {
        "id": ds.id, "name": ds.name, "source": ds.source, "sha256": ds.sha256, "synthetic": ds.synthetic,
        "symbol": ds.symbol, "timeframe_minutes": ds.timeframe_minutes, "bars": ds.bars,
        "start": ds.start.isoformat(), "end": ds.end.isoformat(), "validation": ds.validation,
        "created_at": ds.created_at.isoformat(),
    }


def experiment_out(e: Experiment) -> dict:
    return {
        "id": e.id, "kind": e.kind, "name": e.name, "status": e.status, "dataset_id": e.dataset_id,
        "data_hash": e.data_hash, "data_scope": e.data_scope, "synthetic_data": e.synthetic_data,
        "code_version": e.code_version, "params": e.params, "seed": e.seed, "metrics": e.metrics,
        "decision": e.decision, "decision_reason": e.decision_reason, "error": e.error,
        "created_at": e.created_at.isoformat(), "finished_at": e.finished_at.isoformat() if e.finished_at else None,
    }


def audit_out(a: AuditLog) -> dict:
    return {"id": a.id, "ts": a.ts.isoformat(), "actor": a.actor, "action": a.action, "details": a.details}

import pytest

from klar_lab.db import make_engine, make_sessionmaker, run_migrations
from klar_lab.models import AuditLog, Experiment
from klar_lab.registry import (RegistryError, audit, code_version, fail_experiment, finish_experiment,
                               start_experiment)


@pytest.fixture
def session(settings):
    run_migrations(settings.db_url)
    s = make_sessionmaker(make_engine(settings.db_url))()
    yield s
    s.close()


def test_experiment_lifecycle_records_reproducibility_fields(session):
    exp = start_experiment(session, kind="backtest", name="t", params={"a": 1}, seed=42, data_scope="train")
    finish_experiment(session, exp, metrics={"sharpe": 0.1}, decision="rejected", decision_reason="PF < 1")
    session.commit()
    got = session.get(Experiment, exp.id)
    assert got.status == "finished" and got.params == {"a": 1} and got.seed == 42
    assert got.code_version == code_version() and got.finished_at is not None
    actions = [a.action for a in session.query(AuditLog).order_by(AuditLog.id)]
    assert actions == ["experiment_started", "experiment_finished"]


def test_finished_experiment_is_immutable(session):
    exp = start_experiment(session, kind="backtest", name="t")
    finish_experiment(session, exp, metrics={})
    session.commit()
    with pytest.raises(RegistryError):
        finish_experiment(session, exp, metrics={"x": 1})
    with pytest.raises(RegistryError):
        fail_experiment(session, exp, "x")
    exp.metrics = {"fusk": 1}  # direkt ändring stoppas av ORM-spärren
    with pytest.raises(RegistryError):
        session.flush()
    session.rollback()
    session.delete(session.get(Experiment, exp.id))
    with pytest.raises(RegistryError):
        session.flush()


def test_audit_log_is_append_only(session):
    entry = audit(session, "human", "test")
    session.commit()
    entry.action = "changed"
    with pytest.raises(RegistryError):
        session.flush()
    session.rollback()
    session.delete(entry)
    with pytest.raises(RegistryError):
        session.flush()


def test_decision_requires_reason_and_valid_values(session):
    exp = start_experiment(session, kind="backtest", name="t")
    with pytest.raises(RegistryError):
        finish_experiment(session, exp, metrics={}, decision="approved")
    with pytest.raises(RegistryError):
        finish_experiment(session, exp, metrics={}, decision="maybe", decision_reason="x")
    with pytest.raises(RegistryError):
        start_experiment(session, kind="backtest", name="t", data_scope="framtiden")


def test_code_version_changes_with_source(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    v1 = code_version(tmp_path)
    (tmp_path / "a.py").write_text("x = 2")
    assert code_version(tmp_path) != v1

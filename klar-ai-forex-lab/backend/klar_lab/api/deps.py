"""Gemensamma FastAPI-beroenden."""
from collections.abc import Iterator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from ..models import Dataset


def db(request: Request) -> Iterator[Session]:
    session = request.app.state.sessionmaker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_dataset(session: Session, dataset_id: int) -> Dataset:
    ds = session.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(404, f"Dataset {dataset_id} finns inte.")
    return ds

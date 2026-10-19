import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from klar_lab.settings import Settings  # noqa: E402


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "data", database_url=f"sqlite:///{tmp_path / 'test.db'}",
                    max_upload_mb=5, cors_origins=("http://localhost:5173",))


@pytest.fixture
def client(settings):
    from fastapi.testclient import TestClient

    from klar_lab.api.main import create_app

    with TestClient(create_app(settings)) as c:
        yield c

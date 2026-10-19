"""Globala inställningar. Läses från miljövariabler (se .env.example).

LIVE_TRADING_ENABLED är en hård konstant, inte en miljövariabel: plattformen
innehåller ingen kod för riktiga order och ett test verifierar att värdet är False.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

LIVE_TRADING_ENABLED = False

APP_VERSION = "0.1.0"
PACKAGE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PACKAGE_DIR.parent


def _default_data_dir() -> Path:
    return BACKEND_DIR.parent / "data"


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("KLAR_DATA_DIR", _default_data_dir())))
    database_url: str = field(default_factory=lambda: os.environ.get("KLAR_DATABASE_URL", ""))
    max_upload_mb: int = field(default_factory=lambda: int(os.environ.get("KLAR_MAX_UPLOAD_MB", "200")))
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        o.strip() for o in os.environ.get("KLAR_CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
    ))

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'klar_lab.db'}"

    @property
    def incoming_dir(self) -> Path:
        """Här kan användaren lägga stora CSV-filer för import utan uppladdning."""
        return self.data_dir / "incoming"

    @property
    def datasets_dir(self) -> Path:
        """Normaliserade, validerade kopior av importerade dataset (namn = SHA-256)."""
        return self.data_dir / "datasets"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.incoming_dir, self.datasets_dir):
            d.mkdir(parents=True, exist_ok=True)

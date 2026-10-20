"""Signerad riskkonfiguration (HMAC-SHA256).

Bara den som har nyckeln (KLAR_RISK_SIGNING_KEY, sätts av människan i .env) kan ändra gränserna.
Även en signerad fil får bara göra gränserna STRÄNGARE än specifikationens tak nedan.

Signera en ny konfiguration (från backend/):
    KLAR_RISK_SIGNING_KEY=... python -m klar_lab.risk.signing min_config.json --by "Namn"
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import LabConfig

KEY_ENV = "KLAR_RISK_SIGNING_KEY"

# Specifikationens gränser: får skärpas men aldrig lättas, inte ens av en signerad fil.
CEILINGS = {"risk_per_trade": 0.01, "max_daily_loss": 0.03, "max_drawdown": 0.20, "max_leverage": 10.0}
FLOORS = {"min_reward_risk": 2.0}


class RiskConfigError(Exception):
    pass


def _canonical(config: dict) -> bytes:
    return json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(config: dict, key: str) -> str:
    return hmac.new(key.encode("utf-8"), _canonical(config), hashlib.sha256).hexdigest()


def check_limits(cfg: LabConfig) -> None:
    r = cfg.risk
    for name, ceiling in CEILINGS.items():
        if getattr(r, name) > ceiling:
            raise RiskConfigError(f"{name}={getattr(r, name)} överskrider specifikationens tak {ceiling}.")
    for name, floor in FLOORS.items():
        if getattr(r, name) < floor:
            raise RiskConfigError(f"{name}={getattr(r, name)} understiger specifikationens golv {floor}.")
    c = cfg.costs
    if min(c.spread_pips, c.slippage_pips, c.commission_usd_per_100k) < 0:
        raise RiskConfigError("Kostnader kan inte vara negativa.")


def load_lab_config(path: Path, key: str | None = None) -> tuple[LabConfig, dict]:
    """Returnerar (konfiguration, status). Saknas filen gäller standardvärdena."""
    if not path.exists():
        cfg = LabConfig()
        return cfg, {"source": "default", "signed_by": None, "signed_at": None}
    key = key if key is not None else os.environ.get(KEY_ENV, "")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        config, signature = doc["config"], doc["signature"]
    except (ValueError, KeyError) as exc:
        raise RiskConfigError(f"Riskkonfigurationen {path} är trasig: {exc}")
    if not key:
        raise RiskConfigError(f"{path} finns men {KEY_ENV} är inte satt; signaturen kan inte kontrolleras.")
    if not hmac.compare_digest(sign(config, key), str(signature)):
        raise RiskConfigError(f"Ogiltig signatur på {path}. Filen har ändrats utan giltig signering.")
    try:
        cfg = LabConfig.from_dict(config)
    except (TypeError, ValueError) as exc:
        raise RiskConfigError(str(exc))
    check_limits(cfg)
    return cfg, {"source": "signed", "signed_by": doc.get("signed_by"), "signed_at": doc.get("signed_at")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Signera en riskkonfiguration (endast för människor).")
    ap.add_argument("config", type=Path, help="JSON med sektionerna account/costs/risk")
    ap.add_argument("--by", required=True, help="vem som godkänner ändringen")
    ap.add_argument("--out", type=Path, default=None, help="standard: <KLAR_DATA_DIR>/config/risk_limits.json")
    args = ap.parse_args(argv)
    key = os.environ.get(KEY_ENV, "")
    if len(key) < 16:
        print(f"FEL: sätt {KEY_ENV} (minst 16 tecken).", file=sys.stderr)
        return 2
    config = json.loads(args.config.read_text(encoding="utf-8"))
    cfg = LabConfig.from_dict(config)
    check_limits(cfg)
    full = cfg.to_dict()
    if args.out is None:
        from ..settings import Settings
        args.out = Settings().config_dir / "risk_limits.json"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"config": full, "signature": sign(full, key), "signed_by": args.by,
           "signed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Signerad konfiguration skriven till {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

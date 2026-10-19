"""Absoluta regler: ingen livehandel, ingen mäklarkod."""
from pathlib import Path

from klar_lab import settings

PACKAGE = Path(settings.__file__).resolve().parent

FORBIDDEN = ["import requests", "import socket", "urllib", "http.client", "oanda", "metatrader",
             "ccxt", "ib_insync", "websocket", "smtplib", "place_order", "submit_order"]


def test_live_trading_disabled():
    assert settings.LIVE_TRADING_ENABLED is False


def test_no_network_or_broker_code_in_package():
    for path in PACKAGE.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN:
            assert word not in text, f"{path.relative_to(PACKAGE)} innehåller '{word}'"


def test_live_trading_flag_not_configurable_from_env(monkeypatch):
    import importlib

    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("KLAR_LIVE_TRADING_ENABLED", "true")
    assert importlib.reload(settings).LIVE_TRADING_ENABLED is False

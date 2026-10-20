"""Gemensamt Strategy-interface med deklarativa parametrar.

En strategi definieras av sin klass (nyckel) + en parameterdict. Agent E (M4) kan bara skapa
varianter genom att välja parametrar inom de deklarerade intervallen – aldrig genom att köra kod.
Strategier FÖRESLÅR affärer (riktning + stop/TP-avstånd); riskmotorn beslutar.
"""
import hashlib
import json
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .indicators import atr


@dataclass(frozen=True)
class Param:
    name: str
    kind: str            # "int" | "float"
    default: float
    low: float
    high: float
    description: str = ""

    def coerce(self, value) -> int | float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{self.name}: måste vara ett tal")
        if self.kind == "int":
            if float(value) != int(value):
                raise ValueError(f"{self.name}: måste vara ett heltal")
            value = int(value)
        else:
            value = float(value)
        if not self.low <= value <= self.high:
            raise ValueError(f"{self.name}={value} utanför tillåtet intervall [{self.low}, {self.high}]")
        return value


@dataclass(frozen=True)
class Signal:
    direction: int          # 1 = köp, -1 = sälj
    stop_distance: float    # prisavstånd
    take_profit_distance: float
    reason: str = ""


COMMON_PARAMS = (
    Param("atr_period", "int", 14, 5, 50, "ATR-period för stop-avstånd"),
    Param("sl_atr_mult", "float", 2.0, 0.5, 5.0, "stop-avstånd = sl_atr_mult × ATR"),
    Param("reward_multiple", "float", 2.5, 1.5, 6.0, "TP-avstånd = reward_multiple × stop-avstånd"),
)


class Strategy:
    key = "base"
    title = ""
    description = ""
    own_params: tuple[Param, ...] = ()
    defaults: dict = {}            # klass-specifika standardvärden för gemensamma parametrar

    @classmethod
    def param_specs(cls) -> tuple[Param, ...]:
        common = tuple(Param(p.name, p.kind, cls.defaults.get(p.name, p.default), p.low, p.high, p.description)
                       for p in COMMON_PARAMS)
        return common + cls.own_params

    def __init__(self, **params):
        specs = {p.name: p for p in self.param_specs()}
        unknown = set(params) - set(specs)
        if unknown:
            raise ValueError(f"Okända parametrar för {self.key}: {sorted(unknown)}")
        self.params = {name: spec.coerce(params.get(name, spec.default)) for name, spec in specs.items()}
        self.atr = self.long = self.short = None

    @property
    def config(self) -> dict:
        return {"strategy": self.key, "params": self.params}

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.config, sort_keys=True).encode()).hexdigest()[:16]

    @property
    def name(self) -> str:
        return self.key

    def prepare(self, df: pd.DataFrame) -> None:
        long_, short_ = self.compute(df)
        self.atr = atr(df, self.params["atr_period"]).to_numpy()
        self.long = long_.fillna(False).to_numpy(dtype=bool)
        self.short = short_.fillna(False).to_numpy(dtype=bool)

    def compute(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        raise NotImplementedError

    def signal(self, i: int) -> Signal | None:
        a = self.atr[i]
        if not np.isfinite(a) or a <= 0:
            return None
        lg, sh = self.long[i], self.short[i]
        if lg == sh:
            return None
        sl = self.params["sl_atr_mult"] * a
        return Signal(1 if lg else -1, sl, self.params["reward_multiple"] * sl, self.key)

    @classmethod
    def describe(cls) -> dict:
        return {"key": cls.key, "title": cls.title, "description": cls.description,
                "params": [asdict(p) for p in cls.param_specs()]}

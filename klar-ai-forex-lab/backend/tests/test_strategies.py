import ast
from pathlib import Path

import numpy as np
import pytest

from klar_lab.data.synthetic import generate_synthetic
from klar_lab.strategies import STRATEGIES, baseline, build

STRAT_DIR = Path(__file__).resolve().parent.parent / "klar_lab" / "strategies"


def test_strategies_are_causal():
    df = generate_synthetic(4_000, seed=1)
    for s in baseline():
        s.prepare(df)
        full = (s.long.copy(), s.short.copy(), s.atr.copy())
        s.prepare(df.iloc[:2_500])
        np.testing.assert_array_equal(s.long, full[0][:2_500], err_msg=s.key)
        np.testing.assert_array_equal(s.short, full[1][:2_500], err_msg=s.key)
        np.testing.assert_array_equal(s.atr, full[2][:2_500], err_msg=s.key)


def test_signals_have_positive_distances_and_reward_above_stop():
    df = generate_synthetic(4_000, seed=2)
    for s in baseline():
        s.prepare(df)
        sigs = [x for i in range(len(df)) if (x := s.signal(i))]
        assert sigs, s.key
        assert all(x.stop_distance > 0 and x.take_profit_distance > x.stop_distance for x in sigs)


def test_params_are_declarative_and_validated():
    s = build("A_trend", {"fast": 10, "slow": 30.0})
    assert s.params["fast"] == 10 and isinstance(s.params["slow"], int)
    with pytest.raises(ValueError, match="utanför"):
        build("A_trend", {"fast": 1})
    with pytest.raises(ValueError, match="Okända"):
        build("A_trend", {"exec": 1})
    with pytest.raises(ValueError, match="heltal"):
        build("A_trend", {"fast": 10.5})
    with pytest.raises(ValueError, match="Okänd strategi"):
        build("Z", {})
    assert build("B_momentum").params["sl_atr_mult"] == 1.5


def test_config_hash_depends_on_params():
    assert build("A_trend").config_hash == build("A_trend").config_hash
    assert build("A_trend").config_hash != build("A_trend", {"fast": 21}).config_hash


def test_describe_lists_all_params():
    for cls in STRATEGIES.values():
        d = cls.describe()
        assert {"atr_period", "sl_atr_mult", "reward_multiple"} <= {p["name"] for p in d["params"]}


def test_strategies_cannot_import_risk_or_engine():
    """Strategier föreslår bara; de får inte nå riskmotorn, motorn eller databasen."""
    for path in STRAT_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = ("." * node.level) + (node.module or "")
                assert not any(x in mod for x in ("risk", "engine", "models", "registry", "db")), (path.name, mod)
            if isinstance(node, ast.Import):
                assert not any("klar_lab" in a.name for a in node.names), path.name

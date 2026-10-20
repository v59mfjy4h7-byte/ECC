import json

import pytest

from klar_lab.risk import LabConfig, RiskConfigError, load_lab_config
from klar_lab.risk.signing import main as sign_main
from klar_lab.risk.signing import sign

KEY = "a-very-secret-human-key"


def write_signed(path, config, key=KEY):
    path.write_text(json.dumps({"config": config, "signature": sign(config, key), "signed_by": "Test"}))


def test_missing_file_uses_defaults(tmp_path):
    cfg, status = load_lab_config(tmp_path / "risk_limits.json", KEY)
    assert cfg == LabConfig() and status["source"] == "default"


def test_valid_signature_loads_stricter_limits(tmp_path):
    conf = LabConfig().to_dict()
    conf["risk"]["risk_per_trade"] = 0.005
    write_signed(tmp_path / "r.json", conf)
    cfg, status = load_lab_config(tmp_path / "r.json", KEY)
    assert cfg.risk.risk_per_trade == 0.005 and status["source"] == "signed" and status["signed_by"] == "Test"


def test_tampered_or_unsigned_file_is_rejected(tmp_path):
    conf = LabConfig().to_dict()
    write_signed(tmp_path / "r.json", conf)
    doc = json.loads((tmp_path / "r.json").read_text())
    doc["config"]["risk"]["risk_per_trade"] = 0.009
    (tmp_path / "r.json").write_text(json.dumps(doc))
    with pytest.raises(RiskConfigError, match="signatur"):
        load_lab_config(tmp_path / "r.json", KEY)
    with pytest.raises(RiskConfigError, match="inte satt"):
        load_lab_config(tmp_path / "r.json", "")
    write_signed(tmp_path / "w.json", conf, key="another-key-entirely")
    with pytest.raises(RiskConfigError):
        load_lab_config(tmp_path / "w.json", KEY)


@pytest.mark.parametrize("field,value", [("risk_per_trade", 0.02), ("min_reward_risk", 1.5),
                                         ("max_drawdown", 0.5), ("max_leverage", 30.0), ("max_daily_loss", 0.1)])
def test_even_signed_config_cannot_loosen_spec_limits(tmp_path, field, value):
    conf = LabConfig().to_dict()
    conf["risk"][field] = value
    write_signed(tmp_path / "r.json", conf)
    with pytest.raises(RiskConfigError, match="specifikationens"):
        load_lab_config(tmp_path / "r.json", KEY)


def test_unknown_keys_rejected(tmp_path):
    conf = LabConfig().to_dict()
    conf["risk"]["risk_per_trad"] = 0.005
    write_signed(tmp_path / "r.json", conf)
    with pytest.raises(RiskConfigError, match="Okända"):
        load_lab_config(tmp_path / "r.json", KEY)


def test_cli_signs_file(tmp_path, monkeypatch):
    src = tmp_path / "in.json"
    src.write_text(json.dumps({"costs": {"spread_pips": 1.0}}))
    out = tmp_path / "out.json"
    monkeypatch.setenv("KLAR_RISK_SIGNING_KEY", KEY)
    assert sign_main([str(src), "--by", "Människa", "--out", str(out)]) == 0
    cfg, _ = load_lab_config(out, KEY)
    assert cfg.costs.spread_pips == 1.0
    monkeypatch.setenv("KLAR_RISK_SIGNING_KEY", "short")
    assert sign_main([str(src), "--by", "x", "--out", str(out)]) == 2

import json

from klar_lab.risk import LabConfig


def make_dataset(client, n=6_000, seed=5):
    return client.post("/api/datasets/synthetic", json={"n_bars": n, "seed": seed}).json()["dataset"]


def test_strategies_and_config_endpoints(client):
    keys = [s["key"] for s in client.get("/api/strategies").json()]
    assert keys == ["A_trend", "B_momentum", "C_mean_reversion", "D_breakout"]
    cfg = client.get("/api/config").json()
    assert cfg["status"]["source"] == "default" and cfg["config"]["risk"]["risk_per_trade"] == 0.01
    assert cfg["kill_switch_active"] is False


def test_baseline_backtest_runs_train_and_validation_only(client):
    ds = make_dataset(client)
    exps = client.post("/api/backtests", json={"dataset_id": ds["id"]}).json()
    assert len(exps) == 8
    assert {e["data_scope"] for e in exps} == {"train", "validation"}
    for e in exps:
        assert e["status"] == "finished" and e["synthetic_data"] and e["data_hash"] == ds["sha256"]
        assert "expectancy" in e["metrics"] and e["params"]["config_hash"]
        assert e["params"]["lab_config"]["risk"]["risk_per_trade"] == 0.01
    eq = client.get(f"/api/experiments/{exps[0]['id']}/artifacts/equity").json()
    assert eq and "equity" in eq[0]
    client.get(f"/api/experiments/{exps[0]['id']}/artifacts/trades")
    assert client.get(f"/api/experiments/{exps[0]['id']}/artifacts/../../secret").status_code in (404, 422)
    assert client.get(f"/api/experiments/{exps[0]['id']}/artifacts/passwd").status_code == 404


def test_test_period_locked_and_opens_once(client):
    ds = make_dataset(client)
    body = {"dataset_id": ds["id"], "strategies": [{"key": "D_breakout"}], "periods": ["test"]}
    assert client.post("/api/backtests", json=body).status_code == 400
    r = client.post("/api/backtests", json={**body, "confirm_test_access": True})
    assert r.status_code == 200 and r.json()[0]["data_scope"] == "test"
    assert client.post("/api/backtests", json={**body, "confirm_test_access": True}).status_code == 409
    access = client.get("/api/backtests/test-access", params={"dataset_id": ds["id"]}).json()
    assert access["D_breakout"] is True and access["A_trend"] is False
    # En ny konfiguration är en ny kandidat
    other = {**body, "strategies": [{"key": "D_breakout", "params": {"lookback": 41}}], "confirm_test_access": True}
    assert client.post("/api/backtests", json=other).status_code == 200
    assert any(a["action"] == "test_period_opened" for a in client.get("/api/audit").json())


def test_invalid_params_rejected(client):
    ds = make_dataset(client)
    r = client.post("/api/backtests", json={"dataset_id": ds["id"], "strategies": [{"key": "A_trend",
                                                                                     "params": {"fast": 1}}]})
    assert r.status_code == 422


def test_kill_switch_blocks_all_new_trades(client):
    ds = make_dataset(client)
    assert client.post("/api/kill-switch", json={"active": True}).json()["kill_switch_active"]
    exps = client.post("/api/backtests", json={"dataset_id": ds["id"], "strategies": [{"key": "B_momentum"}],
                                               "periods": ["train"]}).json()
    assert exps[0]["metrics"]["trades"] == 0 and exps[0]["metrics"]["rejected_orders"] > 0
    decisions = client.get(f"/api/experiments/{exps[0]['id']}/artifacts/decisions").json()
    assert {d["reason"] for d in decisions} == {"kill_switch_aktiv"}
    assert client.post("/api/kill-switch", json={"active": False}).status_code == 400
    assert client.post("/api/kill-switch", json={"active": False, "confirm": True}).json()["kill_switch_active"] is False


def test_invalid_signed_config_blocks_backtests(settings, monkeypatch):
    from fastapi.testclient import TestClient

    from klar_lab.api.main import create_app

    settings.ensure_dirs()
    (settings.config_dir / "risk_limits.json").write_text(json.dumps(
        {"config": LabConfig().to_dict(), "signature": "forged"}))
    monkeypatch.setenv("KLAR_RISK_SIGNING_KEY", "a-very-secret-human-key")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/config").json()["error"]
        ds = make_dataset(client, 2_000)
        assert client.post("/api/backtests", json={"dataset_id": ds["id"]}).status_code == 503

from tests.helpers import h1_bars, to_csv_bytes


def test_health_reports_live_trading_disabled(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["live_trading_enabled"] is False


def test_upload_valid_csv_creates_dataset_experiment_and_audit(client):
    r = client.post("/api/datasets/upload", files={"file": ("eurusd.csv", to_csv_bytes(h1_bars()), "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] and body["dataset"]["bars"] == 1_200 and not body["dataset"]["synthetic"]
    # samma data igen -> samma dataset
    again = client.post("/api/datasets/upload", files={"file": ("x.csv", to_csv_bytes(h1_bars()), "text/csv")})
    assert again.json()["created"] is False and again.json()["dataset"]["id"] == body["dataset"]["id"]

    exps = client.get("/api/experiments").json()
    assert len(exps) == 1 and exps[0]["kind"] == "data_validation"
    assert exps[0]["data_hash"] == body["dataset"]["sha256"] and exps[0]["decision"] == "approved"
    actions = {a["action"] for a in client.get("/api/audit").json()}
    assert {"dataset_imported", "experiment_started", "experiment_finished"} <= actions


def test_invalid_csv_rejected_with_report_and_nothing_stored(client):
    df = h1_bars()
    df.iloc[3, 0] = -5
    r = client.post("/api/datasets/upload", files={"file": ("bad.csv", to_csv_bytes(df), "text/csv")})
    assert r.status_code == 422
    assert any(i["code"] == "non_positive_prices" for i in r.json()["report"]["issues"])
    assert client.get("/api/datasets").json() == []


def test_upload_size_limit(client):
    big = b"x" * (5 * 1024 * 1024 + 10)
    assert client.post("/api/datasets/upload", files={"file": ("big.csv", big, "text/csv")}).status_code == 413


def test_synthetic_dataset_is_flagged_and_bars_downsampled(client):
    ds = client.post("/api/datasets/synthetic", json={"n_bars": 5_000, "seed": 3}).json()["dataset"]
    assert ds["synthetic"] is True
    r = client.get(f"/api/datasets/{ds['id']}/bars", params={"max_points": 500}).json()
    assert r["synthetic"] is True and r["aggregated"] is True and len(r["bars"]) <= 500
    assert r["bars_in_range"] == 5_000
    first = r["bars"][0]
    assert first["low"] <= min(first["open"], first["close"]) <= max(first["open"], first["close"]) <= first["high"]


def test_bars_range_filter_and_404(client):
    ds = client.post("/api/datasets/synthetic", json={"n_bars": 2_000, "seed": 1}).json()["dataset"]
    r = client.get(f"/api/datasets/{ds['id']}/bars",
                   params={"start": "2019-01-07T00:00:00", "end": "2019-01-07T23:00:00"}).json()
    assert r["bars_in_range"] == 24 and not r["aggregated"]
    assert client.get("/api/datasets/999").status_code == 404
    assert client.get("/api/experiments/999").status_code == 404


def test_import_from_incoming_and_path_traversal_blocked(client, settings):
    (settings.incoming_dir / "eurusd_h1.csv").write_bytes(to_csv_bytes(h1_bars()))
    (settings.data_dir / "secret.csv").write_text("x")
    assert [f["filename"] for f in client.get("/api/datasets/incoming").json()] == ["eurusd_h1.csv"]
    assert client.post("/api/datasets/import", json={"filename": "eurusd_h1.csv"}).status_code == 200
    for bad in ("../secret.csv", "/etc/passwd", "..\\secret.csv", "klar_lab.db"):
        assert client.post("/api/datasets/import", json={"filename": bad}).status_code == 400, bad

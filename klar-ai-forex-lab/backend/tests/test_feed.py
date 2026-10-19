import pytest

from klar_lab.data import CsvFeed, DataValidationError, SyntheticFeed, dataset_hash, parse_csv
from tests.helpers import h1_bars, to_csv_bytes


def test_csv_roundtrip_and_hash_is_format_independent():
    df = h1_bars()
    a = CsvFeed(to_csv_bytes(df)).load()
    # Annan formatering (semikolon, MT-stil kolumner) ska ge samma hash
    mt = df.copy()
    mt.insert(0, "<DATE>", mt.index.strftime("%Y.%m.%d"))
    mt.insert(1, "<TIME>", mt.index.strftime("%H:%M"))
    mt.columns = ["<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>"]
    b = CsvFeed(mt.to_csv(index=False, sep=";").encode()).load()
    assert a.sha256 == b.sha256 == dataset_hash(df)
    assert not a.synthetic


def test_timezone_aware_times_converted_to_utc():
    text = "time,open,high,low,close\n2024-01-02T10:00:00+01:00,1.1,1.1,1.1,1.1\n"
    df = parse_csv(text)
    assert str(df.index[0]) == "2024-01-02 09:00:00"


def test_missing_file_and_bad_csv_give_clear_errors(tmp_path):
    with pytest.raises(DataValidationError, match="finns inte"):
        CsvFeed(tmp_path / "nope.csv").load()
    with pytest.raises(DataValidationError, match="tidskolumn"):
        parse_csv("a,b\n1,2\n")
    with pytest.raises(DataValidationError, match="Saknade kolumner"):
        parse_csv("time,open\n2024-01-01,1.1\n")
    with pytest.raises(DataValidationError, match="tidsstämplar"):
        parse_csv("time,open,high,low,close\nnot-a-date,1,1,1,1\n")


def test_synthetic_is_flagged_and_deterministic():
    a, b = SyntheticFeed(2_000, seed=7).load(), SyntheticFeed(2_000, seed=7).load()
    assert a.synthetic and "SYNTETISK" in a.source
    assert a.sha256 == b.sha256
    assert SyntheticFeed(2_000, seed=8).load().sha256 != a.sha256

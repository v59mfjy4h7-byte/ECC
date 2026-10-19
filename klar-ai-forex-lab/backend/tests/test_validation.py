from datetime import datetime, timedelta

import pandas as pd
import pytest

from klar_lab.data import DataValidationError, ValidationConfig, check_staleness, validate_bars
from tests.helpers import h1_bars


def codes(rep):
    return {i.code for i in rep.issues}


def test_clean_data_passes_without_issues():
    df, rep = validate_bars(h1_bars())
    assert rep.ok and rep.issues == [] and rep.bars == 1_200
    assert rep.timeframe_minutes == 60
    assert rep.gaps == 0  # helger räknas inte som luckor


def test_nan_is_error():
    df = h1_bars()
    df.iloc[5, 0] = float("nan")
    with pytest.raises(DataValidationError) as exc:
        validate_bars(df)
    assert "nan_prices" in codes(exc.value.report)


def test_non_positive_and_out_of_range_are_errors():
    df = h1_bars()
    df.iloc[3] = [-1, -1, -1, -1]
    df.iloc[4] = [3.0, 3.0, 3.0, 3.0]
    with pytest.raises(DataValidationError) as exc:
        validate_bars(df)
    assert {"non_positive_prices", "price_out_of_range"} <= codes(exc.value.report)


def test_inconsistent_high_low_is_error():
    df = h1_bars()
    df.iloc[10, df.columns.get_loc("high")] = df.iloc[10]["low"] - 0.001
    with pytest.raises(DataValidationError) as exc:
        validate_bars(df)
    assert "inconsistent_high_low" in codes(exc.value.report)


def test_identical_duplicates_removed_with_warning():
    df = h1_bars()
    df = pd.concat([df, df.iloc[[7, 8]]]).sort_index()
    out, rep = validate_bars(df)
    assert rep.duplicates_removed == 2 and len(out) == 1_200
    assert "duplicates_removed" in codes(rep) and rep.ok


def test_conflicting_duplicates_are_error():
    df = h1_bars()
    dup = df.iloc[[7]].copy()
    dup["close"] += 0.0001
    dup["high"] += 0.0001
    with pytest.raises(DataValidationError) as exc:
        validate_bars(pd.concat([df, dup]))
    assert "conflicting_duplicates" in codes(exc.value.report)


def test_unsorted_is_sorted_with_warning():
    df = h1_bars().iloc[::-1]
    out, rep = validate_bars(df)
    assert out.index.is_monotonic_increasing and rep.sorted


def test_midweek_gap_is_warning_and_long_gap_is_error():
    df = h1_bars(2_000)
    # Tisdag 2024-01-09 10:00–15:00 saknas -> varning
    gap = df.drop(df.loc["2024-01-09 10:00":"2024-01-09 15:00"].index)
    _, rep = validate_bars(gap)
    assert rep.gaps == 1 and "gaps" in codes(rep) and rep.ok
    # Två veckor saknas -> fel
    long_gap = df.drop(df.loc["2024-01-15":"2024-01-29"].index)
    with pytest.raises(DataValidationError) as exc:
        validate_bars(long_gap)
    assert "long_gap" in codes(exc.value.report)


def test_spike_is_warning():
    df = h1_bars()
    df.iloc[100] = [1.10, 1.20, 1.10, 1.20]
    _, rep = validate_bars(df)
    assert "price_spikes" in codes(rep)


def test_too_few_bars_is_error():
    with pytest.raises(DataValidationError):
        validate_bars(h1_bars(500))
    _, rep = validate_bars(h1_bars(500), ValidationConfig(min_bars=100))
    assert rep.ok


def test_flat_bars_warning():
    df = h1_bars()
    df.iloc[:200] = 1.1
    _, rep = validate_bars(df)
    assert "flat_bars" in codes(rep)


def test_staleness():
    now = datetime(2024, 1, 10, 12)
    assert check_staleness(now - timedelta(hours=3), now, timedelta(hours=2))
    assert not check_staleness(now - timedelta(minutes=30), now, timedelta(hours=2))

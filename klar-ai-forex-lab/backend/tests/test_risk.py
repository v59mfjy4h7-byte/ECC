"""Riskregler (portade från prototypen + nya kontroller)."""
import dataclasses

import pytest

from klar_lab.risk import AccountState, LabConfig, RiskManager

CFG = LabConfig()


@pytest.fixture
def rm():
    return RiskManager(CFG)


@pytest.fixture
def state():
    return AccountState.new(10_000)


def test_sizing_risks_at_most_one_percent(rm, state):
    d = rm.evaluate(1.10, 0.0020, 0.0050, state)
    assert d.approved and 50 < d.risk_amount <= 100 + 1e-9
    assert d.units % CFG.risk.lot_step == 0


def test_rejects_low_reward_risk(rm, state):
    d = rm.evaluate(1.10, 0.0020, 0.0030, state)
    assert not d.approved and d.reason.startswith("rr_for_lag")


def test_rr_is_net_of_costs(rm, state):
    # Brutto-RR exakt 2.0 men netto under 2 på grund av spread/slippage
    assert not rm.evaluate(1.10, 0.0020, 0.0040, state).approved


@pytest.mark.parametrize("sl", [0, -1, float("nan"), None, float("inf")])
def test_invalid_stop(rm, state, sl):
    assert not rm.evaluate(1.10, sl, 0.005, state).approved


def test_stop_too_tight_and_too_wide(rm, state):
    assert rm.evaluate(1.10, 0.0002, 0.0006, state).reason == "stop_for_tajt"
    assert rm.evaluate(1.10, 0.0300, 0.0900, state).reason == "stop_for_lang"


def test_kill_switch_flag_and_file(tmp_path, state):
    rm = RiskManager(CFG)
    rm.kill_switch = True
    assert rm.evaluate(1.10, 0.0020, 0.0050, state).reason == "kill_switch_aktiv"
    stop = tmp_path / "STOP"
    rm = RiskManager(CFG, stop)
    assert rm.evaluate(1.10, 0.0020, 0.0050, state).approved
    stop.write_text("x")
    assert rm.evaluate(1.10, 0.0020, 0.0050, state).reason == "kill_switch_aktiv"


def test_daily_loss_limit(rm, state):
    state.day_start_balance, state.balance = 10_000, 9_600
    assert rm.evaluate(1.10, 0.0020, 0.0050, state).reason == "daglig_forlustgrans"


def test_drawdown_halts_permanently(rm, state):
    state.balance, state.peak_balance, state.day_start_balance = 7_900, 10_000, 7_900
    assert not rm.evaluate(1.10, 0.0020, 0.0050, state).approved and state.halted
    state.balance = 12_000
    assert rm.evaluate(1.10, 0.0020, 0.0050, state).reason == "konto_stoppat_max_nedgang"


def test_stale_data_and_bad_price(rm, state):
    assert rm.evaluate(1.10, 0.002, 0.005, state, gap_hours=500).reason == "foraldrade_marknadsdata"
    assert rm.evaluate(float("nan"), 0.002, 0.005, state).reason == "ogiltigt_pris"
    assert rm.evaluate(150.0, 0.002, 0.005, state).reason == "ogiltigt_pris"


def test_exposure_cap_only_reduces_size(state):
    cfg = LabConfig(risk=dataclasses.replace(CFG.risk, max_leverage=2.0))
    d = RiskManager(cfg).evaluate(1.10, 0.0020, 0.0050, state)
    assert d.approved and d.units * 1.10 * cfg.account.usd_to_account <= 2 * 10_000
    assert d.units < RiskManager(CFG).evaluate(1.10, 0.0020, 0.0050, AccountState.new(10_000)).units


def test_duplicate_order_and_open_position_rejected(rm, state):
    assert rm.evaluate(1.10, 0.0020, 0.0050, state, order_id="A:1").approved
    assert rm.evaluate(1.10, 0.0020, 0.0050, state, order_id="A:1").reason == "dubbelorder"
    state.open_positions = 1
    assert rm.evaluate(1.10, 0.0020, 0.0050, state, order_id="A:2").reason == "max_antal_positioner"


def test_commission_included_in_planned_risk(state):
    cfg = LabConfig(costs=dataclasses.replace(CFG.costs, commission_usd_per_100k=7.0))
    d = RiskManager(cfg).evaluate(1.10, 0.0020, 0.0050, state)
    assert d.approved and d.risk_amount <= 100 + 1e-9

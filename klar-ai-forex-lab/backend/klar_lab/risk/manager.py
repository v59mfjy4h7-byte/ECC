"""Riskmotor (portad från prototypen). Strategier föreslår, riskmotorn beslutar.

Alla avstånd är i pris (inte pips). Kostnadsmodell (staplar tolkas som BID-priser):
  Long : entry = open + spread + slip ; stop fyller på stop - slip ; TP fyller på TP
  Short: entry = open - slip         ; stop fyller på stop + spread + slip ; TP fyller på TP + spread
Planerad risk/enhet   = stop_dist + spread + 2*slip   (+ ev. provision)
Planerad vinst/enhet  = tp_dist  - spread - slip
Swap ingår inte i planerad risk (den beror på hur länge positionen hålls) men dras i backtesten.
"""
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .config import PIP, LabConfig


@dataclass(frozen=True)
class Decision:
    approved: bool
    reason: str
    units: int = 0
    risk_amount: float = 0.0   # planerad förlust i kontovaluta vid stop-loss
    reward_risk: float = 0.0


@dataclass
class AccountState:
    balance: float
    peak_balance: float
    day: date | None = None
    day_start_balance: float = 0.0
    halted: bool = False
    open_positions: int = 0
    seen_orders: set[str] = field(default_factory=set)

    @classmethod
    def new(cls, balance: float) -> "AccountState":
        return cls(balance=balance, peak_balance=balance, day_start_balance=balance)

    def roll_day(self, day: date) -> None:
        self.day = day
        self.day_start_balance = self.balance

    def apply_pnl(self, pnl: float) -> None:
        self.balance += pnl
        self.peak_balance = max(self.peak_balance, self.balance)


def _valid(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0


class RiskManager:
    def __init__(self, cfg: LabConfig, kill_switch_file: Path | None = None):
        self.cfg = cfg
        self.kill_switch_file = kill_switch_file
        self.kill_switch = False  # kan sättas direkt för omedelbart stopp av nya affärer

    def planned_risk_distance(self, sl_dist: float) -> float:
        c = self.cfg.costs
        return sl_dist + c.spread + 2 * c.slippage

    def planned_reward_distance(self, tp_dist: float) -> float:
        c = self.cfg.costs
        return tp_dist - c.spread - c.slippage

    def commission_per_unit(self) -> float:
        return self.cfg.costs.commission_usd_per_100k / 100_000 * self.cfg.account.usd_to_account

    def kill_switch_active(self) -> bool:
        return self.kill_switch or bool(self.kill_switch_file and self.kill_switch_file.exists())

    def evaluate(self, ref_price: float, sl_dist: float, tp_dist: float, state: AccountState,
                 gap_hours: float = 0.0, order_id: str | None = None) -> Decision:
        """Kontrollerna körs i ordning; första som slår till avgör orsaken."""
        r, a = self.cfg.risk, self.cfg.account

        if self.kill_switch_active():
            return Decision(False, "kill_switch_aktiv")
        if order_id is not None:
            if order_id in state.seen_orders:
                return Decision(False, "dubbelorder")
            state.seen_orders.add(order_id)
        if state.halted:
            return Decision(False, "konto_stoppat_max_nedgang")
        if state.peak_balance > 0 and (state.peak_balance - state.balance) / state.peak_balance >= r.max_drawdown:
            state.halted = True
            return Decision(False, "max_nedgang_overskriden")
        if state.day_start_balance > 0 and \
                (state.day_start_balance - state.balance) / state.day_start_balance >= r.max_daily_loss:
            return Decision(False, "daglig_forlustgrans")
        if state.balance <= 0:
            return Decision(False, "inget_saldo")
        if state.open_positions >= r.max_open_positions:
            return Decision(False, "max_antal_positioner")

        if not (isinstance(ref_price, (int, float)) and math.isfinite(ref_price)
                and r.price_min <= ref_price <= r.price_max):
            return Decision(False, "ogiltigt_pris")
        if gap_hours > r.max_bar_gap_hours:
            return Decision(False, "foraldrade_marknadsdata")

        if not _valid(sl_dist):
            return Decision(False, "stop_loss_saknas_eller_ogiltig")
        if not _valid(tp_dist):
            return Decision(False, "take_profit_ogiltig")
        sl_pips = sl_dist / PIP
        if sl_pips < r.min_stop_pips:
            return Decision(False, "stop_for_tajt")
        if sl_pips > r.max_stop_pips:
            return Decision(False, "stop_for_lang")

        risk_d = self.planned_risk_distance(sl_dist)
        rr = self.planned_reward_distance(tp_dist) / risk_d
        if rr < r.min_reward_risk:
            return Decision(False, f"rr_for_lag_{rr:.2f}", reward_risk=rr)

        per_unit = risk_d * a.usd_to_account + self.commission_per_unit()
        units = int(state.balance * r.risk_per_trade / per_unit // r.lot_step * r.lot_step)
        max_units = int(r.max_leverage * state.balance / (ref_price * a.usd_to_account) // r.lot_step * r.lot_step)
        units = min(units, max_units)  # exponeringsgränsen kan bara minska risken
        if units < r.min_units:
            return Decision(False, "positionsstorlek_under_minimum", reward_risk=rr)

        return Decision(True, "godkand", units=units, risk_amount=units * per_unit, reward_risk=rr)

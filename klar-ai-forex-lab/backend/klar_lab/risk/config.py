"""Risk-, kostnads- och kontoinställningar.

Gränserna ändras bara av en människa: standardvärdena nedan gäller tills en fil
data/config/risk_limits.json finns OCH är signerad med nyckeln i KLAR_RISK_SIGNING_KEY
(se klar_lab.risk.signing). En osignerad eller manipulerad fil gör att systemet vägrar starta
handel/backtest i stället för att tyst använda andra värden.
"""
from dataclasses import asdict, dataclass, field, fields, replace

PIP = 0.0001  # EUR/USD


@dataclass(frozen=True)
class AccountConfig:
    starting_capital: float = 10_000.0
    currency: str = "SEK"
    usd_to_account: float = 9.5          # ANTAGANDE: fast växelkurs SEK per USD


@dataclass(frozen=True)
class CostConfig:
    spread_pips: float = 0.8              # ANTAGANDE: typisk retail-spread
    slippage_pips: float = 0.3            # ANTAGANDE: per order (in) och vid stop-loss (ut)
    commission_usd_per_100k: float = 0.0  # round-turn per 100 000 enheter
    # ANTAGANDE (konservativt): swap är en kostnad åt båda håll. Dras vid varje rollover
    # 22:00 UTC; onsdag räknas tre gånger (helgen).
    swap_long_pips_per_night: float = 0.5
    swap_short_pips_per_night: float = 0.3

    @property
    def spread(self) -> float:
        return self.spread_pips * PIP

    @property
    def slippage(self) -> float:
        return self.slippage_pips * PIP


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade: float = 0.01          # 1 % av aktuellt saldo
    min_reward_risk: float = 2.0          # 1:2, NETTO efter spread/slippage
    max_daily_loss: float = 0.03          # 3 % av dagens startsaldo -> inga nya affärer den dagen
    max_drawdown: float = 0.20            # 20 % från toppsaldo -> permanent stopp
    max_leverage: float = 10.0            # max nominellt värde / saldo (exponeringsgräns)
    max_open_positions: int = 1
    min_stop_pips: float = 8.0
    max_stop_pips: float = 200.0
    lot_step: int = 1_000
    min_units: int = 1_000
    max_bar_gap_hours: float = 100.0      # längre lucka mellan signal och order = föråldrad data
    price_min: float = 0.5
    price_max: float = 2.0


@dataclass(frozen=True)
class LabConfig:
    account: AccountConfig = field(default_factory=AccountConfig)
    costs: CostConfig = field(default_factory=CostConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LabConfig":
        """Okända nycklar avvisas så att stavfel inte tyst ignoreras."""
        parts = {}
        for name, klass in (("account", AccountConfig), ("costs", CostConfig), ("risk", RiskConfig)):
            section = data.get(name, {})
            allowed = {f.name for f in fields(klass)}
            unknown = set(section) - allowed
            if unknown:
                raise ValueError(f"Okända nycklar i '{name}': {sorted(unknown)}")
            parts[name] = replace(klass(), **section)
        unknown_top = set(data) - set(parts)
        if unknown_top:
            raise ValueError(f"Okända sektioner: {sorted(unknown_top)}")
        return cls(**parts)

"""
Domain models for Backtesting Engine.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.signal.domain import FinalSignal


class ExitReason(str, Enum):
    STOP_HIT = "STOP_HIT"
    TARGET_HIT = "TARGET_HIT"
    AMBIGUOUS_BAR_STOP_HIT = "AMBIGUOUS_BAR_STOP_HIT"
    TIME_EXIT = "TIME_EXIT"
    END_OF_DATA = "END_OF_DATA"


@dataclass(frozen=True)
class VirtualTrade:
    trade_id: str
    signal_id: str
    symbol: str
    timeframe: str
    direction: str
    entry_timestamp: datetime
    entry_price: float
    stop_reference: float
    target_reference: float
    risk_r_amount: float
    strategy: str
    market_regime: str
    exit_timestamp: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    gross_result_r: Optional[float] = None
    net_result_r: Optional[float] = None
    holding_bars: int = 0
    is_open: bool = True
    # Risk-engine fields — populated when the trade is created from an
    # OrderProposal (create_trade_from_order). None when created from a
    # raw FinalSignal (create_trade_from_signal).
    volume_lots: Optional[float] = None
    risk_amount_account_currency: Optional[float] = None


@dataclass
class BacktestCostModel:
    """Backtest costs with explicit price units and OHLC price basis.

    ``spread_points`` and ``slippage_points`` are legacy names for configured
    cost units. ``point_value`` converts ONE such configured unit into an
    absolute price delta. For EURUSD, 0.0001 means one pip, not one MT5 point.

    Broker-native OHLCVBar.spread is a different unit (MT5 points). It is used
    only when ``use_bar_spread=True`` and ``bar_spread_point_value`` explicitly
    converts one broker point to a price delta. There is no implicit fallback.

    ``price_basis`` describes the input OHLC prices: MID, BID, or ASK. Select
    it from the provenance of the historical data; MT5 OTC FX bars are commonly
    BID-based, but the data source must be checked rather than guessed.
    """

    spread_points: float = 0.0
    point_value: float = 0.0001
    commission_per_trade_r: float = 0.0
    slippage_points: float = 0.0
    price_basis: str = "MID"
    use_bar_spread: bool = False
    bar_spread_point_value: float | None = None

    def __post_init__(self) -> None:
        for name in ("spread_points", "point_value", "commission_per_trade_r", "slippage_points"):
            try:
                value = float(getattr(self, name))
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"{name} doit être numérique.") from exc
            if not math.isfinite(value):
                raise ValueError(f"{name} doit être fini.")
            setattr(self, name, value)

        if self.spread_points < 0 or self.slippage_points < 0 or self.commission_per_trade_r < 0:
            raise ValueError("Spread, slippage et commission doivent être positifs ou nuls.")
        if self.point_value <= 0:
            raise ValueError("point_value doit être strictement positif.")

        self.price_basis = str(self.price_basis).strip().upper()
        if self.price_basis not in {"MID", "BID", "ASK"}:
            raise ValueError("price_basis doit valoir 'MID', 'BID' ou 'ASK'.")
        if not isinstance(self.use_bar_spread, bool):
            raise ValueError("use_bar_spread doit être booléen.")

        if self.bar_spread_point_value is not None:
            try:
                self.bar_spread_point_value = float(self.bar_spread_point_value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("bar_spread_point_value doit être numérique.") from exc
            if not math.isfinite(self.bar_spread_point_value) or self.bar_spread_point_value <= 0:
                raise ValueError("bar_spread_point_value doit être fini et strictement positif.")

        if self.use_bar_spread and self.bar_spread_point_value is None:
            raise ValueError(
                "use_bar_spread=True exige bar_spread_point_value pour convertir les points broker en prix."
            )

    def spread_price_for_bar(self, bar: Any) -> float:
        """Return this bar's spread as an absolute price delta."""
        if not self.use_bar_spread:
            return self.spread_points * self.point_value

        raw_spread = getattr(bar, "spread", None)
        try:
            broker_points = float(raw_spread)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Spread broker absent ou non numérique sur une bougie.") from exc
        if not math.isfinite(broker_points) or broker_points < 0:
            raise ValueError("Le spread broker doit être fini et positif ou nul.")
        # __post_init__ guarantees that the converter is present in this mode.
        return broker_points * float(self.bar_spread_point_value)

    def bid_ask_from_price(self, reference_price: float, spread_price: float) -> tuple[float, float]:
        """Derive a synthetic quote from the configured OHLC price basis."""
        try:
            price = float(reference_price)
            spread = float(spread_price)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Prix de référence et spread doivent être numériques.") from exc
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Le prix de référence doit être fini et strictement positif.")
        if not math.isfinite(spread) or spread < 0:
            raise ValueError("Le spread converti doit être fini et positif ou nul.")

        if self.price_basis == "MID":
            return price - spread / 2.0, price + spread / 2.0
        if self.price_basis == "BID":
            return price, price + spread
        # ASK-based OHLC
        return price - spread, price

    def quote_bar_range(self, bar: Any, spread_price: float) -> tuple[float, float, float, float]:
        """Return (bid_high, bid_low, ask_high, ask_low) for the bar."""
        high = float(bar.high)
        low = float(bar.low)
        if not math.isfinite(high) or not math.isfinite(low) or low > high:
            raise ValueError("OHLC high/low invalides pour le calcul Bid/Ask.")
        spread = float(spread_price)
        if not math.isfinite(spread) or spread < 0:
            raise ValueError("Le spread converti doit être fini et positif ou nul.")

        if self.price_basis == "MID":
            half = spread / 2.0
            return high - half, low - half, high + half, low + half
        if self.price_basis == "BID":
            return high, low, high + spread, low + spread
        return high - spread, low - spread, high, low


@dataclass
class BacktestConfig:
    symbol: str
    timeframe: str
    warmup_bars: int = 200
    cost_model: BacktestCostModel = field(default_factory=BacktestCostModel)
    initial_capital: float = 10000.0
    risk_per_trade_pct: float = 1.0
    lookback_bars: int = 500
    max_concurrent_trades: int | None = None
    # Risk sizing mode: "PERCENTAGE" (default) or "FIXED_AMOUNT".
    # When "FIXED_AMOUNT", fixed_risk_amount must be set.
    risk_mode: str = "PERCENTAGE"
    fixed_risk_amount: float | None = None


@dataclass
class BacktestMetrics:
    total_evaluated_bars: int
    total_signals: int
    buy_signals: int
    sell_signals: int
    no_trade_count: int
    no_trade_breakdown: Dict[str, int]
    total_virtual_trades: int
    winning_trades: int
    losing_trades: int
    open_trades: int
    win_rate_pct: float
    profit_factor: float
    gross_result_r: float
    net_result_r: float
    max_drawdown_r: float
    regime_segmentation: Dict[str, Dict[str, Any]]
    strategy_segmentation: Dict[str, Dict[str, Any]]

    @property
    def net_r(self) -> float:
        return self.net_result_r

    @property
    def gross_r(self) -> float:
        return self.gross_result_r

    @property
    def max_drawdown(self) -> float:
        return self.max_drawdown_r

    @property
    def win_rate(self) -> float:
        return self.win_rate_pct


@dataclass
class BacktestResult:
    run_id: str
    config: BacktestConfig
    start_timestamp: datetime
    end_timestamp: datetime
    signals: List[FinalSignal]
    trades: List[VirtualTrade]
    metrics: BacktestMetrics
    warnings: List[str] = field(default_factory=list)
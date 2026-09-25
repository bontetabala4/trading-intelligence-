"""
Domain models for Backtesting Engine.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


@dataclass
class BacktestCostModel:
    spread_points: float = 0.0
    point_value: float = 0.0001
    commission_per_trade_r: float = 0.0
    slippage_points: float = 0.0


@dataclass
class BacktestConfig:
    symbol: str
    timeframe: str
    warmup_bars: int = 200
    cost_model: BacktestCostModel = field(default_factory=BacktestCostModel)
    initial_capital: float = 10000.0
    risk_per_trade_pct: float = 1.0


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
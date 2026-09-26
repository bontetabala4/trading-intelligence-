"""
Paper Position & Portfolio Management Module.
Handles virtual position lifecycles, execution friction (spread/slippage/commission),
and deterministic portfolio accounting. Completely isolated from broker execution.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class PositionDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class PaperPosition:
    id: str
    symbol: str
    timeframe: str
    direction: PositionDirection
    entry_timestamp: datetime
    entry_price: float
    stop_price: float
    target_price: float
    strategy: str
    signal_id: str
    risk_r: float = 1.0
    status: PositionStatus = PositionStatus.OPEN
    exit_timestamp: Optional[datetime] = None
    exit_price: Optional[float] = None
    gross_r: Optional[float] = None
    net_r: Optional[float] = None
    exit_reason: Optional[str] = None

    def evaluate_bar(self, bar: Dict[str, Any], cost_model: Dict[str, float], stop_first: bool = True) -> bool:
        """
        Evaluates an open position against a new M15 bar (High/Low).
        Applies conservative STOP_LOSS_FIRST logic on ambiguous bars.
        """
        if self.status != PositionStatus.OPEN:
            return False

        high = bar['high']
        low = bar['low']
        timestamp = bar['timestamp']

        hit_sl = False
        hit_tp = False

        if self.direction == PositionDirection.BUY:
            if low <= self.stop_price:
                hit_sl = True
            if high >= self.target_price:
                hit_tp = True
        else:  # SELL
            if high >= self.stop_price:
                hit_sl = True
            if low <= self.target_price:
                hit_tp = True

        if not hit_sl and not hit_tp:
            return False

        # Resolution logic
        if hit_sl and hit_tp:
            exit_type = "STOP_LOSS" if stop_first else "TAKE_PROFIT"
        elif hit_sl:
            exit_type = "STOP_LOSS"
        else:
            exit_type = "TAKE_PROFIT"

        self.exit_timestamp = timestamp
        self.exit_reason = exit_type
        self.status = PositionStatus.CLOSED

        # Calculate execution price and R-outcomes
        risk_dist = abs(self.entry_price - self.stop_price)
        spread_cost_r = cost_model.get('spread_pip', 1.0) * 0.0001 / risk_dist if risk_dist > 0 else 0
        slippage_r = cost_model.get('slippage_pip', 0.2) * 0.0001 / risk_dist if risk_dist > 0 else 0

        if exit_type == "STOP_LOSS":
            self.exit_price = self.stop_price
            self.gross_r = -1.0
        else:
            self.exit_price = self.target_price
            self.gross_r = abs(self.target_price - self.entry_price) / risk_dist if risk_dist > 0 else 2.0

        self.net_r = self.gross_r - spread_cost_r - slippage_r
        return True


class PaperPortfolio:
    def __init__(self, initial_capital: float = 10000.0, max_open_positions: int = 1):
        self.initial_capital = initial_capital
        self.current_equity = initial_capital
        self.max_open_positions = max_open_positions
        self.open_positions: List[PaperPosition] = []
        self.closed_positions: List[PaperPosition] = []
        self.peak_equity = initial_capital
        self.max_drawdown_r = 0.0
        self.cumulative_net_r = 0.0

    def can_open_position(self) -> bool:
        return len(self.open_positions) < self.max_open_positions

    def add_position(self, position: PaperPosition) -> bool:
        if not self.can_open_position():
            return False
        self.open_positions.append(position)
        return True

    def process_bar(self, bar: Dict[str, Any], cost_model: Dict[str, float]) -> List[PaperPosition]:
        just_closed = []
        remaining_open = []

        for pos in self.open_positions:
            closed = pos.evaluate_bar(bar, cost_model)
            if closed:
                self.closed_positions.append(pos)
                self.cumulative_net_r += pos.net_r
                just_closed.append(pos)
                
                # Drawdown tracking in R
                if self.cumulative_net_r > self.peak_equity:
                    self.peak_equity = self.cumulative_net_r
                dd = self.peak_equity - self.cumulative_net_r
                if dd > self.max_drawdown_r:
                    self.max_drawdown_r = dd
            else:
                remaining_open.append(pos)

        self.open_positions = remaining_open
        return just_closed
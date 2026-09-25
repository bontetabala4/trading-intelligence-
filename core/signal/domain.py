"""
Domain models for Step 8: Final Signal & Notification Engine.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class SignalCandidate:
    action: SignalAction
    symbol: str
    asset_class: str
    timeframe: str
    timestamp: datetime
    strategy_name: str
    market_regime: str
    confidence: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    rationale: Dict[str, Any] = field(default_factory=dict)
    data_quality_score: float = 1.0


class FinalSignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


class NoTradeReason(str, Enum):
    INVALID_DATA = "INVALID_DATA"
    OPPORTUNITY_REJECTED = "OPPORTUNITY_REJECTED"
    OPPORTUNITY_UNCERTAIN = "OPPORTUNITY_UNCERTAIN"
    RISK_REJECTED = "RISK_REJECTED"
    RISK_REVIEW_REQUIRED = "RISK_REVIEW_REQUIRED"
    MISSING_DIRECTION = "MISSING_DIRECTION"
    STRATEGY_NOT_COMPATIBLE = "STRATEGY_NOT_COMPATIBLE"
    NONE = "NONE"


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"


@dataclass(frozen=True)
class FinalSignal:
    signal_id: str
    symbol: str
    asset_class: str
    timeframe: str
    timestamp: datetime
    direction: FinalSignalDirection
    no_trade_reason: NoTradeReason
    strategy: str
    market_regime: str
    opportunity_status: str
    opportunity_score: float
    risk_status: str
    risk_score: float
    data_quality_status: str
    reasons: List[str]
    evidence: Dict[str, Any]
    entry_reference: Optional[float] = None
    stop_reference: Optional[float] = None
    target_reference: Optional[float] = None
    risk_reward: Optional[float] = None
    signal_version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def action(self) -> SignalAction:
        if self.direction == FinalSignalDirection.BUY:
            return SignalAction.BUY
        elif self.direction == FinalSignalDirection.SELL:
            return SignalAction.SELL
        return SignalAction.NO_TRADE

    @property
    def deduplication_key(self) -> str:
        ts_str = self.timestamp.isoformat()
        return f"{self.symbol}:{self.timeframe}:{ts_str}:{self.direction.value}:{self.strategy}:{self.signal_version}"


@dataclass
class NotificationRecord:
    notification_id: str
    signal_id: str
    deduplication_key: str
    recipient: str
    channel: str
    content: str
    status: NotificationStatus
    timestamp: datetime
    error_message: Optional[str] = None
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from core.risk.domain.enums import RiskStatus, RiskRejectReason
from core.strategy.domain.enums import SignalType, StrategyID

class AccountState(BaseModel):
    model_config = ConfigDict(frozen=True)

    balance: float = Field(..., gt=0.0)
    equity: float = Field(..., gt=0.0)
    free_margin: float = Field(..., ge=0.0)
    daily_pnl: float = 0.0
    open_positions_count: int = Field(0, ge=0)

class OrderProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    signal_type: SignalType
    strategy_id: StrategyID
    volume_lots: float = Field(..., ge=0.0)
    stop_loss: float
    take_profit: float
    risk_amount_account_currency: float
    risk_percentage: float
    timestamp: datetime
    status: RiskStatus
    reject_reason: RiskRejectReason = RiskRejectReason.NONE
    audit_trail: List[str] = Field(default_factory=list)
    engine_version: str = "1.0.0"
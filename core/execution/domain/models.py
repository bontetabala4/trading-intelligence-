from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from core.execution.domain.enums import ExecutionStatus, ExecutionMode
from core.strategy.domain.enums import SignalType, StrategyID

class ExecutionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    signal_type: SignalType
    strategy_id: StrategyID
    volume_lots: float = Field(..., gt=0.0)
    stop_loss: float
    take_profit: float
    max_slippage_pips: float = 2.0
    magic_number: int = 123456
    execution_mode: ExecutionMode = ExecutionMode.PAPER

class OrderFillDetails(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: int
    executed_price: float
    executed_volume: float
    commission: float = 0.0
    swap: float = 0.0
    slippage_pips: float = 0.0

class ExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    request: ExecutionRequest
    status: ExecutionStatus
    fill_details: Optional[OrderFillDetails] = None
    retcode: int = 0
    error_message: Optional[str] = None
    timestamp: datetime
    execution_time_ms: float = 0.0
    audit_trail: List[str] = Field(default_factory=list)
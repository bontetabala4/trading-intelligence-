from fastapi import APIRouter
from datetime import datetime, timezone
from core.risk.domain.models import OrderProposal
from core.risk.domain.enums import RiskStatus, RiskRejectReason
from core.strategy.domain.enums import SignalType, StrategyID
from core.execution.domain.models import ExecutionResult
from core.execution.domain.enums import ExecutionMode
from core.execution.services.engine import ExecutionEngine

router = APIRouter(prefix="/execution", tags=["Execution"])
execution_engine = ExecutionEngine(mode=ExecutionMode.PAPER)

@router.post("/execute", response_model=ExecutionResult)
async def execute_order_proposal(price: float = 1.0850):
    fake_proposal = OrderProposal(
        symbol="EURUSD",
        signal_type=SignalType.BUY,
        strategy_id=StrategyID.TREND_FOLLOWING,
        volume_lots=0.1,
        stop_loss=1.0835,
        take_profit=1.0880,
        risk_amount_account_currency=100.0,
        risk_percentage=1.0,
        timestamp=datetime.now(timezone.utc),
        status=RiskStatus.APPROVED,
        reject_reason=RiskRejectReason.NONE
    )

    return execution_engine.process_proposal(fake_proposal, current_price=price)
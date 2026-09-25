from datetime import datetime, timezone
from core.risk.domain.models import OrderProposal
from core.risk.domain.enums import RiskStatus, RiskRejectReason
from core.strategy.domain.enums import SignalType, StrategyID
from core.execution.domain.enums import ExecutionStatus, ExecutionMode
from core.execution.services.engine import ExecutionEngine

def test_paper_execution_success():
    engine = ExecutionEngine(mode=ExecutionMode.PAPER)

    proposal = OrderProposal(
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

    result = engine.process_proposal(proposal, current_price=1.0850)

    assert result.status == ExecutionStatus.EXECUTED
    assert result.fill_details is not None
    assert result.fill_details.executed_price == 1.0850
    assert result.fill_details.executed_volume == 0.1

def test_execution_cancelled_if_risk_rejected():
    engine = ExecutionEngine(mode=ExecutionMode.PAPER)

    proposal = OrderProposal(
        symbol="EURUSD",
        signal_type=SignalType.BUY,
        strategy_id=StrategyID.TREND_FOLLOWING,
        volume_lots=0.0,
        stop_loss=0.0,
        take_profit=0.0,
        risk_amount_account_currency=0.0,
        risk_percentage=0.0,
        timestamp=datetime.now(timezone.utc),
        status=RiskStatus.REJECTED,
        reject_reason=RiskRejectReason.MAX_DAILY_DRAWDOWN_REACHED
    )

    result = engine.process_proposal(proposal, current_price=1.0850)

    assert result.status == ExecutionStatus.CANCELLED
    assert "Proposal not approved" in result.error_message
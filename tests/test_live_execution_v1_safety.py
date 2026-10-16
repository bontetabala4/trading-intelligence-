from datetime import datetime, timezone

from core.risk.domain.models import OrderProposal
from core.risk.domain.enums import RiskStatus, RiskRejectReason
from core.strategy.domain.enums import SignalType, StrategyID
from core.execution.domain.enums import ExecutionStatus, ExecutionMode
from core.execution.services.engine import ExecutionEngine
from core.execution.services.mt5_executor import MT5ExecutionAdapter


def test_live_execution_stays_blocked_when_environment_flag_is_true(monkeypatch):
    """ATIP V1 must never send a live order, even if the legacy flag is true."""

    class SpyMT5Client:
        is_connected = True

        def __init__(self):
            self.order_send_called = False

        def order_send(self, request):
            self.order_send_called = True
            raise AssertionError("ATIP V1 must never submit a live order")

    monkeypatch.setenv("TRADING_EXECUTION_ENABLED", "true")

    client = SpyMT5Client()
    adapter = MT5ExecutionAdapter(mt5_client=client)
    engine = ExecutionEngine(adapter=adapter, mode=ExecutionMode.LIVE)

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
        reject_reason=RiskRejectReason.NONE,
    )

    result = engine.process_proposal(proposal, current_price=1.0850)

    assert result.status == ExecutionStatus.FAILED
    assert result.retcode == -403
    assert "BLOCKED_BY_V1_LIVE_EXECUTION_DISABLED" in result.audit_trail
    assert client.order_send_called is False

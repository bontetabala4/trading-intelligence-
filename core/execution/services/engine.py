from datetime import datetime, timezone
from core.risk.domain.models import OrderProposal
from core.risk.domain.enums import RiskStatus
from core.execution.domain.models import ExecutionRequest, ExecutionResult
from core.execution.domain.enums import ExecutionStatus, ExecutionMode
from core.execution.services.mt5_executor import MT5ExecutionAdapter

class ExecutionEngine:
    def __init__(self, adapter: MT5ExecutionAdapter = None, mode: ExecutionMode = ExecutionMode.PAPER):
        self.adapter = adapter or MT5ExecutionAdapter()
        self.mode = mode

    def process_proposal(self, proposal: OrderProposal, current_price: float) -> ExecutionResult:
        now = datetime.now(timezone.utc)

        # Reject direct si le RiskEngine n'a pas approuvé
        if proposal.status != RiskStatus.APPROVED:
            dummy_request = ExecutionRequest(
                symbol=proposal.symbol,
                signal_type=proposal.signal_type,
                strategy_id=proposal.strategy_id,
                volume_lots=0.01,
                stop_loss=proposal.stop_loss,
                take_profit=proposal.take_profit,
                execution_mode=self.mode
            )
            return ExecutionResult(
                request=dummy_request,
                status=ExecutionStatus.CANCELLED,
                error_message=f"Proposal not approved by RiskEngine ({proposal.reject_reason.value})",
                timestamp=now,
                audit_trail=["CANCELLED_UNAPPROVED_PROPOSAL"]
            )

        exec_request = ExecutionRequest(
            symbol=proposal.symbol,
            signal_type=proposal.signal_type,
            strategy_id=proposal.strategy_id,
            volume_lots=proposal.volume_lots,
            stop_loss=proposal.stop_loss,
            take_profit=proposal.take_profit,
            execution_mode=self.mode
        )

        return self.adapter.execute_order(exec_request, current_price)
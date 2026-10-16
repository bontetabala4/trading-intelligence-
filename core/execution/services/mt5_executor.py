import time
from datetime import datetime, timezone
from core.execution.domain.enums import ExecutionStatus, ExecutionMode
from core.execution.domain.models import ExecutionRequest, ExecutionResult, OrderFillDetails

class MT5ExecutionAdapter:
    """Adaptateur d'exécution MT5 gérant à la fois le Paper Trading et la connexion MT5 réelle."""

    def __init__(self, mt5_client=None):
        self.mt5_client = mt5_client

    def execute_order(self, request: ExecutionRequest, current_price: float) -> ExecutionResult:
        start_time = time.time()
        now = datetime.now(timezone.utc)

        # 1. Mode Simulation / Paper Trading
        if request.execution_mode == ExecutionMode.PAPER:
            fill = OrderFillDetails(
                ticket_id=int(time.time() * 1000) % 1000000,
                executed_price=current_price,
                executed_volume=request.volume_lots,
                commission=0.0,
                slippage_pips=0.0
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return ExecutionResult(
                request=request,
                status=ExecutionStatus.EXECUTED,
                fill_details=fill,
                retcode=10009,
                timestamp=now,
                execution_time_ms=elapsed_ms,
                audit_trail=["PAPER_EXECUTION_SUCCESS"]
            )

        # 2. Mode LIVE — toujours désactivé dans ATIP V1.
        # Cette garde est volontairement inconditionnelle : le flag
        # TRADING_EXECUTION_ENABLED ne doit pas permettre d'envoyer un ordre
        # réel dans cette version. Une version future nécessitera une étape
        # d'autorisation et de sécurité distincte.
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return ExecutionResult(
            request=request,
            status=ExecutionStatus.FAILED,
            retcode=-403,
            error_message=(
                "SAFETY_LOCK: Live order execution is not available in ATIP V1; "
                "TRADING_EXECUTION_ENABLED cannot enable it."
            ),
            timestamp=now,
            execution_time_ms=elapsed_ms,
            audit_trail=[
                "BLOCKED_BY_SAFETY_GUARD_EXECUTION_DISABLED",
                "BLOCKED_BY_V1_LIVE_EXECUTION_DISABLED",
            ],
        )

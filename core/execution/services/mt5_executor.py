import time
from datetime import datetime, timezone
from core.execution.domain.enums import ExecutionStatus, ExecutionMode
from core.execution.domain.models import ExecutionRequest, ExecutionResult, OrderFillDetails
from core.strategy.domain.enums import SignalType

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

        # 2. Mode Live (MetaTrader 5)
        if not self.mt5_client or not getattr(self.mt5_client, "is_connected", False):
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return ExecutionResult(
                request=request,
                status=ExecutionStatus.FAILED,
                retcode=-1,
                error_message="MT5 Terminal Not Connected",
                timestamp=now,
                execution_time_ms=elapsed_ms,
                audit_trail=["MT5_NOT_CONNECTED"]
            )

        # Envoi de la commande à MT5
        action_type = 0 if request.signal_type == SignalType.BUY else 1  # BUY=0 (ORDER_TYPE_BUY), SELL=1
        mt5_req = {
            "action": 1,  # TRADE_ACTION_DEAL
            "symbol": request.symbol,
            "volume": request.volume_lots,
            "type": action_type,
            "price": current_price,
            "sl": request.stop_loss,
            "tp": request.take_profit,
            "deviation": int(request.max_slippage_pips * 10),
            "magic": request.magic_number,
            "comment": f"ATI_{request.strategy_id.value}",
        }

        res = self.mt5_client.order_send(mt5_req)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        if res and getattr(res, "retcode", None) == 10009:
            fill = OrderFillDetails(
                ticket_id=getattr(res, "order", 0),
                executed_price=getattr(res, "price", current_price),
                executed_volume=getattr(res, "volume", request.volume_lots),
                commission=getattr(res, "commission", 0.0)
            )
            return ExecutionResult(
                request=request,
                status=ExecutionStatus.EXECUTED,
                fill_details=fill,
                retcode=10009,
                timestamp=now,
                execution_time_ms=elapsed_ms,
                audit_trail=["MT5_ORDER_EXECUTED_SUCCESS"]
            )

        retcode = getattr(res, "retcode", -1) if res else -1
        return ExecutionResult(
            request=request,
            status=ExecutionStatus.REJECTED,
            retcode=retcode,
            error_message=f"MT5 Order Rejected with retcode={retcode}",
            timestamp=now,
            execution_time_ms=elapsed_ms,
            audit_trail=[f"MT5_REJECTED_{retcode}"]
        )
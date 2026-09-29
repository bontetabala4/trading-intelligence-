from datetime import datetime, timezone

from core.strategy.domain.models import StrategySignal
from core.strategy.domain.enums import SignalType

from core.risk.domain.models import (
    AccountState,
    OrderProposal,
)

from core.risk.domain.enums import (
    RiskStatus,
    RiskRejectReason,
)

from core.risk.services.sizer import PositionSizer
from core.risk.services.limits import RiskLimitsChecker
from brokers.base.interface import SymbolInfo


class RiskEngine:

    def __init__(
        self,
        sizer: PositionSizer | None = None,
        limits: RiskLimitsChecker | None = None,
        engine_version: str = "1.0.0",
    ):
        self.sizer = sizer or PositionSizer()
        self.limits = limits or RiskLimitsChecker()
        self.engine_version = engine_version

    def evaluate_signal(
        self,
        signal: StrategySignal,
        account: AccountState,
        current_price: float,
        current_spread_pips: float = 1.0,
        pip_size: float = 0.0001,
        symbol_info: SymbolInfo | None = None,
        evaluation_timestamp: datetime | None = None,
    ) -> OrderProposal:

        timestamp = (
            evaluation_timestamp
            or signal.timestamp
            or datetime.now(timezone.utc)
        )

        if timestamp.tzinfo is None:
            raise ValueError(
                "RiskEngine timestamp doit être timezone-aware."
            )

        audit_trail = [
            f"SIGNAL_RECEIVED_{signal.signal.value}"
        ]

        # ==============================================================
        # 1. NEUTRAL
        # ==============================================================

        if signal.signal == SignalType.NEUTRAL:

            return OrderProposal(
                symbol=signal.symbol,
                signal_type=signal.signal,
                strategy_id=signal.strategy_id,
                volume_lots=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_amount_account_currency=0.0,
                risk_percentage=0.0,
                timestamp=timestamp,
                status=RiskStatus.REJECTED,
                reject_reason=RiskRejectReason.SIGNAL_NEUTRAL,
                audit_trail=[
                    "REJECTED_NEUTRAL_SIGNAL"
                ],
                engine_version=self.engine_version,
            )

        # ==============================================================
        # 2. LIMITES
        # ==============================================================

        limit_reason = self.limits.validate(
            account,
            current_spread_pips,
        )

        if limit_reason != RiskRejectReason.NONE:

            audit_trail.append(
                f"REJECTED_LIMIT_{limit_reason.value}"
            )

            return OrderProposal(
                symbol=signal.symbol,
                signal_type=signal.signal,
                strategy_id=signal.strategy_id,
                volume_lots=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_amount_account_currency=0.0,
                risk_percentage=0.0,
                timestamp=timestamp,
                status=RiskStatus.REJECTED,
                reject_reason=limit_reason,
                audit_trail=audit_trail,
                engine_version=self.engine_version,
            )

        # ==============================================================
        # 3. SL / TP
        # ==============================================================
        sl_distance = (
            signal.suggested_sl_distance
            if signal.suggested_sl_distance is not None
            else 0.0
        )

        tp_distance = (
            signal.suggested_tp_distance
            if signal.suggested_tp_distance is not None
            else 0.0
        )

        if sl_distance <= 0 or tp_distance <= 0:
            return OrderProposal(
                symbol=signal.symbol,
                signal_type=signal.signal,
                strategy_id=signal.strategy_id,
                volume_lots=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_amount_account_currency=0.0,
                risk_percentage=0.0,
                timestamp=timestamp,
                status=RiskStatus.REJECTED,
                reject_reason=RiskRejectReason.INVALID_SL_TP,
                audit_trail=[
                    "REJECTED_INVALID_SL_TP"
                ],
                engine_version=self.engine_version,
            )
        if signal.signal == SignalType.BUY:

            sl_price = round(
                current_price - sl_distance,
                5,
            )

            tp_price = round(
                current_price + tp_distance,
                5,
            )
        else:
            sl_price = round(
                current_price + sl_distance,
                5,
            )

            tp_price = round(
                current_price - tp_distance,
                5,
            )

        # ==============================================================
        # 4. POSITION SIZE
        # ==============================================================

        volume_lots = self.sizer.calculate_lot_size(
            balance=account.balance,
            sl_distance=sl_distance,
            symbol_info=symbol_info,
            pip_size=pip_size,
        )

        if volume_lots <= 0.0:

            audit_trail.append(
                "REJECTED_VOLUME_BELOW_MINIMUM"
            )

            return OrderProposal(
                symbol=signal.symbol,
                signal_type=signal.signal,
                strategy_id=signal.strategy_id,
                volume_lots=0.0,
                stop_loss=sl_price,
                take_profit=tp_price,
                risk_amount_account_currency=0.0,
                risk_percentage=0.0,
                timestamp=timestamp,
                status=RiskStatus.REJECTED,
                reject_reason=RiskRejectReason.INSUFFICIENT_MARGIN,
                audit_trail=audit_trail,
                engine_version=self.engine_version,
            )

        # ==============================================================
        # 5. APPROVAL
        # ==============================================================

        risk_currency = round(
            account.balance
            * self.sizer.risk_per_trade_pct,
            2,
        )

        risk_percentage = round(
            self.sizer.risk_per_trade_pct * 100,
            2,
        )

        audit_trail.append(
            f"APPROVED_VOLUME_{volume_lots}_LOTS"
        )

        return OrderProposal(
            symbol=signal.symbol,
            signal_type=signal.signal,
            strategy_id=signal.strategy_id,
            volume_lots=volume_lots,
            stop_loss=sl_price,
            take_profit=tp_price,
            risk_amount_account_currency=risk_currency,
            risk_percentage=risk_percentage,
            timestamp=timestamp,
            status=RiskStatus.APPROVED,
            reject_reason=RiskRejectReason.NONE,
            audit_trail=audit_trail,
            engine_version=self.engine_version,
        )
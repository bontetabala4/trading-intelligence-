from datetime import datetime, timezone
import math

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

    def reject_missing_risk_inputs(
        self,
        signal: StrategySignal,
        evaluation_timestamp: datetime,
        missing_inputs: list[str],
    ) -> OrderProposal:
        if evaluation_timestamp.tzinfo is None:
            raise ValueError("RiskEngine timestamp doit être timezone-aware.")
        return OrderProposal(
            symbol=signal.symbol,
            signal_type=signal.signal,
            strategy_id=signal.strategy_id,
            volume_lots=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            risk_amount_account_currency=0.0,
            risk_percentage=0.0,
            timestamp=evaluation_timestamp,
            status=RiskStatus.REJECTED,
            reject_reason=RiskRejectReason.MISSING_RISK_INPUTS,
            audit_trail=[
                "REJECTED_MISSING_RISK_INPUTS",
                *[f"MISSING_{name.upper()}" for name in missing_inputs],
            ],
            engine_version=self.engine_version,
        )

    def evaluate_signal(
        self,
        signal: StrategySignal,
        account: AccountState,
        current_price: float,
        current_spread_pips: float | None = None,
        pip_size: float = 0.0001,
        symbol_info: SymbolInfo | None = None,
        evaluation_timestamp: datetime | None = None,
        current_spread_price: float | None = None,
        require_symbol_info: bool = False,
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
        # 1b. INPUTS DU RISQUE — échec fermé en chemin strict/API
        # ==============================================================

        if not math.isfinite(current_price) or current_price <= 0:
            return self.reject_missing_risk_inputs(
                signal, timestamp, ["CURRENT_PRICE"]
            )

        if require_symbol_info:
            required_symbol_values = {
                "POINT": getattr(symbol_info, "point", None),
                "DIGITS": getattr(symbol_info, "digits", None),
                "TRADE_TICK_SIZE": getattr(symbol_info, "trade_tick_size", None),
                "TRADE_TICK_VALUE": getattr(symbol_info, "trade_tick_value", None),
                "VOLUME_MIN": getattr(symbol_info, "volume_min", None),
                "VOLUME_MAX": getattr(symbol_info, "volume_max", None),
                "VOLUME_STEP": getattr(symbol_info, "volume_step", None),
            }
            missing = []
            if symbol_info is None or not getattr(symbol_info, "exists", False):
                missing.append("SYMBOL_INFO")
            elif not getattr(symbol_info, "tradable", False):
                missing.append("SYMBOL_NOT_TRADABLE")
            for name, value in required_symbol_values.items():
                try:
                    if name == "DIGITS":
                        numeric = float(value) if value is not None else float("nan")
                        valid = math.isfinite(numeric) and numeric >= 0 and numeric.is_integer()
                    else:
                        valid = value is not None and math.isfinite(float(value)) and float(value) > 0
                except (TypeError, ValueError):
                    valid = False
                if not valid:
                    missing.append(name)
            if missing:
                return self.reject_missing_risk_inputs(signal, timestamp, missing)

            if current_spread_price is None:
                return self.reject_missing_risk_inputs(
                    signal, timestamp, ["CURRENT_SPREAD_PRICE"]
                )

        if current_spread_price is not None and (
            not math.isfinite(current_spread_price) or current_spread_price < 0
        ):
            return self.reject_missing_risk_inputs(
                signal, timestamp, ["CURRENT_SPREAD_PRICE"]
            )

        if current_spread_pips is not None and (
            not math.isfinite(current_spread_pips) or current_spread_pips < 0
        ):
            return self.reject_missing_risk_inputs(
                signal, timestamp, ["CURRENT_SPREAD_PIPS"]
            )

        if current_spread_pips is None and current_spread_price is None:
            return self.reject_missing_risk_inputs(signal, timestamp, ["CURRENT_SPREAD"])

        # ==============================================================
        # 2. LIMITES
        # ==============================================================

        limit_reason = self.limits.validate(
            account,
            current_spread_pips,
            current_spread_price=current_spread_price,
            stop_distance_price=(
                float(signal.suggested_sl_distance)
                if signal.suggested_sl_distance is not None
                else None
            ),
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
        price_digits = (
            int(symbol_info.digits)
            if symbol_info is not None and symbol_info.digits is not None
            else 5
        )
        if signal.signal == SignalType.BUY:
            sl_price = round(current_price - sl_distance, price_digits)
            tp_price = round(current_price + tp_distance, price_digits)
        else:
            sl_price = round(current_price + sl_distance, price_digits)
            tp_price = round(current_price - tp_distance, price_digits)

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
            self.sizer.get_risk_amount(account.balance),
            2,
        )

        risk_percentage = round(
            self.sizer.get_risk_percentage(),
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
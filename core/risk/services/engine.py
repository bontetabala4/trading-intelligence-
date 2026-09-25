from datetime import datetime, timezone
from core.strategy.domain.models import StrategySignal
from core.strategy.domain.enums import SignalType
from core.risk.domain.models import AccountState, OrderProposal
from core.risk.domain.enums import RiskStatus, RiskRejectReason
from core.risk.services.sizer import PositionSizer
from core.risk.services.limits import RiskLimitsChecker

class RiskEngine:
    def __init__(self, sizer: PositionSizer = None, limits: RiskLimitsChecker = None):
        self.sizer = sizer or PositionSizer()
        self.limits = limits or RiskLimitsChecker()

    def evaluate_signal(
        self,
        signal: StrategySignal,
        account: AccountState,
        current_price: float,
        current_spread_pips: float = 1.0,
        pip_size: float = 0.0001
    ) -> OrderProposal:
        now = datetime.now(timezone.utc)
        audit_trail = [f"SIGNAL_RECEIVED_{signal.signal.value}"]

        # 1. Filtre signal NEUTRAL
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
                timestamp=now,
                status=RiskStatus.REJECTED,
                reject_reason=RiskRejectReason.SIGNAL_NEUTRAL,
                audit_trail=["REJECTED_NEUTRAL_SIGNAL"]
            )

        # 2. Vérification des limites de compte / marché
        limit_reason = self.limits.validate(account, current_spread_pips)
        if limit_reason != RiskRejectReason.NONE:
            audit_trail.append(f"REJECTED_LIMIT_{limit_reason.value}")
            return OrderProposal(
                symbol=signal.symbol,
                signal_type=signal.signal,
                strategy_id=signal.strategy_id,
                volume_lots=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_amount_account_currency=0.0,
                risk_percentage=0.0,
                timestamp=now,
                status=RiskStatus.REJECTED,
                reject_reason=limit_reason,
                audit_trail=audit_trail
            )

        # 3. Calcul SL / TP absolus
        sl_pips = signal.suggested_sl_pips or 15.0
        tp_pips = signal.suggested_tp_pips or 30.0

        if signal.signal == SignalType.BUY:
            sl_price = round(current_price - (sl_pips * pip_size), 5)
            tp_price = round(current_price + (tp_pips * pip_size), 5)
        else:
            sl_price = round(current_price + (sl_pips * pip_size), 5)
            tp_price = round(current_price - (tp_pips * pip_size), 5)

        # 4. Calcul de la taille de lot
        volume_lots = self.sizer.calculate_lot_size(account.balance, sl_pips)

        if volume_lots <= 0.0:
            audit_trail.append("REJECTED_VOLUME_BELOW_MINIMUM")
            return OrderProposal(
                symbol=signal.symbol,
                signal_type=signal.signal,
                strategy_id=signal.strategy_id,
                volume_lots=0.0,
                stop_loss=sl_price,
                take_profit=tp_price,
                risk_amount_account_currency=0.0,
                risk_percentage=0.0,
                timestamp=now,
                status=RiskStatus.REJECTED,
                reject_reason=RiskRejectReason.INSUFFICIENT_MARGIN,
                audit_trail=audit_trail
            )

        risk_currency = round(account.balance * self.sizer.risk_per_trade_pct, 2)
        audit_trail.append(f"APPROVED_VOLUME_{volume_lots}_LOTS")

        return OrderProposal(
            symbol=signal.symbol,
            signal_type=signal.signal,
            strategy_id=signal.strategy_id,
            volume_lots=volume_lots,
            stop_loss=sl_price,
            take_profit=tp_price,
            risk_amount_account_currency=risk_currency,
            risk_percentage=round(self.sizer.risk_per_trade_pct * 100, 2),
            timestamp=now,
            status=RiskStatus.APPROVED,
            reject_reason=RiskRejectReason.NONE,
            audit_trail=audit_trail
        )
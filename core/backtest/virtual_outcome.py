import uuid
from dataclasses import replace
from typing import Optional
 
from core.backtest.domain import BacktestCostModel, VirtualTrade, ExitReason
from core.signal.domain import FinalSignal, FinalSignalDirection
 
 
class VirtualOutcomeEngine:
 
    @staticmethod
    def create_trade_from_signal(
        signal: FinalSignal,
        entry_price: float,
        cost_model: BacktestCostModel,
    ) -> Optional[VirtualTrade]:
        
        if signal.direction not in (FinalSignalDirection.BUY, FinalSignalDirection.SELL):
            return None
 
        if signal.stop_reference is None or signal.target_reference is None:
            return None
 
        is_long = signal.direction == FinalSignalDirection.BUY
 
        # Coût d'entrée : slippage (toujours défavorable) + moitié du spread
        slippage_price = cost_model.slippage_points * cost_model.point_value
        half_spread_price = (cost_model.spread_points * cost_model.point_value) / 2.0
 
        if is_long:
            adjusted_entry = entry_price + slippage_price + half_spread_price
        else:
            adjusted_entry = entry_price - slippage_price - half_spread_price
 
        risk_r_amount = abs(adjusted_entry - signal.stop_reference)
        if risk_r_amount <= 0:
            return None
 
        return VirtualTrade(
            trade_id=str(uuid.uuid4()),
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction=signal.direction.value,
            entry_timestamp=signal.timestamp,
            entry_price=adjusted_entry,
            stop_reference=signal.stop_reference,
            target_reference=signal.target_reference,
            risk_r_amount=risk_r_amount,
            strategy=signal.strategy,
            market_regime=signal.market_regime,
            is_open=True,
        )
 
    @staticmethod
    def evaluate_trade(
        trade: VirtualTrade,
        current_bar,
        cost_model: BacktestCostModel,
    ) -> VirtualTrade:
      
        if not trade.is_open:
            return trade
 
        is_long = trade.direction == "BUY"
        high = current_bar.high
        low = current_bar.low
        timestamp = current_bar.timestamp
 
        stop_hit = (low <= trade.stop_reference) if is_long else (high >= trade.stop_reference)
        target_hit = (high >= trade.target_reference) if is_long else (low <= trade.target_reference)
 
        if stop_hit and target_hit:
            raw_exit_price = trade.stop_reference
            exit_reason = ExitReason.AMBIGUOUS_BAR_STOP_HIT
        elif stop_hit:
            raw_exit_price = trade.stop_reference
            exit_reason = ExitReason.STOP_HIT
        elif target_hit:
            raw_exit_price = trade.target_reference
            exit_reason = ExitReason.TARGET_HIT
        else:
            return trade  # toujours ouvert, rien à faire cette bougie
 
        # Slippage de sortie (toujours défavorable)
        slippage_price = cost_model.slippage_points * cost_model.point_value
        adjusted_exit = (raw_exit_price - slippage_price) if is_long else (raw_exit_price + slippage_price)
 
        if is_long:
            gross_result_r = (adjusted_exit - trade.entry_price) / trade.risk_r_amount
        else:
            gross_result_r = (trade.entry_price - adjusted_exit) / trade.risk_r_amount
 
        net_result_r = gross_result_r - cost_model.commission_per_trade_r
 
        return replace(
            trade,
            exit_timestamp=timestamp,
            exit_price=adjusted_exit,
            exit_reason=exit_reason,
            gross_result_r=gross_result_r,
            net_result_r=net_result_r,
            holding_bars=trade.holding_bars + 1,
            is_open=False,
        )
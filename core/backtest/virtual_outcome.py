import math
import uuid
from dataclasses import replace
from typing import Optional
 
from core.backtest.domain import BacktestCostModel, VirtualTrade, ExitReason
from core.signal.domain import FinalSignal, FinalSignalDirection
 
 
class VirtualOutcomeEngine:

    @staticmethod
    def _effective_spread_price(cost_model: BacktestCostModel, spread_price: float | None) -> float:
        if spread_price is None:
            if cost_model.use_bar_spread:
                raise ValueError(
                    "spread_price explicite requis avec use_bar_spread=True; "
                    "résoudre le spread de la bougie avant d'évaluer le trade."
                )
            value = cost_model.spread_points * cost_model.point_value
        else:
            value = float(spread_price)
        if not math.isfinite(value) or value < 0:
            raise ValueError("spread_price doit être fini et positif ou nul.")
        return value

    @staticmethod
    def _adjusted_entry_price(
        entry_price: float,
        is_long: bool,
        cost_model: BacktestCostModel,
        spread_price: float,
    ) -> float:
        slippage = cost_model.slippage_points * cost_model.point_value
        half_spread = spread_price / 2.0
        basis = cost_model.price_basis
        if basis == "MID":
            spread_adjustment = half_spread if is_long else -half_spread
        elif basis == "BID":
            spread_adjustment = spread_price if is_long else 0.0
        else:  # ASK-based OHLC
            spread_adjustment = 0.0 if is_long else -spread_price
        return entry_price + spread_adjustment + (slippage if is_long else -slippage)

    @staticmethod
    def create_trade_from_signal(
        signal: FinalSignal,
        entry_price: float,
        cost_model: BacktestCostModel,
        spread_price: float | None = None,
    ) -> Optional[VirtualTrade]:

        if signal.direction not in (FinalSignalDirection.BUY, FinalSignalDirection.SELL):
            return None
 
        if signal.stop_reference is None or signal.target_reference is None:
            return None
 
        is_long = signal.direction == FinalSignalDirection.BUY
        effective_spread_price = VirtualOutcomeEngine._effective_spread_price(
            cost_model, spread_price
        )
        adjusted_entry = VirtualOutcomeEngine._adjusted_entry_price(
            entry_price, is_long, cost_model, effective_spread_price
        )
 
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
    def create_trade_from_order(
        signal: FinalSignal,
        order_proposal,
        entry_price: float,
        cost_model: BacktestCostModel,
        spread_price: float | None = None,
    ) -> Optional[VirtualTrade]:

        if order_proposal is None:
            return None

        if signal.direction not in (
            FinalSignalDirection.BUY,
            FinalSignalDirection.SELL,
        ):
            return None

        if order_proposal.volume_lots <= 0:
            return None

        is_long = signal.direction == FinalSignalDirection.BUY
        effective_spread_price = VirtualOutcomeEngine._effective_spread_price(
            cost_model, spread_price
        )
        adjusted_entry = VirtualOutcomeEngine._adjusted_entry_price(
            entry_price, is_long, cost_model, effective_spread_price
        )

        stop_reference = order_proposal.stop_loss
        target_reference = order_proposal.take_profit

        risk_r_amount = abs(
            adjusted_entry - stop_reference
        )

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
            stop_reference=stop_reference,
            target_reference=target_reference,
            risk_r_amount=risk_r_amount,
            volume_lots=order_proposal.volume_lots,
            risk_amount_account_currency=(
                order_proposal.risk_amount_account_currency
            ),
            strategy=signal.strategy,
            market_regime=signal.market_regime,
            is_open=True,
        )
 
    @staticmethod
    def evaluate_trade(
        trade: VirtualTrade,
        current_bar,
        cost_model: BacktestCostModel,
        spread_price: float | None = None,
    ) -> VirtualTrade:

        if not trade.is_open:
            return trade
 
        is_long = trade.direction == "BUY"
        high = float(current_bar.high)
        low = float(current_bar.low)
        timestamp = current_bar.timestamp
        effective_spread_price = VirtualOutcomeEngine._effective_spread_price(
            cost_model, spread_price
        )
        bid_high, bid_low, ask_high, ask_low = cost_model.quote_bar_range(
            current_bar, effective_spread_price
        )

        # A long closes on Bid; a short closes on Ask. Stops/targets are
        # tested on the executable quote side rather than the raw candle side.
        if is_long:
            stop_hit = bid_low <= trade.stop_reference
            target_hit = bid_high >= trade.target_reference
        else:
            stop_hit = ask_high >= trade.stop_reference
            target_hit = ask_low <= trade.target_reference
 
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
 
        # SL/TP represent executable exit-side levels; spread was applied
        # when deriving Bid/Ask ranges and must not be deducted a second time.
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
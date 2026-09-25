from typing import Dict, Any
from core.strategy.strategies.base import BaseStrategy
from core.strategy.domain.enums import StrategyID, SignalType
from core.strategy.domain.models import StrategySignal
from core.regime.domain.models import MarketRegime
from core.regime.domain.enums import TrendRegime

class TrendFollowingStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            strategy_id=StrategyID.TREND_FOLLOWING,
            compatible_regimes=[TrendRegime.TRENDING_BULL.value, TrendRegime.TRENDING_BEAR.value]
        )

    def evaluate(self, regime: MarketRegime, features: Dict[str, Any]) -> StrategySignal:
        rsi_14 = features.get("rsi_14", 50.0)
        atr_14 = features.get("atr_14", 0.0010)

        evidence = [f"REGIME_MATCH_{regime.regime.value}"]
        signal_type = SignalType.NEUTRAL
        strength = 0.0

        if regime.regime == TrendRegime.TRENDING_BULL:
            if 50.0 <= rsi_14 < 70.0:
                signal_type = SignalType.BUY
                strength = round(min(1.0, 0.5 + (rsi_14 - 50.0) / 40.0), 2)
                evidence.append(f"RSI_BULLISH_CONTINUATION_{rsi_14:.2f}")
            else:
                evidence.append("RSI_OVERBOUGHT_OR_WEAK")

        elif regime.regime == TrendRegime.TRENDING_BEAR:
            if 30.0 < rsi_14 <= 50.0:
                signal_type = SignalType.SELL
                strength = round(min(1.0, 0.5 + (50.0 - rsi_14) / 40.0), 2)
                evidence.append(f"RSI_BEARISH_CONTINUATION_{rsi_14:.2f}")
            else:
                evidence.append("RSI_OVERSOLD_OR_WEAK")

        sl_pips = round(atr_14 * 1.5 * 10000, 1) if atr_14 else 15.0
        tp_pips = round(atr_14 * 3.0 * 10000, 1) if atr_14 else 30.0

        return StrategySignal(
            symbol=regime.symbol,
            timeframe=regime.timeframe,
            timestamp=regime.timestamp,
            strategy_id=self.strategy_id,
            signal=signal_type,
            strength=strength,
            regime_context=regime.regime,
            evidence=evidence,
            suggested_sl_pips=sl_pips,
            suggested_tp_pips=tp_pips
        )
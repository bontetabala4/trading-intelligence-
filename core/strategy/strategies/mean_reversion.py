from typing import Dict, Any
from core.strategy.strategies.base import BaseStrategy
from core.strategy.domain.enums import StrategyID, SignalType
from core.strategy.domain.models import StrategySignal
from core.regime.domain.models import MarketRegime
from core.regime.domain.enums import TrendRegime

class MeanReversionStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            strategy_id=StrategyID.MEAN_REVERSION,
            compatible_regimes=[TrendRegime.RANGING.value]
        )

    def evaluate(self, regime: MarketRegime, features: Dict[str, Any]) -> StrategySignal:
        rsi_14 = features.get("rsi_14", 50.0)
        atr_14 = features.get("atr_14", 0.0010)

        evidence = [f"REGIME_MATCH_{regime.regime.value}"]
        signal_type = SignalType.NEUTRAL
        strength = 0.0

        if rsi_14 <= 35.0:
            signal_type = SignalType.BUY
            strength = round(min(1.0, (35.0 - rsi_14) / 20.0 + 0.5), 2)
            evidence.append(f"RSI_OVERSOLD_IN_RANGE_{rsi_14:.2f}")
        elif rsi_14 >= 65.0:
            signal_type = SignalType.SELL
            strength = round(min(1.0, (rsi_14 - 65.0) / 20.0 + 0.5), 2)
            evidence.append(f"RSI_OVERBOUGHT_IN_RANGE_{rsi_14:.2f}")
        else:
            evidence.append("RSI_IN_NEUTRAL_RANGE_ZONE")

        sl_distance = round(atr_14 * 1.0, 8) if atr_14 else 0.0010
        tp_distance = round(atr_14 * 1.5, 8) if atr_14 else 0.0015

        return StrategySignal(
            symbol=regime.symbol,
            timeframe=regime.timeframe,
            timestamp=regime.timestamp,
            strategy_id=self.strategy_id,
            signal=signal_type,
            strength=strength,
            regime_context=regime.regime,
            evidence=evidence,
            suggested_sl_distance=sl_distance,
            suggested_tp_distance=tp_distance
        )
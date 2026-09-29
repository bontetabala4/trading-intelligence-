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
            compatible_regimes=[
                TrendRegime.TRENDING_BULL.value,
                TrendRegime.TRENDING_BEAR.value,
            ],
        )

    def evaluate(
        self,
        regime: MarketRegime,
        features: Dict[str, Any],
    ) -> StrategySignal:

        rsi_14 = features.get("rsi_14", 50.0)
        atr_14 = features.get("atr_14", 0.0010)

        evidence = [
            f"REGIME_MATCH_{regime.regime.value}"
        ]

        signal_type = SignalType.NEUTRAL
        strength = 0.0

        if regime.regime == TrendRegime.TRENDING_BULL:
            if 50.0 <= rsi_14 < 70.0:
                signal_type = SignalType.BUY
                strength = round(
                    min(1.0, 0.5 + (rsi_14 - 50.0) / 40.0),
                    2,
                )
                evidence.append(
                    f"RSI_BULLISH_CONTINUATION_{rsi_14:.2f}"
                )
            else:
                evidence.append(
                    "RSI_OVERBOUGHT_OR_WEAK"
                )

        elif regime.regime == TrendRegime.TRENDING_BEAR:
            if 30.0 < rsi_14 <= 50.0:
                signal_type = SignalType.SELL
                strength = round(
                    min(1.0, 0.5 + (50.0 - rsi_14) / 40.0),
                    2,
                )
                evidence.append(
                    f"RSI_BEARISH_CONTINUATION_{rsi_14:.2f}"
                )
            else:
                evidence.append(
                    "RSI_OVERSOLD_OR_WEAK"
                )

        # ==========================================================
        # SL / TP
        # ==========================================================
        #
        # Les distances sont exprimées directement dans l'unité
        # de prix du symbole.
        #
        # Exemple XAUUSD :
        # ATR = 2.3793
        # SL = 3.5690
        # TP = 7.1381
        #
        sl_distance = (
            round(atr_14 * 1.5, 8)
            if atr_14
            else 0.0015
        )

        tp_distance = (
            round(atr_14 * 3.0, 8)
            if atr_14
            else 0.0030
        )

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
            suggested_tp_distance=tp_distance,
            engine_version="1.0.0",
        )
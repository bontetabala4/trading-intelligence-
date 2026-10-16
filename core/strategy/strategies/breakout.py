"""
BreakoutPriceActionStrategy — Inspiration Jesse Livermore / Price Action.
Cassure d'un range clé (plus haut/bas sur N périodes) avec expansion de volatilité
et confirmation de volume (si disponible).
Stop d'invalidation strict et prévention des faux signaux (wicks).
"""
from typing import Any, Dict

from core.regime.domain.enums import TrendRegime
from core.regime.domain.models import MarketRegime
from core.strategy.domain.enums import SignalType, StrategyID
from core.strategy.domain.models import StrategySignal
from core.strategy.strategies.base import BaseStrategy


class BreakoutPriceActionStrategy(BaseStrategy):
    """
    Stratégie de cassure / Price Action.

    Règles :
    - Cassure haussière : Close > Highest High du range passé avec confirmation momentum/volume.
    - Cassure baissière : Close < Lowest Low du range passé avec confirmation momentum/volume.
    - Filtre de volume : Si volume disponible, exige un volume supérieur à la moyenne.
    - Invalidation / SL : 1.5 * ATR_14, TP : 3.0 * ATR_14 (Ratio 2R).
    """

    def __init__(self, lookback_period: int = 20):
        super().__init__(
            strategy_id=StrategyID.BREAKOUT_PRICE_ACTION,
            compatible_regimes=[
                TrendRegime.TRENDING_BULL.value,
                TrendRegime.TRENDING_BEAR.value,
                TrendRegime.RANGING.value,
            ],
        )
        self.lookback_period = lookback_period

    def evaluate(
        self,
        regime: MarketRegime,
        features: Dict[str, Any],
    ) -> StrategySignal:
        close = features.get("close")
        atr_14 = features.get("atr_14", 0.0010)
        rsi_14 = features.get("rsi_14", 50.0)

        # Features de range / breakout (calculées ou extraites des bandes/momentum)
        rolling_high = features.get("rolling_high_20") or features.get("donchian_high_20")
        rolling_low = features.get("rolling_low_20") or features.get("donchian_low_20")
        volume_ratio = features.get("volume_ratio", 1.0)

        evidence = [f"REGIME_{regime.regime.value}"]

        # Fallback de calcul si les features directes ne sont pas encore sérialisées
        bb_upper = features.get("bollinger_upper_20")
        bb_lower = features.get("bollinger_lower_20")

        signal_type = SignalType.NEUTRAL
        strength = 0.0

        if close is None:
            evidence.append("MISSING_CLOSE_PRICE")
            return self._build_signal(regime, signal_type, strength, evidence, atr_14)

        # Cassure haussière
        is_bullish_breakout = False
        if rolling_high is not None and close > rolling_high:
            is_bullish_breakout = True
            evidence.append(f"BREAKOUT_ABOVE_ROLLING_HIGH_{rolling_high:.5f}")
        elif bb_upper is not None and close > bb_upper:
            is_bullish_breakout = True
            evidence.append(f"BREAKOUT_ABOVE_BOLLINGER_UPPER_{bb_upper:.5f}")

        # Cassure baissière
        is_bearish_breakout = False
        if rolling_low is not None and close < rolling_low:
            is_bearish_breakout = True
            evidence.append(f"BREAKOUT_BELOW_ROLLING_LOW_{rolling_low:.5f}")
        elif bb_lower is not None and close < bb_lower:
            is_bearish_breakout = True
            evidence.append(f"BREAKOUT_BELOW_BOLLINGER_LOWER_{bb_lower:.5f}")

        # Validation avec momentum & volume
        if is_bullish_breakout:
            if rsi_14 >= 55.0 and volume_ratio >= 1.0:
                signal_type = SignalType.BUY
                strength = 0.8
                evidence.append(f"VOLUME_MOMENTUM_CONFIRMED_RSI_{rsi_14:.1f}")
            else:
                evidence.append("BREAKOUT_UNCONFIRMED_BY_MOMENTUM")

        elif is_bearish_breakout:
            if rsi_14 <= 45.0 and volume_ratio >= 1.0:
                signal_type = SignalType.SELL
                strength = 0.8
                evidence.append(f"VOLUME_MOMENTUM_CONFIRMED_RSI_{rsi_14:.1f}")
            else:
                evidence.append("BREAKOUT_UNCONFIRMED_BY_MOMENTUM")
        else:
            evidence.append("INSIDE_RANGE_NO_BREAKOUT")

        return self._build_signal(regime, signal_type, strength, evidence, atr_14)

    def _build_signal(
        self,
        regime: MarketRegime,
        signal_type: SignalType,
        strength: float,
        evidence: list[str],
        atr_14: float,
    ) -> StrategySignal:
        sl_distance = round(atr_14 * 1.5, 8) if atr_14 else 0.0015
        tp_distance = round(atr_14 * 3.0, 8) if atr_14 else 0.0030

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

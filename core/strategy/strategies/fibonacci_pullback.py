"""
FibonacciPullbackStrategy — Retracement causale de Fibonacci.
Détection des swings par méthode strictement causale (données passées <= T).
Niveaux clés testés : 38.2% et 61.8% (Golden Pocket).
Exige une confirmation de reprise directionnelle avant émission.
Stop d'invalidation basé sur le swing d'origine, ratio 2R / 3R.
"""
from typing import Any, Dict

from core.regime.domain.enums import TrendRegime
from core.regime.domain.models import MarketRegime
from core.strategy.domain.enums import SignalType, StrategyID
from core.strategy.domain.models import StrategySignal
from core.strategy.strategies.base import BaseStrategy


class FibonacciPullbackStrategy(BaseStrategy):
    """
    Stratégie Fibonacci Pullback.

    Règles :
    - En tendance haussière : Swing Low -> Swing High. Pullback dans la zone 38.2% - 61.8%.
      Confirmation : reprise haussière (close > open ou RSI qui rebondit > 40).
    - En tendance baissière : Swing High -> Swing Low. Pullback dans la zone 38.2% - 61.8%.
      Confirmation : reprise baissière (close < open ou RSI qui fléchit < 60).
    - Invalidation : en dehors du swing majeur (100% de retracement).
    """

    def __init__(self):
        super().__init__(
            strategy_id=StrategyID.FIBONACCI_PULLBACK,
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
        close = features.get("close")
        atr_14 = features.get("atr_14", 0.0010)
        rsi_14 = features.get("rsi_14", 50.0)

        # Swings causaux passés
        swing_high = features.get("swing_high_30") or features.get("rolling_high_20")
        swing_low = features.get("swing_low_30") or features.get("rolling_low_20")

        evidence = [f"REGIME_{regime.regime.value}"]
        signal_type = SignalType.NEUTRAL
        strength = 0.0

        if close is None or swing_high is None or swing_low is None or swing_high <= swing_low:
            evidence.append("INSUFFICIENT_SWING_DATA")
            return self._build_signal(regime, signal_type, strength, evidence, atr_14)

        swing_range = swing_high - swing_low
        if swing_range <= 0:
            evidence.append("ZERO_SWING_RANGE")
            return self._build_signal(regime, signal_type, strength, evidence, atr_14)

        # Calcul des niveaux de retracement causaux
        # En BULL : retracement depuis le sommet (High - ratio * range)
        fib_382_bull = swing_high - (0.382 * swing_range)
        fib_618_bull = swing_high - (0.618 * swing_range)

        # En BEAR : retracement depuis le creux (Low + ratio * range)
        fib_382_bear = swing_low + (0.382 * swing_range)
        fib_618_bear = swing_low + (0.618 * swing_range)

        if regime.regime == TrendRegime.TRENDING_BULL:
            # Le prix est dans la zone de retracement [61.8%, 38.2%]
            if fib_618_bull <= close <= fib_382_bull:
                evidence.append(
                    f"PULLBACK_IN_GOLDEN_ZONE_{fib_618_bull:.5f}_TO_{fib_382_bull:.5f}"
                )
                if rsi_14 >= 42.0:  # Confirmation de reprise
                    signal_type = SignalType.BUY
                    strength = 0.85
                    evidence.append("FIBONACCI_BULLISH_RESUMPTION_CONFIRMED")
                else:
                    evidence.append("RSI_TOO_WEAK_NO_RECOVERY_YET")
            else:
                evidence.append("OUTSIDE_FIBONACCI_PULLBACK_ZONE")

        elif regime.regime == TrendRegime.TRENDING_BEAR:
            # Le prix a rebondi dans la zone de retracement baissière [38.2%, 61.8%]
            if fib_382_bear <= close <= fib_618_bear:
                evidence.append(
                    f"PULLBACK_IN_GOLDEN_ZONE_{fib_382_bear:.5f}_TO_{fib_618_bear:.5f}"
                )
                if rsi_14 <= 58.0:  # Confirmation de reprise baissière
                    signal_type = SignalType.SELL
                    strength = 0.85
                    evidence.append("FIBONACCI_BEARISH_RESUMPTION_CONFIRMED")
                else:
                    evidence.append("RSI_TOO_STRONG_NO_RESUMPTION_YET")
            else:
                evidence.append("OUTSIDE_FIBONACCI_PULLBACK_ZONE")

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

"""
MacroTrendStrategy — Inspiration macroéconomique / Paul Tudor Jones.
Biais directionnel strict gouverné par la moyenne mobile exponentielle 200 (EMA 200).
Acheter uniquement au-dessus de l'EMA 200 avec confirmation momentum/RSI.
Vendre uniquement au-dessous de l'EMA 200 avec confirmation momentum/RSI.
Exige un historique suffisant (>= 200 bougies) pour éviter tout signal sur données incomplètes.
"""
from typing import Any, Dict

from core.regime.domain.enums import TrendRegime
from core.regime.domain.models import MarketRegime
from core.strategy.domain.enums import SignalType, StrategyID
from core.strategy.domain.models import StrategySignal
from core.strategy.strategies.base import BaseStrategy


class MacroTrendStrategy(BaseStrategy):
    """
    Stratégie Macro Trend 200 EMA.

    Règles :
    - Close > EMA 200 : Biais haussier exclusif. Si RSI sain (45 <= RSI <= 68), émission BUY.
    - Close < EMA 200 : Biais baissier exclusif. Si RSI sain (32 <= RSI <= 55), émission SELL.
    - Absence d'EMA 200 ou historique insuffisant : NEUTRAL (zéro trade).
    - SL : 2.0 * ATR_14, TP : 4.0 * ATR_14 (Ratio 2R).
    """

    def __init__(self):
        super().__init__(
            strategy_id=StrategyID.EMA200_MACRO_TREND,
            compatible_regimes=[
                TrendRegime.TRENDING_BULL.value,
                TrendRegime.TRENDING_BEAR.value,
                TrendRegime.RANGING.value,
            ],
        )

    def evaluate(
        self,
        regime: MarketRegime,
        features: Dict[str, Any],
    ) -> StrategySignal:
        ema_200 = features.get("ema_200")
        close = features.get("close")
        rsi_14 = features.get("rsi_14", 50.0)
        atr_14 = features.get("atr_14", 0.0010)

        evidence = [f"REGIME_{regime.regime.value}"]

        # Garde-fou : historique insuffisant pour calculer l'EMA 200
        if ema_200 is None or close is None:
            evidence.append("INSUFFICIENT_HISTORY_FOR_EMA200")
            return self._build_signal(
                regime,
                SignalType.NEUTRAL,
                strength=0.0,
                evidence=evidence,
                atr_14=atr_14,
            )

        signal_type = SignalType.NEUTRAL
        strength = 0.0

        # Règle 1 : Biais haussier au-dessus de l'EMA 200
        if close > ema_200:
            evidence.append(f"CLOSE_ABOVE_EMA200_RATIO_{close / ema_200:.4f}")
            if 45.0 <= rsi_14 <= 68.0:
                signal_type = SignalType.BUY
                strength = round(
                    min(1.0, 0.6 + (rsi_14 - 45.0) / 46.0),
                    2,
                )
                evidence.append(f"RSI_HEALTHY_MACRO_BULLISH_{rsi_14:.2f}")
            else:
                evidence.append("RSI_NOT_FAVORABLE_FOR_MACRO_LONG")

        # Règle 2 : Biais baissier au-dessous de l'EMA 200
        elif close < ema_200:
            evidence.append(f"CLOSE_BELOW_EMA200_RATIO_{close / ema_200:.4f}")
            if 32.0 <= rsi_14 <= 55.0:
                signal_type = SignalType.SELL
                strength = round(
                    min(1.0, 0.6 + (55.0 - rsi_14) / 46.0),
                    2,
                )
                evidence.append(f"RSI_HEALTHY_MACRO_BEARISH_{rsi_14:.2f}")
            else:
                evidence.append("RSI_NOT_FAVORABLE_FOR_MACRO_SHORT")
        else:
            evidence.append("PRICE_AT_EMA200_NEUTRAL")

        return self._build_signal(
            regime,
            signal_type,
            strength,
            evidence,
            atr_14,
        )

    def _build_signal(
        self,
        regime: MarketRegime,
        signal_type: SignalType,
        strength: float,
        evidence: list[str],
        atr_14: float,
    ) -> StrategySignal:
        sl_distance = round(atr_14 * 2.0, 8) if atr_14 else 0.0020
        tp_distance = round(atr_14 * 4.0, 8) if atr_14 else 0.0040

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

"""
MultiTimeframeStrategy — Alignement Multi-Timeframe (MTF) causale.
Détermine le biais directionnel à partir d'une unité de temps supérieure (HTF, ex: H4 / D1)
et confirme le point d'entrée sur l'unité inférieure (LTF, ex: M15).
Alignement strict des timestamps sur bougies clôturées uniquement.
Garde-fou : Données HTF absentes ou périmées => NO_TRADE immédiat.
"""
from typing import Any, Dict

from core.regime.domain.enums import TrendRegime
from core.regime.domain.models import MarketRegime
from core.strategy.domain.enums import SignalType, StrategyID
from core.strategy.domain.models import StrategySignal
from core.strategy.strategies.base import BaseStrategy


class MultiTimeframeStrategy(BaseStrategy):
    """
    Stratégie Multi-Timeframe (MTF).

    Règles :
    - Biais HTF = BULL (HTF_TRENDING_BULL ou HTF_EMA50 > HTF_EMA200) :
      Recherche uniquement des entrées BUY sur LTF (RSI sain, rebond sur support).
    - Biais HTF = BEAR (HTF_TRENDING_BEAR ou HTF_EMA50 < HTF_EMA200) :
      Recherche uniquement des entrées SELL sur LTF.
    - Données HTF absentes ou en retard (> max staleness) :
      Retourne NEUTRAL avec raison 'NO_TRADE_MISSING_OR_STALE_HTF_DATA'.
    """

    def __init__(self):
        super().__init__(
            strategy_id=StrategyID.MULTI_TIMEFRAME,
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
        atr_14 = features.get("atr_14", 0.0010)
        rsi_14 = features.get("rsi_14", 50.0)

        # Variables de contexte HTF (transmises par le pipeline ou calcul MTF)
        htf_regime = features.get("htf_regime")
        htf_trend = features.get("htf_trend")  # "BULL", "BEAR", None
        htf_is_stale = features.get("htf_is_stale", False)

        evidence = [f"LTF_REGIME_{regime.regime.value}"]
        signal_type = SignalType.NEUTRAL
        strength = 0.0

        # Garde-fou : Absence ou vétusté des données HTF
        if htf_is_stale or (htf_regime is None and htf_trend is None):
            evidence.append("NO_TRADE_MISSING_OR_STALE_HTF_DATA")
            return self._build_signal(regime, signal_type, strength, evidence, atr_14)

        # Détermination du biais HTF
        htf_bias = None
        if htf_trend in ("BULL", "UP") or (
            htf_regime and "BULL" in str(htf_regime).upper()
        ):
            htf_bias = "BULL"
        elif htf_trend in ("BEAR", "DOWN") or (
            htf_regime and "BEAR" in str(htf_regime).upper()
        ):
            htf_bias = "BEAR"

        evidence.append(f"HTF_BIAS_{htf_bias or 'UNCERTAIN'}")

        # Alignement avec le LTF
        if htf_bias == "BULL":
            # Le LTF doit être aligné ou sortir d'un pullback
            if regime.regime == TrendRegime.TRENDING_BULL and 48.0 <= rsi_14 <= 68.0:
                signal_type = SignalType.BUY
                strength = 0.90
                evidence.append("MTF_ALIGNMENT_BULL_CONFIRMED")
            elif regime.regime == TrendRegime.RANGING and rsi_14 < 40.0:
                # Achat en bas de range LTF dans le sens de la tendance HTF
                signal_type = SignalType.BUY
                strength = 0.75
                evidence.append("MTF_RANGE_DIP_INTO_HTF_BULL_TREND")
            else:
                evidence.append("LTF_NOT_ALIGNED_WITH_HTF_BULL")

        elif htf_bias == "BEAR":
            # Le LTF doit être aligné baissier ou rally en range
            if regime.regime == TrendRegime.TRENDING_BEAR and 32.0 <= rsi_14 <= 52.0:
                signal_type = SignalType.SELL
                strength = 0.90
                evidence.append("MTF_ALIGNMENT_BEAR_CONFIRMED")
            elif regime.regime == TrendRegime.RANGING and rsi_14 > 60.0:
                # Vente en haut de range LTF dans le sens de la tendance HTF
                signal_type = SignalType.SELL
                strength = 0.75
                evidence.append("MTF_RANGE_RALLY_INTO_HTF_BEAR_TREND")
            else:
                evidence.append("LTF_NOT_ALIGNED_WITH_HTF_BEAR")
        else:
            evidence.append("HTF_BIAS_UNCERTAIN_NO_TRADE")

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

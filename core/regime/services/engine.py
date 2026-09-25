from datetime import datetime
from typing import Dict, Any, List
from core.regime.domain.enums import TrendRegime, VolatilityState, ConfidenceLevel
from core.regime.domain.models import MarketRegime

class MarketRegimeEngine:
    def __init__(self, ema_slope_min: float = 0.0001, rsi_bull_min: float = 52.0, rsi_bear_max: float = 48.0):
        self.ema_slope_min = ema_slope_min
        self.rsi_bull_min = rsi_bull_min
        self.rsi_bear_max = rsi_bear_max

    def evaluate(self, symbol: str, timeframe: str, timestamp: datetime, features: Dict[str, Any], data_quality: str) -> MarketRegime:
        evidence: List[str] = []
        
        # 1. Vérification de la qualité des données
        if data_quality != "VALID":
            return MarketRegime(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                regime=TrendRegime.UNCERTAIN,
                volatility_state=VolatilityState.NORMAL_VOLATILITY,
                strength=0.0,
                confidence=ConfidenceLevel.LOW,
                evidence=["DATA_QUALITY_NOT_VALID"],
                data_quality=data_quality
            )

        # 2. Vérification de la présence des features requises
        ema_20 = features.get("ema_20")
        ema_50 = features.get("ema_50")
        rsi_14 = features.get("rsi_14")
        atr_14 = features.get("atr_14")
        true_range = features.get("true_range")

        if None in (ema_20, ema_50, rsi_14):
            return MarketRegime(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                regime=TrendRegime.UNCERTAIN,
                volatility_state=VolatilityState.NORMAL_VOLATILITY,
                strength=0.0,
                confidence=ConfidenceLevel.LOW,
                evidence=["INSUFFICIENT_HISTORICAL_DATA_FOR_INDICATORS"],
                data_quality=data_quality
            )

        # 3. Évaluation de la Volatilité
        vol_state = VolatilityState.NORMAL_VOLATILITY
        if atr_14 and true_range:
            if true_range > (atr_14 * 1.8):
                vol_state = VolatilityState.EXPANSION
                evidence.append("VOLATILITY_EXPANSION_DETECTED")
            elif true_range < (atr_14 * 0.6):
                vol_state = VolatilityState.CONTRACTION
                evidence.append("VOLATILITY_CONTRACTION_DETECTED")

        # 4. Classification de Tendance
        regime = TrendRegime.RANGING
        strength = 0.5
        confidence = ConfidenceLevel.MEDIUM

        if ema_20 > ema_50 and rsi_14 >= self.rsi_bull_min:
            regime = TrendRegime.TRENDING_BULL
            strength = min(1.0, 0.5 + (rsi_14 - 50) / 100)
            confidence = ConfidenceLevel.HIGH
            evidence.append(f"EMA_20 ({ema_20:.4f}) > EMA_50 ({ema_50:.4f})")
            evidence.append(f"RSI_14 ({rsi_14:.2f}) >= {self.rsi_bull_min}")

        elif ema_20 < ema_50 and rsi_14 <= self.rsi_bear_max:
            regime = TrendRegime.TRENDING_BEAR
            strength = min(1.0, 0.5 + (50 - rsi_14) / 100)
            confidence = ConfidenceLevel.HIGH
            evidence.append(f"EMA_20 ({ema_20:.4f}) < EMA_50 ({ema_50:.4f})")
            evidence.append(f"RSI_14 ({rsi_14:.2f}) <= {self.rsi_bear_max}")

        else:
            evidence.append("NO_CLEAR_TREND_ALIGNMENT")
            if vol_state == VolatilityState.EXPANSION:
                regime = TrendRegime.BREAKOUT_POTENTIAL

        return MarketRegime(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            regime=regime,
            volatility_state=vol_state,
            strength=round(strength, 2),
            confidence=confidence,
            evidence=evidence,
            data_quality=data_quality
        )
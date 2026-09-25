"""
TrendFeatures — SMA/EMA et distance du prix à ces moyennes (section 5).
Périodes configurables au constructeur — aucune valeur codée en dur dans
la logique de calcul elle-même.

Ne produit AUCUNE interprétation ("tendance haussière") — uniquement des
valeurs quantitatives, comme exigé section 5.
"""
from core.features.calculators.base import FeatureCalculator
from core.features.domain.ohlcv_series import OHLCVSeries


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema_series(values: list[float], period: int) -> list[float | None]:
    """
    Retourne l'EMA à CHAQUE point (pas seulement le dernier), calculée sans
    aucune donnée future : ema[i] ne dépend que de values[0..i]. Nécessaire
    pour le test anti-look-ahead et pour permettre le calcul incrémental.
    """
    if len(values) < period:
        return [None] * len(values)

    alpha = 2 / (period + 1)
    result: list[float | None] = [None] * (period - 1)
    seed = sum(values[:period]) / period
    result.append(seed)
    prev = seed
    for v in values[period:]:
        current = v * alpha + prev * (1 - alpha)
        result.append(current)
        prev = current
    return result


class TrendFeatures(FeatureCalculator):
    def __init__(self, sma_periods: list[int] | None = None, ema_periods: list[int] | None = None):
        self._sma_periods = sma_periods or [20]
        self._ema_periods = ema_periods or [20, 50, 200]

    @property
    def name(self) -> str:
        return "trend"

    def compute(self, series: OHLCVSeries) -> dict[str, float | None]:
        bar = series.last()
        if bar is None:
            return {}

        closes = series.closes()
        result: dict[str, float | None] = {}

        for period in self._sma_periods:
            value = sma(closes, period)
            result[f"sma_{period}"] = value
            result[f"distance_to_sma_{period}"] = (
                (bar.close - value) if value is not None else None
            )

        for period in self._ema_periods:
            ema_vals = ema_series(closes, period)
            value = ema_vals[-1]
            result[f"ema_{period}"] = value
            result[f"distance_to_ema_{period}"] = (
                (bar.close - value) if value is not None else None
            )
            # Variation de la moyenne (section 5) : pente sur la dernière période,
            # None si pas assez de points pour comparer.
            if len(ema_vals) >= 2 and ema_vals[-2] is not None and value is not None:
                result[f"ema_{period}_slope"] = value - ema_vals[-2]
            else:
                result[f"ema_{period}_slope"] = None

        return result

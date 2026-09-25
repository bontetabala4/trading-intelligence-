"""
VolatilityFeatures — True Range, ATR, volatilité glissante (section 6).
Aucune interprétation "BUY/SELL" — valeurs quantitatives uniquement.
"""
import statistics

from core.features.calculators.base import FeatureCalculator
from core.features.domain.ohlcv_series import OHLCVSeries


def true_range(curr_high: float, curr_low: float, prev_close: float | None) -> float:
    if prev_close is None:
        return curr_high - curr_low
    return max(
        curr_high - curr_low,
        abs(curr_high - prev_close),
        abs(curr_low - prev_close),
    )


class VolatilityFeatures(FeatureCalculator):
    def __init__(self, atr_period: int = 14, stddev_period: int = 20):
        self._atr_period = atr_period
        self._stddev_period = stddev_period

    @property
    def name(self) -> str:
        return "volatility"

    def compute(self, series: OHLCVSeries) -> dict[str, float | None]:
        bar = series.last()
        if bar is None:
            return {}

        bars = series.bars
        prev_close = bars[-2].close if len(bars) >= 2 else None
        tr = true_range(bar.high, bar.low, prev_close)

        atr = self._atr(bars)
        closes = series.closes()

        rolling_std = None
        if len(closes) >= self._stddev_period:
            rolling_std = statistics.pstdev(closes[-self._stddev_period :])

        relative_range = (tr / bar.close) if bar.close != 0 else None

        return {
            "true_range": tr,
            f"atr_{self._atr_period}": atr,
            f"rolling_stddev_{self._stddev_period}": rolling_std,
            "relative_range": relative_range,
        }

    def _atr(self, bars) -> float | None:
        """ATR = moyenne mobile simple du True Range sur `atr_period` bougies.
        Choix documenté (docs/features.md) : SMA plutôt que la moyenne mobile
        de Wilder — plus simple à vérifier, cohérent avec la section 23 (KISS)."""
        if len(bars) < self._atr_period + 1:
            return None
        trs = []
        for i in range(len(bars) - self._atr_period, len(bars)):
            prev_close = bars[i - 1].close if i > 0 else None
            trs.append(true_range(bars[i].high, bars[i].low, prev_close))
        return sum(trs) / len(trs)

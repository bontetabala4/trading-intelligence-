"""
VolumeFeatures — n'utilise que les volumes réellement disponibles
(section 8). Si real_volume est absent (NULL en base), les features qui
en dépendent restent explicitement None — jamais de valeur inventée.
"""
from core.features.calculators.base import FeatureCalculator
from core.features.domain.ohlcv_series import OHLCVSeries


class VolumeFeatures(FeatureCalculator):
    def __init__(self, rolling_period: int = 20):
        self._rolling_period = rolling_period

    @property
    def name(self) -> str:
        return "volume"

    def compute(self, series: OHLCVSeries) -> dict[str, float | None]:
        bar = series.last()
        if bar is None:
            return {}

        bars = series.bars
        tick_volumes = [b.tick_volume for b in bars]
        real_volumes = [b.real_volume for b in bars]

        rolling_avg_tick = self._rolling_avg(tick_volumes, self._rolling_period)
        rolling_avg_real = self._rolling_avg(real_volumes, self._rolling_period)

        relative_tick_volume = None
        if bar.tick_volume is not None and rolling_avg_tick not in (None, 0):
            relative_tick_volume = bar.tick_volume / rolling_avg_tick

        relative_real_volume = None
        if bar.real_volume is not None and rolling_avg_real not in (None, 0):
            relative_real_volume = bar.real_volume / rolling_avg_real

        return {
            "tick_volume": bar.tick_volume,  # None si le broker ne le fournit pas
            "real_volume": bar.real_volume,  # None si non disponible — jamais inventé
            f"rolling_avg_tick_volume_{self._rolling_period}": rolling_avg_tick,
            f"rolling_avg_real_volume_{self._rolling_period}": rolling_avg_real,
            "relative_tick_volume": relative_tick_volume,
            "relative_real_volume": relative_real_volume,
            # Indicateur explicite de disponibilité (section 8/9) plutôt que
            # de laisser l'appelant deviner pourquoi une valeur est None.
            "real_volume_available": bar.real_volume is not None,
        }

    @staticmethod
    def _rolling_avg(values: list[float | None], period: int) -> float | None:
        if len(values) < period:
            return None
        window = values[-period:]
        if any(v is None for v in window):
            return None
        return sum(window) / period

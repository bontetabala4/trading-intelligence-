"""
VWAPFeatures — Volume-Weighted Average Price, glissant sur `period` bougies
(section 9).

Décisions documentées (docs/features.md) :
- Type de volume : real_volume en priorité si présent sur TOUTES les
  bougies de la fenêtre, sinon repli sur tick_volume. Jamais un mélange
  des deux au sein d'une même fenêtre (biaiserait le calcul).
- Période : glissante sur `period` bougies (pas de VWAP de session/jour —
  explicitement reporté à une étape future, section 9).
- Méthode : prix typique (H+L+C)/3 pondéré par le volume choisi.
- Hypothèse : le volume est constant sur toute la bougie (approximation
  standard de VWAP intra-bougie, pas de données tick-by-tick ici).
- Limitation : si AUCUN volume n'est disponible sur la fenêtre, VWAP est
  explicitement indisponible plutôt que calculé avec un volume fictif de 1.
"""
from core.features.calculators.base import FeatureCalculator
from core.features.domain.ohlcv_series import OHLCVSeries


class VWAPFeatures(FeatureCalculator):
    def __init__(self, period: int = 20):
        self._period = period

    @property
    def name(self) -> str:
        return "vwap"

    def compute(self, series: OHLCVSeries) -> dict[str, float | None]:
        bar = series.last()
        if bar is None:
            return {}

        if not series.has_min_length(self._period):
            return {
                "vwap": None,
                "vwap_available": False,
                "vwap_volume_source": None,
                "distance_to_vwap": None,
            }

        window = series.bars[-self._period :]

        volume_source = self._select_volume_source(window)
        if volume_source is None:
            return {
                "vwap": None,
                "vwap_available": False,
                "vwap_volume_source": None,
                "distance_to_vwap": None,
            }

        total_pv = 0.0
        total_v = 0.0
        for b in window:
            typical_price = (b.high + b.low + b.close) / 3
            vol = b.real_volume if volume_source == "real_volume" else b.tick_volume
            total_pv += typical_price * vol
            total_v += vol

        if total_v == 0:
            return {
                "vwap": None,
                "vwap_available": False,
                "vwap_volume_source": None,
                "distance_to_vwap": None,
            }

        vwap_value = total_pv / total_v

        return {
            "vwap": vwap_value,
            "vwap_available": True,
            "vwap_volume_source": volume_source,
            "distance_to_vwap": bar.close - vwap_value,
        }

    @staticmethod
    def _select_volume_source(window) -> str | None:
        if all(b.real_volume is not None for b in window):
            return "real_volume"
        if all(b.tick_volume is not None for b in window):
            return "tick_volume"
        return None

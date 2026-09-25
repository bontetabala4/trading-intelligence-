"""
FeatureCalculator — contrat abstrait que tout calculateur de features doit
respecter. Chaque calculateur produit un dict[str, float | None] pour la
DERNIÈRE bougie de la série reçue — jamais None remplacé par 0 (section 16).
"""
from abc import ABC, abstractmethod

from core.features.domain.ohlcv_series import OHLCVSeries


class FeatureCalculator(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Nom court du groupe de features (ex: 'price', 'trend'). Utilisé par le Registry."""

    @abstractmethod
    def compute(self, series: OHLCVSeries) -> dict[str, float | None]:
        """
        Calcule les features pour la DERNIÈRE bougie de `series`.
        `series` ne doit contenir que des bougies jusqu'à l'instant T inclus
        — jamais de bougies futures (garanti par l'appelant, FeatureEngine).
        Une feature non calculable (historique insuffisant, division par
        zéro évitée, etc.) vaut explicitement None — jamais 0 par défaut.
        """

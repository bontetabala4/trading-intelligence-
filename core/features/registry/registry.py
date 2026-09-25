"""
FeatureRegistry — permet d'ajouter un futur calculateur (FVG, order-flow,
session, macro, ML features — section 12) sans modifier FeatureEngine :
il suffit d'enregistrer une nouvelle instance de FeatureCalculator.
"""
from core.features.calculators.base import FeatureCalculator
from core.features.calculators.momentum import MomentumFeatures
from core.features.calculators.price import PriceFeatures
from core.features.calculators.trend import TrendFeatures
from core.features.calculators.volatility import VolatilityFeatures
from core.features.calculators.volume import VolumeFeatures
from core.features.calculators.vwap import VWAPFeatures


class FeatureRegistry:
    def __init__(self) -> None:
        self._calculators: dict[str, FeatureCalculator] = {}

    def register(self, calculator: FeatureCalculator) -> None:
        self._calculators[calculator.name] = calculator

    def unregister(self, name: str) -> None:
        self._calculators.pop(name, None)

    def get(self, name: str) -> FeatureCalculator | None:
        return self._calculators.get(name)

    def all(self) -> list[FeatureCalculator]:
        return list(self._calculators.values())

    def names(self) -> list[str]:
        return list(self._calculators.keys())


def default_registry() -> FeatureRegistry:
    """
    Registre par défaut de l'Étape 3 : price, trend, volatility, momentum,
    volume, vwap (section 12). Les futurs calculateurs (FVG, IFVG, PDH/PDL,
    liquidity sweep, market structure, session, macro, order-flow, ML)
    s'ajoutent ici sans toucher au FeatureEngine.
    """
    registry = FeatureRegistry()
    registry.register(PriceFeatures())
    registry.register(TrendFeatures())
    registry.register(VolatilityFeatures())
    registry.register(MomentumFeatures())
    registry.register(VolumeFeatures())
    registry.register(VWAPFeatures())
    return registry

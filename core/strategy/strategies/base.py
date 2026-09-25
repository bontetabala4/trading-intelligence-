from abc import ABC, abstractmethod
from typing import Dict, Any, List
from core.strategy.domain.models import StrategySignal
from core.strategy.domain.enums import StrategyID
from core.regime.domain.models import MarketRegime

class BaseStrategy(ABC):
    def __init__(self, strategy_id: StrategyID, compatible_regimes: List[str]):
        self.strategy_id = strategy_id
        self.compatible_regimes = compatible_regimes

    def is_compatible(self, regime: MarketRegime) -> bool:
        return regime.regime.value in self.compatible_regimes

    @abstractmethod
    def evaluate(self, regime: MarketRegime, features: Dict[str, Any]) -> StrategySignal:
        pass

from typing import List, Optional

from core.strategy.strategies.base import BaseStrategy
from core.strategy.registry.registry import (
    StrategyRegistry,
    default_strategy_registry,
)
from core.strategy.domain.models import StrategySignal
from core.regime.domain.models import MarketRegime


class StrategyEngine:

    def __init__(
        self,
        strategies: Optional[List[BaseStrategy]] = None,
        registry: Optional[StrategyRegistry] = None,
    ):
        self.registry = registry or default_strategy_registry()
        if strategies is not None:
            self.strategies = strategies
        else:
            self.strategies = self.registry.get_active_strategies()


    def evaluate_all(
        self,
        regime: MarketRegime,
        features: dict,
    ) -> List[StrategySignal]:

        signals: List[StrategySignal] = []

        for strategy in self.strategies:

            if not strategy.is_compatible(regime):
                continue

            signal = strategy.evaluate(
                regime,
                features,
            )

            signals.append(signal)

        return signals
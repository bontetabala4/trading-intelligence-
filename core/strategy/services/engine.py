
from typing import List, Optional

from core.strategy.strategies.base import BaseStrategy
from core.strategy.strategies.trend_following import (
    TrendFollowingStrategy,
)
from core.strategy.strategies.mean_reversion import (
    MeanReversionStrategy,
)
from core.strategy.domain.models import StrategySignal
from core.regime.domain.models import MarketRegime


class StrategyEngine:

    def __init__(
        self,
        strategies: Optional[List[BaseStrategy]] = None,
    ):
        self.strategies = strategies or [
            TrendFollowingStrategy(),
            MeanReversionStrategy(),
        ]

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
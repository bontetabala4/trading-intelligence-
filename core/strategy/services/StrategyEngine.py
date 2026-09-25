from typing import List, Dict, Any, Optional
from core.strategy.strategies.base import BaseStrategy
from core.strategy.strategies.trend_following import TrendFollowingStrategy
from core.strategy.strategies.mean_reversion import MeanReversionStrategy
from core.strategy.domain.models import StrategySignal
from core.regime.domain.models import MarketRegime

class StrategyEngine:
    def __init__(self, strategies: Optional[List[BaseStrategy]] = None):
        self.strategies = strategies or [
            TrendFollowingStrategy(),
            MeanReversionStrategy()
        ]

    def evaluate_all(self, regime: MarketRegime, features: Dict[str, Any]) -> List[StrategySignal]:
        signals: List[StrategySignal] = []

        # N'évalue que les stratégies compatibles avec le régime de marché actuel
        for strategy in self.strategies:
            if strategy.is_compatible(regime):
                signal = strategy.evaluate(regime, features)
                signals.append(signal)

        return signals
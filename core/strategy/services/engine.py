"""
Strategy Engine Service (compatibilité et export principal).
"""
from core.strategy.services.StrategyEngine import StrategyEngine

# Alias pour compatibilité ascendante si référencé sous le nom SignalEngine
SignalEngine = StrategyEngine

__all__ = ["StrategyEngine", "SignalEngine"]

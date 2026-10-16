"""
Unit tests for StrategyRegistry.
Verifies registration, status filtering, metadata listing, and compatibility filtering.
"""
import pytest
from core.strategy.registry.registry import (
    StrategyRegistry,
    default_strategy_registry,
)
from core.strategy.domain.enums import StrategyID, StrategyStatus
from core.strategy.domain.models import StrategyMetadata
from core.strategy.strategies.trend_following import TrendFollowingStrategy


def test_default_registry_exposes_experimental_and_unsupported_entries_safely():
    registry = default_strategy_registry()
    metadata_list = registry.list_all_metadata()
    strategy_ids = [m.strategy_id for m in metadata_list]

    assert StrategyID.TREND_FOLLOWING in strategy_ids
    assert StrategyID.MEAN_REVERSION in strategy_ids
    assert StrategyID.EMA200_MACRO_TREND in strategy_ids
    assert StrategyID.BREAKOUT_PRICE_ACTION in strategy_ids
    assert StrategyID.FIBONACCI_PULLBACK in strategy_ids
    assert StrategyID.MULTI_TIMEFRAME in strategy_ids
    assert StrategyID.PAIRS_TRADING in strategy_ids
    assert StrategyID.MARKET_MAKING in strategy_ids
    assert len(registry.get_active_strategies()) == 2
    assert registry.get_metadata("EMA200_MACRO_TREND").status == StrategyStatus.EXPERIMENTAL
    assert registry.get_metadata("PAIRS_TRADING").status == StrategyStatus.UNSUPPORTED_DATA
    assert registry.get_strategy("PAIRS_TRADING") is None


def test_strategy_status_filtering():
    registry = StrategyRegistry()
    strategy = TrendFollowingStrategy()

    metadata = StrategyMetadata(
        strategy_id=StrategyID.TREND_FOLLOWING,
        name="Trend Following",
        version="1.0.0",
        description="Test disabled",
        status=StrategyStatus.DISABLED,
        compatible_regimes=strategy.compatible_regimes,
    )
    registry.register(strategy, metadata)

    assert registry.get_strategy("TREND_FOLLOWING") is not None
    assert len(registry.get_active_strategies()) == 0


def test_asset_class_and_timeframe_filtering():
    registry = StrategyRegistry()
    strategy = TrendFollowingStrategy()

    metadata = StrategyMetadata(
        strategy_id=StrategyID.TREND_FOLLOWING,
        name="Trend Following",
        version="1.0.0",
        description="Forex only",
        status=StrategyStatus.ENABLED,
        supported_asset_classes=["FOREX"],
        supported_timeframes=["H1", "D1"],
    )
    registry.register(strategy, metadata)

    # Compatible
    assert len(registry.get_active_strategies(asset_class="FOREX", timeframe="H1")) == 1
    # Incompatible asset class
    assert len(registry.get_active_strategies(asset_class="CRYPTO", timeframe="H1")) == 0
    # Incompatible timeframe
    assert len(registry.get_active_strategies(asset_class="FOREX", timeframe="M1")) == 0

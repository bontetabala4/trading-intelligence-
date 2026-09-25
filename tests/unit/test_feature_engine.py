from datetime import datetime, timedelta, timezone

import pytest

from brokers.base.interface import OHLCVBar, Timeframe
from core.features.registry.registry import FeatureRegistry, default_registry
from core.features.services.context_builder import MarketContextBuilder
from core.features.services.feature_engine import FeatureEngine, InsufficientDataError
from core.market.selection import AssetClass


def _bars(n: int, symbol_price=100.0) -> list[OHLCVBar]:
    now = datetime.now(timezone.utc)
    bars = []
    price = symbol_price
    for i in range(n):
        ts = now - timedelta(minutes=15 * (n - i))
        bars.append(
            OHLCVBar(
                timestamp=ts, open=price, high=price + 1, low=price - 1, close=price + 0.5,
                volume=100, tick_volume=100, real_volume=50,
            )
        )
        price += 0.5
    return bars


def test_feature_engine_computes_full_set():
    engine = FeatureEngine()
    result = engine.compute_feature_set("XAUUSD", Timeframe.M15, _bars(30))

    assert result.symbol == "XAUUSD"
    assert result.timeframe == Timeframe.M15
    assert "body" in result.values  # price
    assert "sma_20" in result.values  # trend
    assert "atr_14" in result.values  # volatility
    assert "rsi_14" in result.values  # momentum
    assert "tick_volume" in result.values  # volume
    assert "vwap" in result.values  # vwap


def test_feature_engine_raises_on_empty_bars():
    engine = FeatureEngine()
    with pytest.raises(InsufficientDataError):
        engine.compute_feature_set("XAUUSD", Timeframe.M15, [])


def test_feature_engine_multi_symbol_independent_results():
    """Section 13 : le moteur ne doit pas coder XAUUSD en dur."""
    engine = FeatureEngine()
    xau_result = engine.compute_feature_set("XAUUSD", Timeframe.M15, _bars(30, symbol_price=2650))
    eur_result = engine.compute_feature_set("EURUSD", Timeframe.M15, _bars(30, symbol_price=1.085))

    assert xau_result.symbol == "XAUUSD"
    assert eur_result.symbol == "EURUSD"
    assert xau_result.values["sma_20"] != eur_result.values["sma_20"]


def test_feature_engine_multi_timeframe_no_confusion():
    """Section 14 : une feature M15 ne doit pas être confondue avec H1."""
    engine = FeatureEngine()
    m15_result = engine.compute_feature_set("XAUUSD", Timeframe.M15, _bars(30))
    h1_result = engine.compute_feature_set("XAUUSD", Timeframe.H1, _bars(30))

    assert m15_result.timeframe == Timeframe.M15
    assert h1_result.timeframe == Timeframe.H1


def test_registry_default_contains_all_expected_groups():
    registry = default_registry()
    names = set(registry.names())
    assert names == {"price", "trend", "volatility", "momentum", "volume", "vwap"}


def test_registry_can_register_and_unregister_without_touching_engine():
    """Section 12 : ajouter/retirer une feature sans modifier FeatureEngine."""
    registry = FeatureRegistry()
    from core.features.calculators.price import PriceFeatures

    registry.register(PriceFeatures())
    assert "price" in registry.names()

    registry.unregister("price")
    assert "price" not in registry.names()


def test_market_context_builder_reflects_bad_quality():
    """Section 17 : données invalides -> data_quality le reflète, pas de résultat présenté comme fiable."""
    builder = MarketContextBuilder()
    now = datetime.now(timezone.utc)
    invalid_bar = OHLCVBar(
        timestamp=now, open=100, high=90, low=95, close=100, volume=10,  # high < low : invalide
    )

    context = builder.build("XAUUSD", AssetClass.METALS, Timeframe.M15, [invalid_bar])

    assert context.data_quality.status.value == "INVALID"


def test_market_context_has_no_buy_sell_fields():
    """Vérification architecturale : MarketContext ne doit exposer aucune décision de trading."""
    builder = MarketContextBuilder()
    context = builder.build("XAUUSD", AssetClass.METALS, Timeframe.M15, _bars(30))

    field_names = set(context.__dataclass_fields__.keys())
    forbidden = {"signal", "action", "buy", "sell", "decision", "recommendation", "strategy"}
    assert field_names.isdisjoint(forbidden)

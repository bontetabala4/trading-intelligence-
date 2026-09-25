import pytest

from brokers.base.interface import Timeframe
from brokers.mt5.mock_adapter import MockMT5Adapter
from core.data.quality_engine import DataQualityEngine
from core.market.observer import MarketObserver, MarketObserverError
from core.market.selection import AssetClass


def test_build_snapshot_returns_valid_snapshot(market_observer):
    snapshot = market_observer.build_snapshot("XAUUSD", AssetClass.METALS, Timeframe.M15)
    assert snapshot.symbol == "XAUUSD"
    assert snapshot.asset_class == AssetClass.METALS
    assert snapshot.close > 0
    assert snapshot.data_quality is not None


def test_build_snapshot_unknown_symbol_raises(market_observer):
    with pytest.raises(MarketObserverError):
        market_observer.build_snapshot("NOT_REAL", AssetClass.FOREX, Timeframe.M15)


def test_build_snapshot_fails_when_broker_disconnected():
    broker = MockMT5Adapter()  # non connecté volontairement
    observer = MarketObserver(broker=broker, quality_engine=DataQualityEngine())
    with pytest.raises(MarketObserverError, match="non connecté"):
        observer.build_snapshot("EURUSD", AssetClass.FOREX, Timeframe.M15)


def test_snapshot_never_contains_trading_signal(market_observer):
    """
    Vérification architecturale : MarketSnapshot ne doit exposer aucun champ
    de décision (pas de 'signal', 'action', 'buy', 'sell').
    """
    snapshot = market_observer.build_snapshot("EURUSD", AssetClass.FOREX, Timeframe.M15)
    field_names = {f for f in snapshot.__dataclass_fields__}
    forbidden = {"signal", "action", "buy", "sell", "recommendation"}
    assert field_names.isdisjoint(forbidden)

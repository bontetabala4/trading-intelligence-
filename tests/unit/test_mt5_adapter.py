import pytest
import numpy as np

from brokers.base.interface import ExecutionDisabledError, OrderRequest, Timeframe
from brokers.mt5.mock_adapter import MockMT5Adapter

from brokers.mt5 import adapter as mt5_adapter
from brokers.mt5.adapter import MT5Adapter


def test_connect_sets_connected_state():
    broker = MockMT5Adapter()
    assert broker.is_connected() is False
    broker.connect()
    assert broker.is_connected() is True


def test_disconnect_clears_connected_state():
    broker = MockMT5Adapter()
    broker.connect()
    broker.disconnect()
    assert broker.is_connected() is False


def test_existing_symbol_reports_exists_true(mock_broker):
    info = mock_broker.get_symbol_info("EURUSD")
    assert info.exists is True
    assert info.tradable is True


def test_nonexistent_symbol_reports_exists_false(mock_broker):
    info = mock_broker.get_symbol_info("NOT_A_REAL_SYMBOL")
    assert info.exists is False
    assert info.tradable is False


def test_get_ohlcv_returns_requested_count(mock_broker):
    bars = mock_broker.get_ohlcv("XAUUSD", Timeframe.M15, count=100)
    assert len(bars) == 100
    # Chronologiquement croissant
    timestamps = [b.timestamp for b in bars]
    assert timestamps == sorted(timestamps)


def test_get_ohlcv_unknown_symbol_returns_empty(mock_broker):
    bars = mock_broker.get_ohlcv("UNKNOWN", Timeframe.M15, count=10)
    assert bars == []


def test_execute_order_is_always_disabled(mock_broker):
    """
    Garde-fou critique : même un adaptateur mock ne doit JAMAIS pouvoir
    exécuter un ordre à l'Étape 1. Le stub vient de la classe de base et
    n'est surchargé par aucun adaptateur concret.
    """
    order = OrderRequest(symbol="EURUSD", volume=0.1, side="buy")
    with pytest.raises(ExecutionDisabledError):
        mock_broker.execute_order(order)
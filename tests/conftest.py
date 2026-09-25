import sys
from pathlib import Path

import pytest

# Permet d'importer les modules du projet sans installation en mode package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brokers.mt5.mock_adapter import MockMT5Adapter  # noqa: E402
from core.data.quality_engine import DataQualityEngine  # noqa: E402
from core.market.observer import MarketObserver  # noqa: E402


@pytest.fixture
def mock_broker() -> MockMT5Adapter:
    broker = MockMT5Adapter(seed=123)
    broker.connect()
    return broker


@pytest.fixture
def quality_engine() -> DataQualityEngine:
    return DataQualityEngine()


@pytest.fixture
def market_observer(mock_broker, quality_engine) -> MarketObserver:
    return MarketObserver(broker=mock_broker, quality_engine=quality_engine)

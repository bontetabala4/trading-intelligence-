import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from configs.settings import AppEnv, BrokerBackend, Settings
from core.decision.service import persist_decision, run_decision
from database.models import Base, DecisionRecord
from brokers.base.interface import Timeframe
from core.market.selection import AssetClass


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_persist_decision_writes_record(db_session, mock_broker):
    mock_broker.connect()
    result = run_decision(
        symbol="XAUUSD",
        asset_class=AssetClass.METALS,
        timeframe=Timeframe.M15,
        broker=mock_broker,
        lookback=200,
    )
    settings = Settings(
        broker_backend=BrokerBackend.MOCK,
        app_env=AppEnv.TESTING,
    )
    record = persist_decision(db_session, result, settings)

    assert isinstance(record, DecisionRecord)
    assert record.signal_id == result.signal.signal_id
    assert record.symbol == "XAUUSD"
    assert json.loads(record.features_json)

    again = persist_decision(db_session, result, settings)
    assert again.id == record.id

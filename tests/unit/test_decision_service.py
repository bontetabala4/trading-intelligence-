from brokers.base.interface import Timeframe
from core.decision.service import pipeline_result_to_dict, run_decision
from core.market.selection import AssetClass
from core.signal.domain import FinalSignalDirection


def test_run_decision_returns_pipeline_result(mock_broker):
    mock_broker.connect()
    result = run_decision(
        symbol="XAUUSD",
        asset_class=AssetClass.METALS,
        timeframe=Timeframe.M15,
        broker=mock_broker,
        lookback=200,
    )
    assert result.signal.symbol == "XAUUSD"
    assert result.signal.direction in (
        FinalSignalDirection.BUY,
        FinalSignalDirection.SELL,
        FinalSignalDirection.NO_TRADE,
    )


def test_pipeline_result_to_dict_serializes(mock_broker):
    mock_broker.connect()
    result = run_decision(
        symbol="EURUSD",
        asset_class=AssetClass.FOREX,
        timeframe=Timeframe.M15,
        broker=mock_broker,
        lookback=200,
    )
    data = pipeline_result_to_dict(result)
    assert "decision" in data
    assert data["decision"]["direction"] in ("BUY", "SELL", "NO_TRADE")

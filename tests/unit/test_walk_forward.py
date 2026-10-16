from datetime import timezone

import pandas as pd
import pytest

from core.backtest.domain import BacktestConfig
from core.backtest.walk_forward import WalkForwardConfig, WalkForwardEngine
from core.signal.signal_engine import SignalEngine


def make_dataset(periods: int = 120) -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=periods, freq="15min", tz="UTC")
    close = [1.10 + (index * 0.0001) for index in range(periods)]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": close,
            "high": [price + 0.0002 for price in close],
            "low": [price - 0.0002 for price in close],
            "close": close,
            "volume": 1000.0,
        }
    )


def test_walk_forward_windows_are_chronologically_separated_and_reproducible():
    dataset = make_dataset()
    engine = WalkForwardEngine(SignalEngine())
    config = BacktestConfig(symbol="EURUSD", timeframe="M15", warmup_bars=20)
    wf_config = WalkForwardConfig(train_bars=60, test_bars=30, step_bars=30, min_windows=2)

    report_a = engine.run(dataset, config, wf_config)
    report_b = engine.run(dataset, config, wf_config)

    assert report_a.dataset_hash == report_b.dataset_hash
    assert report_a.total_windows == 2
    assert report_a.generated_at.tzinfo == timezone.utc
    for window in report_a.windows:
        assert window.train_end < window.test_start
        assert all(signal.timestamp >= window.test_start for signal in window.oos_result.signals)
        assert all(trade.entry_timestamp >= window.test_start for trade in window.oos_result.trades)


def test_walk_forward_rejects_non_progressing_or_ambiguous_input():
    dataset = make_dataset(90)
    engine = WalkForwardEngine(SignalEngine())
    config = BacktestConfig(symbol="EURUSD", timeframe="M15", warmup_bars=20)

    with pytest.raises(ValueError, match="step_bars must be positive"):
        engine.run(dataset, config, WalkForwardConfig(train_bars=60, test_bars=30, step_bars=0))

    duplicated = pd.concat([dataset, dataset.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate timestamps"):
        engine.run(duplicated, config, WalkForwardConfig(train_bars=60, test_bars=30))

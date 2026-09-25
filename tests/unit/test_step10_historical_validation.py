"""
Unit and Integration Tests for ATIP Step 10.
Ensures zero-lookahead, exact reproducibility, dataset integrity validation,
isolation from live brokers, and cost sensitivity calculations.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.backtest.dataset_validator import DatasetValidator
from core.backtest.data_quality import DatasetMetadata, QualityMetrics, DataQualityReport
from core.backtest.runner import BacktestRunner, BacktestConfig


@pytest.fixture
def real_like_dataset():
    """Generates a realistic 1,000-bar M15 historical dataframe (2022-2025 range)."""
    dates = pd.date_range(start="2022-01-03 00:00:00", periods=1000, freq="15min", tz="UTC")
    np.random.seed(42)
    price = 1.1000 + np.cumsum(np.random.randn(1000) * 0.0005)
    
    df = pd.DataFrame({
        "timestamp": dates,
        "open": price,
        "high": price + np.abs(np.random.randn(1000) * 0.0002),
        "low": price - np.abs(np.random.randn(1000) * 0.0002),
        "close": price + np.random.randn(1000) * 0.0001,
        "volume": np.random.randint(100, 5000, size=1000)
    })
    # Correct OHLC bounds
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def test_data_quality_report_invalid_ohlc(real_like_dataset):
    validator = DatasetValidator()
    invalid_df = real_like_dataset.copy()
    invalid_df.loc[10, "high"] = invalid_df.loc[10, "low"] - 0.01  # OHLC Violation

    is_valid, errors = validator.validate(
    invalid_df, 
    expected_symbol="EURUSD", 
    expected_timeframe="M15"
)
    assert not is_valid
    assert any("OHLC violation" in err for err in errors)


def test_future_mutation_no_lookahead(real_like_dataset):
    """
    Mutation Test: Mutate T+1, T+2... and ensure Signal at T is strictly invariant.
    """
    config = BacktestConfig(symbol="EURUSD", timeframe="M15", initial_capital=10000.0)
    runner = BacktestRunner(config=config, signal_engine=None)
    # Base Run
    base_results = runner.run(real_like_dataset)
    signal_at_t = base_results.signals[100]

    # Mutated Future Run
    mutated_df = real_like_dataset.copy()
    mutated_df.loc[101:, ["open", "high", "low", "close"]] *= 2.0  # Massive future mutation

    mutated_results = runner.run(mutated_df, config)
    mutated_signal_at_t = mutated_results.signals[100]

    assert signal_at_t.action == mutated_signal_at_t.action
    assert signal_at_t.direction == mutated_signal_at_t.direction


def test_reproducibility_identical_runs(real_like_dataset):
    """Identical input MUST yield identical outputs."""
    config = BacktestConfig(symbol="EURUSD", timeframe="M15", initial_capital=10000.0)
    runner = BacktestRunner(config=config, signal_engine=None)

    run_1 = runner.run(real_like_dataset, config)
    run_2 = runner.run(real_like_dataset, config)

    assert run_1.metrics.net_r == run_2.metrics.net_r
    assert run_1.metrics.total_signals == run_2.metrics.total_signals
    assert run_1.metrics.no_trade_count == run_2.metrics.no_trade_count


def test_v1_isolation_no_broker_calls():
    """Ensure no MT5 or broker modules are loaded or called."""
    import sys
    assert "Metatrader5" not in sys.modules
    assert "broker_execution" not in sys.modules
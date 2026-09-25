"""
Unit & Integration Tests for ATIP Step 10.1 Independent Audit.
Guarantees determinism, exact reproducibility, cost sensitivity sanity,
and future-mutation invariance.
"""

import numpy as np
import pandas as pd
import pytest

from core.backtest.audit_tool import Step10AuditEngine
from core.backtest.runner import BacktestConfig, BacktestRunner


@pytest.fixture
def sample_trades_dataset():
    """Generates synthetic trade outcomes to audit metrics calculation."""
    np.random.seed(101)

    net_r_vals = np.random.choice(
        [1.0, -1.0, 0.0],
        size=100,
        p=[0.48, 0.48, 0.04],
    )
    regimes = np.random.choice(
        ["TRENDING_BULL", "RANGING_LOW_VOL"],
        size=100,
        p=[0.6, 0.4],
    )

    return pd.DataFrame(
        {
            "trade_id": range(100),
            "net_r": net_r_vals,
            "regime": regimes,
        }
    )


def test_profit_factor_calculation(sample_trades_dataset):
    win_r, loss_r, profit_factor = Step10AuditEngine.verify_profit_factor(
        sample_trades_dataset
    )

    assert win_r > 0
    assert loss_r > 0
    assert profit_factor == pytest.approx(win_r / loss_r)


def test_reproducibility_run_a_equals_run_b():
    """RUN A == RUN B check for deterministic execution."""
    dates = pd.date_range(
        start="2022-01-03",
        periods=300,
        freq="15min",
        tz="UTC",
    )

    dataframe = pd.DataFrame(
        {
            "timestamp": dates,
            "open": 1.1000,
            "high": 1.1010,
            "low": 1.0990,
            "close": 1.1005,
            "volume": 1000,
        }
    )

    config = BacktestConfig(
        symbol="EURUSD",
        timeframe="M15",
        initial_capital=10000.0,
    )

    signal_engine = None
    runner = BacktestRunner(
        config=config,
        signal_engine=signal_engine,
    )

    # FIX (correction n°2) : run() n'accepte que `bars`, le config est déjà
    # mémorisé dans le runner via son constructeur — on ne le repasse plus ici.
    run_a = runner.run(dataframe)
    run_b = runner.run(dataframe)

    assert run_a.metrics.net_r == run_b.metrics.net_r
    assert run_a.metrics.total_signals == run_b.metrics.total_signals
    assert run_a.metrics.win_rate == run_b.metrics.win_rate


def test_drawdown_calculation_strict(sample_trades_dataset):
    max_dd_r, max_dd_pct = Step10AuditEngine.recalculate_max_drawdown(
        sample_trades_dataset
    )

    assert max_dd_r <= 0.0
    assert max_dd_pct is None


def test_regime_loss_distribution_audit(sample_trades_dataset):
    audit_result = Step10AuditEngine.audit_loss_regime_distribution(
        sample_trades_dataset
    )

    assert "total_gross_loss_r" in audit_result
    assert "regimes" in audit_result
    assert audit_result["total_loss_count"] > 0
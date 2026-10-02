from datetime import datetime, timezone

from core.backtest.domain import VirtualTrade
from core.backtest.runner import BacktestRunner
from core.backtest.domain import BacktestConfig

from core.strategy.domain.models import StrategySignal
from core.strategy.domain.enums import SignalType, StrategyID
from core.regime.domain.enums import TrendRegime


def _make_runner():
    config = BacktestConfig(
        symbol="EURUSD",
        timeframe="M15",
        initial_capital=10_000.0,
        risk_per_trade_pct=1.0,
    )

    return BacktestRunner(config)


def _make_closed_trade(
    net_result_r: float,
    risk_amount: float = 100.0,
) -> VirtualTrade:
    return VirtualTrade(
        trade_id="trade-test",
        signal_id="signal-test",
        symbol="EURUSD",
        timeframe="M15",
        direction="BUY",
        entry_timestamp=datetime(
            2025,
            1,
            2,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        entry_price=1.1000,
        stop_reference=1.0990,
        target_reference=1.1020,
        risk_r_amount=0.0010,
        strategy="TREND_FOLLOWING",
        market_regime="TRENDING_BULL",
        volume_lots=1.0,
        risk_amount_account_currency=risk_amount,
        exit_timestamp=datetime(
            2025,
            1,
            2,
            11,
            0,
            tzinfo=timezone.utc,
        ),
        exit_price=1.1020,
        gross_result_r=net_result_r,
        net_result_r=net_result_r,
        holding_bars=4,
        is_open=False,
    )


def test_dynamic_capital_updates_after_winning_trade():
    runner = _make_runner()

    trade = _make_closed_trade(
        net_result_r=2.0,
        risk_amount=100.0,
    )

    runner._update_account_after_closed_trades(
        [trade],
        active_trades_count=0,
    )

    assert runner.account.balance == 10_200.0
    assert runner.account.equity == 10_200.0
    assert runner.account.free_margin == 10_200.0
    assert runner.account.daily_pnl == 200.0
    assert runner.account.open_positions_count == 0


def test_dynamic_capital_updates_after_losing_trade():
    runner = _make_runner()

    trade = _make_closed_trade(
        net_result_r=-1.0,
        risk_amount=100.0,
    )

    runner._update_account_after_closed_trades(
        [trade],
        active_trades_count=0,
    )

    assert runner.account.balance == 9_900.0
    assert runner.account.equity == 9_900.0
    assert runner.account.free_margin == 9_900.0
    assert runner.account.daily_pnl == -100.0


def test_multiple_closed_trades_are_applied_to_capital():
    runner = _make_runner()

    trade_1 = _make_closed_trade(
        net_result_r=2.0,
        risk_amount=100.0,
    )

    trade_2 = _make_closed_trade(
        net_result_r=-1.0,
        risk_amount=100.0,
    )

    runner._update_account_after_closed_trades(
        [trade_1, trade_2],
        active_trades_count=1,
    )

    assert runner.account.balance == 10_100.0
    assert runner.account.equity == 10_100.0
    assert runner.account.free_margin == 10_100.0
    assert runner.account.daily_pnl == 100.0
    assert runner.account.open_positions_count == 1


def test_daily_pnl_resets_when_simulated_day_changes():
    runner = _make_runner()

    trade = _make_closed_trade(
        net_result_r=-2.0,
        risk_amount=100.0,
    )

    runner._update_account_after_closed_trades(
        [trade],
        active_trades_count=0,
    )

    assert runner.account.balance == 9_800.0
    assert runner.account.daily_pnl == -200.0

    runner._reset_daily_pnl_if_new_day(
        datetime(
            2025,
            1,
            3,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        datetime(
            2025,
            1,
            2,
            23,
            45,
            tzinfo=timezone.utc,
        ),
    )

    assert runner.account.balance == 9_800.0
    assert runner.account.daily_pnl == 0.0
    assert runner.account.equity == 9_800.0
    assert runner.account.free_margin == 9_800.0


def test_daily_pnl_does_not_reset_inside_same_day():
    runner = _make_runner()

    trade = _make_closed_trade(
        net_result_r=-1.0,
        risk_amount=100.0,
    )

    runner._update_account_after_closed_trades(
        [trade],
        active_trades_count=0,
    )

    runner._reset_daily_pnl_if_new_day(
        datetime(
            2025,
            1,
            2,
            15,
            0,
            tzinfo=timezone.utc,
        ),
        datetime(
            2025,
            1,
            2,
            14,
            45,
            tzinfo=timezone.utc,
        ),
    )

    assert runner.account.balance == 9_900.0
    assert runner.account.daily_pnl == -100.0


def test_account_resets_between_backtest_runs():
    runner = _make_runner()

    trade = _make_closed_trade(
        net_result_r=2.0,
        risk_amount=100.0,
    )

    runner._update_account_after_closed_trades(
        [trade],
        active_trades_count=0,
    )

    assert runner.account.balance == 10_200.0

    runner._reset_account()

    assert runner.account.balance == 10_000.0
    assert runner.account.equity == 10_000.0
    assert runner.account.free_margin == 10_000.0
    assert runner.account.daily_pnl == 0.0
    assert runner.account.open_positions_count == 0

def test_updated_capital_is_consumed_by_risk_engine():
    runner = _make_runner()

    first_trade = _make_closed_trade(
        net_result_r=2.0,
        risk_amount=100.0,
    )

    runner._update_account_after_closed_trades(
        [first_trade],
        active_trades_count=0,
    )

    assert runner.account.balance == 10_200.0

    # Le pipeline doit maintenant utiliser le nouveau compte.
    assert runner.pipeline.account.balance == 10_200.0

    # Le RiskEngine doit donc calculer 1% sur 10 200 $.
    risk_amount = (
        runner.pipeline.risk_engine.sizer.risk_per_trade_pct
        * runner.pipeline.account.balance
    )

    assert risk_amount == 102.0

def test_order_proposal_uses_updated_dynamic_capital():
    runner = _make_runner()

    first_trade = _make_closed_trade(
        net_result_r=2.0,
        risk_amount=100.0,
    )

    runner._update_account_after_closed_trades(
        [first_trade],
        active_trades_count=0,
    )

    assert runner.pipeline.account.balance == 10_200.0

    # Vérification directe du RiskEngine avec le compte actualisé.
    

    signal = StrategySignal(
    symbol="EURUSD",
    timeframe="M15",
    timestamp=datetime(
        2025,
        1,
        2,
        12,
        0,
        tzinfo=timezone.utc,
    ),
    strategy_id=StrategyID.TREND_FOLLOWING,
    signal=SignalType.BUY,
    strength=1.0,
    regime_context=TrendRegime.TRENDING_BULL,
    suggested_sl_distance=0.0015,
    suggested_tp_distance=0.0030,
)

    proposal = runner.pipeline.risk_engine.evaluate_signal(
        signal=signal,
        account=runner.pipeline.account,
        current_price=1.1000,
        current_spread_pips=1.0,
        evaluation_timestamp=signal.timestamp,
    )

    assert proposal.risk_amount_account_currency == 102.0
    assert proposal.risk_percentage == 1.0   
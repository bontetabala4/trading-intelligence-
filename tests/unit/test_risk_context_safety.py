from datetime import datetime, timezone

from brokers.base.interface import SymbolInfo
from brokers.mt5.mock_adapter import MockMT5Adapter
from core.pipeline import ATIPPipeline
from core.risk.domain.enums import RiskRejectReason, RiskStatus
from core.risk.domain.models import AccountState
from core.risk.services.engine import RiskEngine
from core.regime.domain.enums import TrendRegime
from core.strategy.domain.enums import SignalType, StrategyID
from core.strategy.domain.models import StrategySignal


def _signal():
    return StrategySignal(
        symbol="EURUSD",
        timeframe="M15",
        timestamp=datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc),
        strategy_id=StrategyID.TREND_FOLLOWING,
        signal=SignalType.BUY,
        strength=0.8,
        regime_context=TrendRegime.TRENDING_BULL,
        suggested_sl_distance=0.0015,
        suggested_tp_distance=0.0030,
    )


def test_pipeline_does_not_invent_a_default_account():
    assert ATIPPipeline().account is None


def test_strict_risk_engine_rejects_incomplete_symbol_specs():
    account = AccountState(
        balance=10_000, equity=10_000, free_margin=10_000,
        daily_pnl=0, open_positions_count=0,
    )
    incomplete = SymbolInfo(symbol="EURUSD", exists=True, tradable=True)
    result = RiskEngine().evaluate_signal(
        signal=_signal(),
        account=account,
        current_price=1.0850,
        current_spread_pips=1.0,
        current_spread_price=0.0001,
        symbol_info=incomplete,
        require_symbol_info=True,
    )
    assert result.status == RiskStatus.REJECTED
    assert result.reject_reason == RiskRejectReason.MISSING_RISK_INPUTS
    assert "REJECTED_MISSING_RISK_INPUTS" in result.audit_trail


def test_spread_is_checked_against_stop_distance_for_non_fx():
    from core.risk.services.limits import RiskLimitsChecker

    account = AccountState(
        balance=10_000, equity=10_000, free_margin=10_000,
        daily_pnl=0, open_positions_count=0,
    )
    reason = RiskLimitsChecker().validate(
        account,
        current_spread_pips=None,
        current_spread_price=0.0003,
        stop_distance_price=0.0010,
    )
    assert reason == RiskRejectReason.SPREAD_TOO_HIGH


def test_mock_broker_labels_risk_fields_as_available_simulation_inputs():
    broker = MockMT5Adapter()
    account = broker.get_account_info()
    symbol = broker.get_symbol_info("EURUSD")

    assert account.free_margin is not None
    assert account.daily_pnl is not None
    assert account.open_positions_count is not None
    assert symbol.point is not None
    assert symbol.trade_tick_size is not None
    assert symbol.trade_tick_value is not None
    assert symbol.volume_step is not None


def test_risk_engine_rejects_missing_spread_by_default():
    account = AccountState(
        balance=10_000, equity=10_000, free_margin=10_000,
        daily_pnl=0, open_positions_count=0,
    )
    result = RiskEngine().evaluate_signal(
        signal=_signal(),
        account=account,
        current_price=1.0850,
    )
    assert result.status == RiskStatus.REJECTED
    assert result.reject_reason == RiskRejectReason.MISSING_RISK_INPUTS
    assert "MISSING_CURRENT_SPREAD" in result.audit_trail


def test_limits_reject_when_both_spread_measurements_are_missing():
    from core.risk.services.limits import RiskLimitsChecker

    account = AccountState(
        balance=10_000, equity=10_000, free_margin=10_000,
        daily_pnl=0, open_positions_count=0,
    )
    reason = RiskLimitsChecker().validate(account, current_spread_pips=None)
    assert reason == RiskRejectReason.MISSING_RISK_INPUTS


def test_mock_broker_provides_an_explicit_synthetic_current_quote():
    broker = MockMT5Adapter()
    quote = broker.get_current_quote("EURUSD")
    assert quote is not None
    assert quote.bid > 0
    assert quote.ask >= quote.bid
    assert quote.timestamp.tzinfo is not None


def test_current_quote_validation_rejects_stale_and_naive_quotes():
    from datetime import timedelta
    from brokers.base.interface import MarketQuote
    from core.decision.service import _usable_current_quote

    now = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
    from core.decision.service import MAX_CURRENT_QUOTE_AGE_SECONDS
    stale = MarketQuote(
        symbol="EURUSD", bid=1.0849, ask=1.0850,
        timestamp=now - timedelta(seconds=MAX_CURRENT_QUOTE_AGE_SECONDS + 1),
    )
    naive = MarketQuote(
        symbol="EURUSD", bid=1.0849, ask=1.0850,
        timestamp=datetime(2026, 10, 16, 12, 0),
    )
    assert _usable_current_quote(stale, now=now) is None
    assert _usable_current_quote(naive, now=now) is None


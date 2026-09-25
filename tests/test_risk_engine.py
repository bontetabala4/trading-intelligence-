from datetime import datetime, timezone
from core.strategy.domain.models import StrategySignal
from core.strategy.domain.enums import SignalType, StrategyID
from core.regime.domain.enums import TrendRegime
from core.risk.domain.models import AccountState
from core.risk.domain.enums import RiskStatus, RiskRejectReason
from core.risk.services.engine import RiskEngine

def test_risk_engine_approval():
    engine = RiskEngine()

    signal = StrategySignal(
        symbol="EURUSD",
        timeframe="M15",
        timestamp=datetime.now(timezone.utc),
        strategy_id=StrategyID.TREND_FOLLOWING,
        signal=SignalType.BUY,
        strength=0.8,
        regime_context=TrendRegime.TRENDING_BULL,
        suggested_sl_pips=15.0,
        suggested_tp_pips=30.0
    )

    account = AccountState(balance=10000.0, equity=10000.0, free_margin=10000.0)

    proposal = engine.evaluate_signal(signal, account, current_price=1.0850)

    assert proposal.status == RiskStatus.APPROVED
    # 1% de 10 000$ = 100$ de risque. 15 pips * 10$/pip = 150$ de risque par lot. 100 / 150 = 0.66 lot
    assert proposal.volume_lots == 0.66
    assert proposal.stop_loss == 1.0835
    assert proposal.take_profit == 1.0880

def test_risk_engine_rejection_daily_drawdown():
    engine = RiskEngine()

    signal = StrategySignal(
        symbol="EURUSD",
        timeframe="M15",
        timestamp=datetime.now(timezone.utc),
        strategy_id=StrategyID.TREND_FOLLOWING,
        signal=SignalType.BUY,
        strength=0.8,
        regime_context=TrendRegime.TRENDING_BULL
    )

    # Perte de 600$ sur un compte de 10k$ (> 5% max drawdown)
    account = AccountState(balance=10000.0, equity=9400.0, free_margin=9400.0, daily_pnl=-600.0)

    proposal = engine.evaluate_signal(signal, account, current_price=1.0850)

    assert proposal.status == RiskStatus.REJECTED
    assert proposal.reject_reason == RiskRejectReason.MAX_DAILY_DRAWDOWN_REACHED
    assert proposal.volume_lots == 0.0
from fastapi import APIRouter, Query
from datetime import datetime, timezone
from core.strategy.domain.models import StrategySignal
from core.strategy.domain.enums import SignalType, StrategyID
from core.regime.domain.enums import TrendRegime
from core.risk.domain.models import AccountState, OrderProposal
from core.risk.services.engine import RiskEngine

router = APIRouter(prefix="/risk", tags=["Risk Management"])
risk_engine = RiskEngine()

@router.get("/evaluate", response_model=OrderProposal)
async def evaluate_risk(
    symbol: str = "EURUSD",
    signal_type: SignalType = SignalType.BUY,
    price: float = 1.0850,
    balance: float = Query(10000.0, gt=0)
):
    fake_signal = StrategySignal(
        symbol=symbol,
        timeframe="M15",
        timestamp=datetime.now(timezone.utc),
        strategy_id=StrategyID.TREND_FOLLOWING,
        signal=signal_type,
        strength=0.8,
        regime_context=TrendRegime.TRENDING_BULL,
        evidence=["RSI_HEALTHY_BULLISH"],
        suggested_sl_pips=15.0,
        suggested_tp_pips=30.0
    )

    fake_account = AccountState(
        balance=balance,
        equity=balance,
        free_margin=balance,
        daily_pnl=0.0,
        open_positions_count=0
    )

    return risk_engine.evaluate_signal(
        signal=fake_signal,
        account=fake_account,
        current_price=price,
        current_spread_pips=1.0
    )
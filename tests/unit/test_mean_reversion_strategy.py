from datetime import datetime, timezone

from core.regime.domain.enums import TrendRegime, VolatilityState, ConfidenceLevel
from core.regime.domain.models import MarketRegime
from core.strategy.domain.enums import SignalType, StrategyID
from core.strategy.strategies.mean_reversion import MeanReversionStrategy


def test_mean_reversion_uses_two_risk_reward_ratio():
    strategy = MeanReversionStrategy()

    regime = MarketRegime(
        symbol="EURUSD",
        timeframe="M15",
        timestamp=datetime.now(timezone.utc),
        regime=TrendRegime.RANGING,
        volatility_state=VolatilityState.NORMAL_VOLATILITY,
        strength=0.8,
        confidence=ConfidenceLevel.HIGH,
        data_quality="VALID",
    )

    signal = strategy.evaluate(
        regime=regime,
        features={
            "rsi_14": 30.0,
            "atr_14": 0.0010,
        },
    )

    assert signal.strategy_id == StrategyID.MEAN_REVERSION
    assert signal.signal == SignalType.BUY
    assert signal.suggested_sl_distance == 0.0010
    assert signal.suggested_tp_distance == 0.0020
    assert signal.suggested_tp_distance / signal.suggested_sl_distance == 2.0

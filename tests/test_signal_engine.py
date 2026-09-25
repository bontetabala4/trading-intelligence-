from datetime import datetime, timezone
from core.regime.services.engine import MarketRegimeEngine
from core.strategy.services.engine import StrategyEngine
from core.strategy.domain.enums import SignalType, StrategyID


def test_trend_following_signal():
    regime_engine = MarketRegimeEngine()
    strategy_engine = StrategyEngine()

    bull_features = {
        "ema_20": 1.0850,
        "ema_50": 1.0810,
        "rsi_14": 58.4,
        "atr_14": 0.0012,
        "true_range": 0.0015,
    }

    now = datetime.now(timezone.utc)
    regime = regime_engine.evaluate("EURUSD", "M15", now, bull_features, "VALID")
    signals = strategy_engine.evaluate_all(regime, bull_features)

    assert len(signals) == 1
    assert signals[0].strategy_id == StrategyID.TREND_FOLLOWING
    assert signals[0].signal == SignalType.BUY
    assert signals[0].strength > 0.0


def test_mean_reversion_in_ranging_regime():
    regime_engine = MarketRegimeEngine()
    strategy_engine = StrategyEngine()

    ranging_features = {
        "ema_20": 1.0820,
        "ema_50": 1.0820,
        "rsi_14": 28.0,  # Survendu
        "atr_14": 0.0010,
        "true_range": 0.0008,
    }

    now = datetime.now(timezone.utc)
    regime = regime_engine.evaluate("EURUSD", "M15", now, ranging_features, "VALID")
    signals = strategy_engine.evaluate_all(regime, ranging_features)

    assert len(signals) == 1
    assert signals[0].strategy_id == StrategyID.MEAN_REVERSION
    assert signals[0].signal == SignalType.BUY
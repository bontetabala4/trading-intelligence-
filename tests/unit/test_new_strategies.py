"""
Unit tests for the new quantitative strategy family:
1. MacroTrendStrategy (EMA 200 Paul Tudor Jones inspiration)
2. BreakoutPriceActionStrategy (Jesse Livermore inspiration)
3. FibonacciPullbackStrategy
4. MultiTimeframeStrategy
"""
from datetime import datetime, timezone
import pytest

from core.regime.domain.enums import TrendRegime, VolatilityState, ConfidenceLevel
from core.regime.domain.models import MarketRegime
from core.strategy.domain.enums import SignalType, StrategyID
from core.strategy.strategies.macro_trend import MacroTrendStrategy
from core.strategy.strategies.breakout import BreakoutPriceActionStrategy
from core.strategy.strategies.fibonacci_pullback import FibonacciPullbackStrategy
from core.strategy.strategies.multi_timeframe import MultiTimeframeStrategy


def make_regime(trend: TrendRegime = TrendRegime.TRENDING_BULL) -> MarketRegime:
    return MarketRegime(
        symbol="EURUSD",
        timeframe="M15",
        timestamp=datetime.now(timezone.utc),
        regime=trend,
        volatility_state=VolatilityState.NORMAL_VOLATILITY,
        strength=0.8,
        confidence=ConfidenceLevel.HIGH,
        data_quality="VALID",
    )


# --- 1. Macro Trend (EMA 200) ---

def test_macro_trend_bullish_signal_above_ema200():
    strategy = MacroTrendStrategy()
    regime = make_regime(TrendRegime.TRENDING_BULL)
    features = {
        "close": 1.1000,
        "ema_200": 1.0800,  # Price is well above EMA200
        "rsi_14": 58.0,      # Healthy bullish
        "atr_14": 0.0012,
    }
    signal = strategy.evaluate(regime, features)
    assert signal.signal == SignalType.BUY
    assert signal.strategy_id == StrategyID.EMA200_MACRO_TREND
    assert signal.suggested_sl_distance == round(0.0012 * 2.0, 8)
    assert signal.suggested_tp_distance == round(0.0012 * 4.0, 8)


def test_macro_trend_bearish_signal_below_ema200():
    strategy = MacroTrendStrategy()
    regime = make_regime(TrendRegime.TRENDING_BEAR)
    features = {
        "close": 1.0700,
        "ema_200": 1.0900,  # Price is well below EMA200
        "rsi_14": 42.0,      # Healthy bearish
        "atr_14": 0.0012,
    }
    signal = strategy.evaluate(regime, features)
    assert signal.signal == SignalType.SELL
    assert signal.strategy_id == StrategyID.EMA200_MACRO_TREND


def test_macro_trend_neutral_when_insufficient_history():
    strategy = MacroTrendStrategy()
    regime = make_regime(TrendRegime.TRENDING_BULL)
    features = {
        "close": 1.1000,
        "ema_200": None,  # Insufficient history
        "rsi_14": 58.0,
    }
    signal = strategy.evaluate(regime, features)
    assert signal.signal == SignalType.NEUTRAL
    assert any("INSUFFICIENT_HISTORY" in ev for ev in signal.evidence)


# --- 2. Breakout Price Action ---

def test_breakout_bullish_above_rolling_high():
    strategy = BreakoutPriceActionStrategy()
    regime = make_regime(TrendRegime.TRENDING_BULL)
    features = {
        "close": 1.1050,
        "rolling_high_20": 1.1020,
        "rsi_14": 62.0,
        "volume_ratio": 1.3,
        "atr_14": 0.0015,
    }
    signal = strategy.evaluate(regime, features)
    assert signal.signal == SignalType.BUY
    assert signal.strategy_id == StrategyID.BREAKOUT_PRICE_ACTION
    assert signal.suggested_sl_distance == round(0.0015 * 1.5, 8)
    assert signal.suggested_tp_distance == round(0.0015 * 3.0, 8)


def test_breakout_neutral_inside_range():
    strategy = BreakoutPriceActionStrategy()
    regime = make_regime(TrendRegime.RANGING)
    features = {
        "close": 1.0950,
        "rolling_high_20": 1.1000,
        "rolling_low_20": 1.0900,
        "rsi_14": 50.0,
    }
    signal = strategy.evaluate(regime, features)
    assert signal.signal == SignalType.NEUTRAL


# --- 3. Fibonacci Pullback ---

def test_fibonacci_pullback_bullish_in_golden_zone():
    strategy = FibonacciPullbackStrategy()
    regime = make_regime(TrendRegime.TRENDING_BULL)
    # Swing: Low=1.0000, High=1.1000 (Range = 0.1000)
    # 38.2% = 1.1000 - 0.0382 = 1.0618
    # 61.8% = 1.1000 - 0.0618 = 1.0382
    # Golden Zone: 1.0382 to 1.0618
    features = {
        "close": 1.0500,  # inside [1.0382, 1.0618]
        "swing_high_30": 1.1000,
        "swing_low_30": 1.0000,
        "rsi_14": 46.0,  # recovering
        "atr_14": 0.0020,
    }
    signal = strategy.evaluate(regime, features)
    assert signal.signal == SignalType.BUY
    assert signal.strategy_id == StrategyID.FIBONACCI_PULLBACK
    assert any("GOLDEN_ZONE" in ev for ev in signal.evidence)


def test_fibonacci_pullback_neutral_outside_zone():
    strategy = FibonacciPullbackStrategy()
    regime = make_regime(TrendRegime.TRENDING_BULL)
    features = {
        "close": 1.0950,  # near the top, no pullback
        "swing_high_30": 1.1000,
        "swing_low_30": 1.0000,
        "rsi_14": 65.0,
    }
    signal = strategy.evaluate(regime, features)
    assert signal.signal == SignalType.NEUTRAL


# --- 4. Multi-Timeframe ---

def test_mtf_bullish_alignment():
    strategy = MultiTimeframeStrategy()
    regime = make_regime(TrendRegime.TRENDING_BULL)
    features = {
        "htf_trend": "BULL",
        "htf_regime": "TRENDING_BULL",
        "rsi_14": 56.0,
        "atr_14": 0.0010,
    }
    signal = strategy.evaluate(regime, features)
    assert signal.signal == SignalType.BUY
    assert signal.strategy_id == StrategyID.MULTI_TIMEFRAME


def test_mtf_no_trade_when_htf_missing():
    strategy = MultiTimeframeStrategy()
    regime = make_regime(TrendRegime.TRENDING_BULL)
    features = {
        "htf_trend": None,
        "htf_regime": None,
        "rsi_14": 56.0,
    }
    signal = strategy.evaluate(regime, features)
    assert signal.signal == SignalType.NEUTRAL
    assert any("NO_TRADE_MISSING_OR_STALE_HTF_DATA" in ev for ev in signal.evidence)

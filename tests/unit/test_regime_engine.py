from datetime import datetime, timezone

from core.market.structure import MarketStructure, MarketStructureState
from core.regime.domain.enums import ConfidenceLevel, TrendRegime
from core.regime.services.engine import MarketRegimeEngine


def make_features(
    *,
    ema_20: float = 1.0850,
    ema_50: float = 1.0810,
    rsi_14: float = 58.0,
    atr_14: float = 0.0012,
    true_range: float = 0.0015,
) -> dict:
    return {
        "ema_20": ema_20,
        "ema_50": ema_50,
        "rsi_14": rsi_14,
        "atr_14": atr_14,
        "true_range": true_range,
    }


def make_structure(state: MarketStructureState) -> MarketStructure:
    return MarketStructure(
        state=state,
        swing_highs=(),
        swing_lows=(),
        protected_level=None,
        protected_level_type=None,
    )


def evaluate(*, features: dict, structure: MarketStructure | None):
    engine = MarketRegimeEngine()

    return engine.evaluate(
        symbol="EURUSD",
        timeframe="M15",
        timestamp=datetime.now(timezone.utc),
        features=features,
        data_quality="VALID",
        market_structure=structure,
    )


def test_bullish_structure_aligned_with_bullish_indicators():
    result = evaluate(
        features=make_features(
            ema_20=1.0850,
            ema_50=1.0810,
            rsi_14=58.0,
        ),
        structure=make_structure(MarketStructureState.BULLISH),
    )

    assert result.regime == TrendRegime.TRENDING_BULL
    assert result.confidence == ConfidenceLevel.HIGH
    assert "MARKET_STRUCTURE_BULLISH_CONFIRMED" in result.evidence


def test_bearish_structure_aligned_with_bearish_indicators():
    result = evaluate(
        features=make_features(
            ema_20=1.0810,
            ema_50=1.0850,
            rsi_14=42.0,
        ),
        structure=make_structure(MarketStructureState.BEARISH),
    )

    assert result.regime == TrendRegime.TRENDING_BEAR
    assert result.confidence == ConfidenceLevel.HIGH
    assert "MARKET_STRUCTURE_BEARISH_CONFIRMED" in result.evidence


def test_bullish_structure_contradicted_by_bearish_indicators_is_transition():
    result = evaluate(
        features=make_features(
            ema_20=1.0810,
            ema_50=1.0850,
            rsi_14=42.0,
        ),
        structure=make_structure(MarketStructureState.BULLISH),
    )

    assert result.regime == TrendRegime.TRANSITION
    assert result.confidence in (
        ConfidenceLevel.MEDIUM,
        ConfidenceLevel.LOW,
    )
    assert "MARKET_STRUCTURE_INDICATOR_DIVERGENCE" in result.evidence


def test_bearish_structure_contradicted_by_bullish_indicators_is_transition():
    result = evaluate(
        features=make_features(
            ema_20=1.0850,
            ema_50=1.0810,
            rsi_14=58.0,
        ),
        structure=make_structure(MarketStructureState.BEARISH),
    )

    assert result.regime == TrendRegime.TRANSITION
    assert result.confidence in (
        ConfidenceLevel.MEDIUM,
        ConfidenceLevel.LOW,
    )
    assert "MARKET_STRUCTURE_INDICATOR_DIVERGENCE" in result.evidence


def test_range_structure_with_no_clear_trend_is_ranging():
    result = evaluate(
        features=make_features(
            ema_20=1.0830,
            ema_50=1.0828,
            rsi_14=50.0,
        ),
        structure=make_structure(MarketStructureState.RANGE),
    )

    assert result.regime == TrendRegime.RANGING


def test_uncertain_structure_does_not_override_indicator_regime():
    result = evaluate(
        features=make_features(
            ema_20=1.0850,
            ema_50=1.0810,
            rsi_14=58.0,
        ),
        structure=make_structure(MarketStructureState.UNCERTAIN),
    )

    assert result.regime == TrendRegime.TRENDING_BULL


def test_without_market_structure_keeps_backward_compatible_behavior():
    result = evaluate(
        features=make_features(
            ema_20=1.0850,
            ema_50=1.0810,
            rsi_14=58.0,
        ),
        structure=None,
    )

    assert result.regime == TrendRegime.TRENDING_BULL
    assert result.confidence == ConfidenceLevel.HIGH


def test_invalid_data_quality_still_blocks_regime_classification():
    result = MarketRegimeEngine().evaluate(
        symbol="EURUSD",
        timeframe="M15",
        timestamp=datetime.now(timezone.utc),
        features=make_features(),
        data_quality="INVALID",
        market_structure=make_structure(MarketStructureState.BULLISH),
    )

    assert result.regime == TrendRegime.UNCERTAIN
    assert result.confidence == ConfidenceLevel.LOW
    assert "DATA_QUALITY_NOT_VALID" in result.evidence
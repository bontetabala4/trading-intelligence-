"""
Tests unitaires et d'intégration pour l'Étape 6 : Moteur de Quantification
et de Validation d'Opportunités (ATIP Engine).
"""
from datetime import datetime, timezone
import pytest

from core.opportunity.detector import OpportunityDetector
from core.opportunity.models import (
    Opportunity,
    OpportunityDirection,
    OpportunityResult,
    OpportunityScore,
    ValidationStatus,
)
from core.opportunity.quantifier import OpportunityQuantifier
from core.opportunity.validator import OpportunityValidator
from core.signal import SignalAction, SignalEngine
from core.signal.signal_engine import SignalEngine


@pytest.fixture
def sample_timestamp():
    return datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_features():
    return {
        "close": 1.0850,
        "atr": 0.0015,
        "rsi": 58.0,
        "trend_slope": 0.0004,
        "bb_upper": 1.0890,
        "bb_lower": 1.0810,
    }


# ------------------------------------------------------------------
# 1. Tests de l'OpportunityDetector
# ------------------------------------------------------------------

def test_detector_creates_bullish_opportunity(sample_timestamp, sample_features):
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="TRENDING_BULL",
        strategy_name="Trend Following",
        strategy_evaluation={"is_compatible": True, "signal": "BUY"},
        features=sample_features,
        data_quality_score=0.95,
    )

    assert opp is not None
    assert opp.symbol == "EURUSD"
    assert opp.direction == OpportunityDirection.BULLISH
    assert opp.entry_reference == 1.0850
    assert opp.stop_reference < 1.0850
    assert opp.target_reference > 1.0850


def test_detector_creates_bearish_opportunity(sample_timestamp, sample_features):
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="GBPUSD",
        asset_class="FOREX",
        timeframe="H1",
        timestamp=sample_timestamp,
        market_regime="TRENDING_BEAR",
        strategy_name="Breakout",
        strategy_evaluation={"is_compatible": True, "signal": "SELL"},
        features=sample_features,
        data_quality_score=0.90,
    )

    assert opp is not None
    assert opp.direction == OpportunityDirection.BEARISH
    assert opp.stop_reference > 1.0850
    assert opp.target_reference < 1.0850


def test_detector_returns_none_on_neutral_signal(sample_timestamp, sample_features):
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="RANGING",
        strategy_name="Mean Reversion",
        strategy_evaluation={"is_compatible": True, "signal": "NEUTRAL"},
        features=sample_features,
        data_quality_score=1.0,
    )

    assert opp is None


def test_detector_returns_none_when_incompatible(sample_timestamp, sample_features):
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="HIGH_VOLATILITY",
        strategy_name="Trend Following",
        strategy_evaluation={"is_compatible": False, "signal": "BUY"},
        features=sample_features,
        data_quality_score=1.0,
    )

    assert opp is None


def test_detector_naive_timestamp_raises_value_error(sample_features):
    detector = OpportunityDetector()
    naive_ts = datetime(2026, 9, 24, 12, 0, 0)  # pas de tzinfo

    with pytest.raises(ValueError, match="timezone-aware"):
        detector.detect(
            symbol="EURUSD",
            asset_class="FOREX",
            timeframe="M15",
            timestamp=naive_ts,
            market_regime="TRENDING_BULL",
            strategy_name="Trend Following",
            strategy_evaluation={"is_compatible": True, "signal": "BUY"},
            features=sample_features,
        )


# ------------------------------------------------------------------
# 2. Tests de l'OpportunityQuantifier
# ------------------------------------------------------------------

def test_quantifier_score_bounds_and_structure(sample_timestamp, sample_features):
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="TRENDING_BULL",
        strategy_name="Trend Following",
        strategy_evaluation={"is_compatible": True, "signal": "BUY"},
        features=sample_features,
        data_quality_score=1.0,
    )

    quantifier = OpportunityQuantifier()
    score = quantifier.quantify(opp)

    assert 0.0 <= score.total_score <= 100.0
    assert len(score.sub_scores) == 6
    assert sum(score.sub_scores.values()) == pytest.approx(score.total_score, rel=1e-2)


def test_quantifier_handles_missing_rsi_or_atr(sample_timestamp):
    sparse_features = {"close": 1.0850}  # ni rsi ni atr
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="RANGING",
        strategy_name="Mean Reversion",
        strategy_evaluation={"is_compatible": True, "signal": "BUY"},
        features=sparse_features,
        data_quality_score=0.80,
    )

    quantifier = OpportunityQuantifier()
    score = quantifier.quantify(opp)

    assert score.sub_scores["momentum_quality"] == 0.0
    assert score.sub_scores["volatility_quality"] == 0.0
    assert 0.0 <= score.total_score <= 100.0


# ------------------------------------------------------------------
# 3. Tests de l'OpportunityValidator
# ------------------------------------------------------------------

def test_validator_accepts_high_score(sample_timestamp, sample_features):
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="TRENDING_BULL",
        strategy_name="Trend Following",
        strategy_evaluation={"is_compatible": True, "signal": "BUY"},
        features=sample_features,
        data_quality_score=1.0,
    )

    quantifier = OpportunityQuantifier()
    score = quantifier.quantify(opp)

    validator = OpportunityValidator(valid_score_threshold=65.0)
    result = validator.validate(opp, score)

    assert result.status == ValidationStatus.VALID
    assert result.score.total_score >= 65.0


def test_validator_uncertain_score_range(sample_timestamp):
    # Setup avec score intermédiaire
    partial_features = {"close": 1.0850, "rsi": 50.0}
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="UNCERTAIN",
        strategy_name="Trend Following",
        strategy_evaluation={"is_compatible": True, "signal": "BUY"},
        features=partial_features,
        data_quality_score=0.75,
    )

    quantifier = OpportunityQuantifier()
    score = quantifier.quantify(opp)

    validator = OpportunityValidator(valid_score_threshold=80.0, uncertain_score_threshold=40.0)
    result = validator.validate(opp, score)

    assert result.status in (ValidationStatus.UNCERTAIN, ValidationStatus.REJECTED)


def test_validator_rejects_low_data_quality(sample_timestamp, sample_features):
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="TRENDING_BULL",
        strategy_name="Trend Following",
        strategy_evaluation={"is_compatible": True, "signal": "BUY"},
        features=sample_features,
        data_quality_score=0.40,  # Bien en dessous du seuil de 0.70
    )

    quantifier = OpportunityQuantifier()
    score = quantifier.quantify(opp)

    validator = OpportunityValidator(min_data_quality=0.70)
    result = validator.validate(opp, score)

    assert result.status == ValidationStatus.REJECTED
    assert any("Qualité des données" in reason for reason in result.reasons)


def test_validator_rejects_incompatible_strategy(sample_timestamp, sample_features):
    # Création manuelle pour forcer l'incompatibilité
    opp = Opportunity(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="HIGH_VOLATILITY",
        strategy_name="Scalping",
        direction=OpportunityDirection.BULLISH,
        entry_reference=1.0850,
        evidence={"strategy_evaluation": {"is_compatible": False, "signal": "BUY"}},
        data_quality_score=0.95,
    )

    quantifier = OpportunityQuantifier()
    score = quantifier.quantify(opp)

    validator = OpportunityValidator()
    result = validator.validate(opp, score)

    assert result.status == ValidationStatus.REJECTED
    assert any("incompatible" in reason for reason in result.reasons)


# ------------------------------------------------------------------
# 4. Tests d'Intégration (Pipeline Opportunity -> Signal Engine)
# ------------------------------------------------------------------

def test_pipeline_valid_opportunity_to_buy_signal(sample_timestamp, sample_features):
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="TRENDING_BULL",
        strategy_name="Trend Following",
        strategy_evaluation={"is_compatible": True, "signal": "BUY"},
        features=sample_features,
        data_quality_score=1.0,
    )

    score = OpportunityQuantifier().quantify(opp)
    opp_result = OpportunityValidator().validate(opp, score)

    signal_engine = SignalEngine()
    candidate = signal_engine.process_opportunity(opp_result)

    assert candidate.action == SignalAction.BUY
    assert candidate.symbol == "EURUSD"
    assert candidate.confidence > 0.60
    assert candidate.entry_price == 1.0850


def test_pipeline_rejected_opportunity_to_no_trade_signal(sample_timestamp, sample_features):
    detector = OpportunityDetector()
    opp = detector.detect(
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="M15",
        timestamp=sample_timestamp,
        market_regime="TRENDING_BULL",
        strategy_name="Trend Following",
        strategy_evaluation={"is_compatible": True, "signal": "BUY"},
        features=sample_features,
        data_quality_score=0.30,  # Rejeté pour mauvaise qualité
    )

    score = OpportunityQuantifier().quantify(opp)
    opp_result = OpportunityValidator(min_data_quality=0.70).validate(opp, score)

    signal_engine = SignalEngine()
    candidate = signal_engine.process_opportunity(opp_result)

    assert candidate.action == SignalAction.NO_TRADE
    assert candidate.rationale["status"] == "REJECTED"
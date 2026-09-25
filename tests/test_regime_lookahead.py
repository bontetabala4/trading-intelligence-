from datetime import datetime, timezone
from core.regime.services.engine import MarketRegimeEngine

def test_regime_anti_lookahead():
    engine = MarketRegimeEngine()
    
    # Données à l'instant T
    features_t = {
        "ema_20": 1.0850,
        "ema_50": 1.0810,
        "rsi_14": 58.4,
        "atr_14": 0.0012,
        "true_range": 0.0015
    }
    
    now = datetime.now(timezone.utc)
    regime_before = engine.evaluate("EURUSD", "M15", now, features_t, "VALID")
    
    # Modification d'une bougie future à T+1 (ne doit pas impacter T)
    features_t_plus_1 = features_t.copy()
    features_t_plus_1["rsi_14"] = 20.0  # Chute brutale future
    
    regime_after = engine.evaluate("EURUSD", "M15", now, features_t, "VALID")
    
    assert regime_before.regime == regime_after.regime
    assert regime_before.strength == regime_after.strength

    
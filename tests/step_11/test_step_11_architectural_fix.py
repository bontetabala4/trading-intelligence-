"""
Suite de tests de validation d'architecture — Step 11 Fix
Garantit la parité Backtest / Forward Paper Trading, l'isolation hors-échantillon et l'absence de lookahead.
"""

import pytest
import pandas as pd
import numpy as np
import datetime
import os

from core.paper_trading.forward_paper_engine import ForwardPaperEngine, PaperBroker
from core.signal.signal_engine import SignalEngine


def generate_mock_data(periods=200, seed=42):
    """Génère un dataframe OHLCV déterministe pour les tests."""
    np.random.seed(seed)
    start_dt = datetime.datetime(2024, 1, 1, 0, 0)
    timestamps = [start_dt + datetime.timedelta(minutes=15 * i) for i in range(periods)]
    
    price = 1.1000
    data = []
    for ts in timestamps:
        change = np.random.normal(0, 0.0008)
        price += change
        high = price + abs(np.random.normal(0, 0.0004))
        low = price - abs(np.random.normal(0, 0.0004))
        close = price
        data.append({
            "timestamp": ts, 
            "open": price, 
            "high": high, 
            "low": low, 
            "close": close, 
            "volume": 1000
        })
        
    return pd.DataFrame(data)


def _extract_signal_value(output):
    """Extrait de manière sécurisée la valeur du signal d'un dictionnaire ou d'un objet."""
    if isinstance(output, dict):
        val = output.get("signal") or output.get("action") or output.get("direction")
        return str(val) if val is not None else "NO_TRADE"
    elif hasattr(output, "signal"):
        return str(output.signal)
    elif hasattr(output, "action"):
        return str(output.action)
    return str(output)


def test_forward_engine_uses_official_signal_engine():
    engine = ForwardPaperEngine()
    assert hasattr(engine, "signal_engine")
    assert isinstance(engine.signal_engine, SignalEngine)


def test_no_direct_strategy_calls_in_paper_engine():
    engine = ForwardPaperEngine()
    assert not hasattr(engine, "strategies")
    assert not hasattr(engine, "evaluate_strategy")


def test_backtest_forward_signal_equivalence():
    df = generate_mock_data(100)
    fwd_engine = ForwardPaperEngine()
    sig_engine = SignalEngine()

    raw_direct = sig_engine.process(df)
    direct_signal_str = _extract_signal_value(raw_direct)
    
    res = fwd_engine.process_next_bar(df, len(df) - 1)
    fwd_signal_str = _extract_signal_value(res["signal_output"])
    
    assert fwd_signal_str == direct_signal_str


def test_no_lookahead_future_mutation():
    df = generate_mock_data(100)
    fwd_engine1 = ForwardPaperEngine()
    res1 = fwd_engine1.process_next_bar(df, 50)

    # Altération des données futures à l'index 51
    df_mutated = df.copy()
    df_mutated.iloc[51, df_mutated.columns.get_loc("close")] += 10.0

    fwd_engine2 = ForwardPaperEngine()
    res2 = fwd_engine2.process_next_bar(df_mutated, 50)

    sig1 = _extract_signal_value(res1["signal_output"])
    sig2 = _extract_signal_value(res2["signal_output"])

    assert sig1 == sig2


def test_january_2025_isolation():
    df_2024 = generate_mock_data(100, seed=123)
    df_2025 = generate_mock_data(150, seed=123)

    fwd1 = ForwardPaperEngine()
    fwd2 = ForwardPaperEngine()

    sig_out1 = fwd1.process_next_bar(df_2024, 99)["signal_output"]
    sig_out2 = fwd2.process_next_bar(df_2025, 99)["signal_output"]

    sig1 = _extract_signal_value(sig_out1)
    sig2 = _extract_signal_value(sig_out2)

    assert sig1 == sig2


def test_checkpoint_and_resume():
    df = generate_mock_data(80)
    fwd = ForwardPaperEngine(run_id="RUN_ORIGINAL")
    
    for i in range(25, 50):
        fwd.process_next_bar(df, i)
        
    chkpt = fwd.export_checkpoint("MOCK_DS")
    
    fwd_resumed = ForwardPaperEngine()
    fwd_resumed.load_checkpoint(chkpt)
    
    assert fwd_resumed.cursor == 49
    assert len(fwd_resumed.broker.positions) == len(fwd.broker.positions)
    assert len(fwd_resumed.broker.closed_trades) == len(fwd.broker.closed_trades)


def test_end_of_data_close():
    broker = PaperBroker()
    bar = pd.Series({
        "timestamp": "2024-12-31 23:45", 
        "open": 1.1000, 
        "high": 1.1020, 
        "low": 1.0980, 
        "close": 1.1010
    })
    
    broker.positions.append({
        "id": "POS_TEST",
        "direction": "BUY",
        "entry_time": "2024-12-31 20:00",
        "entry_price": 1.1000,
        "stop_price": 1.0950,
        "target_price": 1.1100
    })
    
    closed = broker.close_all_positions_end_of_data(bar)
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "END_OF_DATA"
    assert closed[0]["exit_price"] == 1.1010


def test_ambiguous_bar_stop_loss_first():
    broker = PaperBroker()
    broker.positions.append({
        "id": "POS_AMBIG",
        "direction": "BUY",
        "entry_time": "2024-01-01 10:00",
        "entry_price": 1.1000,
        "stop_price": 1.0950,
        "target_price": 1.1050
    })
    
    ambig_bar = pd.Series({
        "timestamp": "2024-01-01 10:15", 
        "open": 1.1000, 
        "high": 1.1060, 
        "low": 1.0940, 
        "close": 1.1020
    })
    exited = broker.update_positions(ambig_bar)
    
    assert len(exited) == 1
    assert exited[0]["exit_reason"] == "STOP_LOSS"
    assert exited[0]["exit_price"] == 1.0950


def test_mt5_static_code_isolation():
    paper_dir = "core/paper_trading"
    forbidden = ["MetaTrader5", "order_send", "positions_get", "orders_get", "symbol_select"]
    
    if os.path.exists(paper_dir):
        for root, _, files in os.walk(paper_dir):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    with open(path, "r", encoding="utf-8") as file_content:
                        text = file_content.read()
                        for term in forbidden:
                            assert term not in text, f"Code MT5 interdit '{term}' détecté dans {path}"
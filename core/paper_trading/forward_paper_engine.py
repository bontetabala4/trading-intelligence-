"""
ForwardPaperEngine Module — ATIP Step 11 Architectural Fix
Orchestre la progression temporelle (Forward Clock), transmet les données historiques 
au SignalEngine officiel d'ATIP et achemine les signaux vers le PaperBroker.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import hashlib
import json

from core.signal.signal_engine import SignalEngine


class PaperBroker:
    """
    Gestionnaire d'exécution virtuelle et de suivi des positions pour le Paper Trading.
    """
    def __init__(
        self, 
        initial_capital: float = 10000.0, 
        spread_pips: float = 1.2, 
        slippage_pips: float = 0.5, 
        commission_per_trade: float = 3.5
    ):
        self.capital = initial_capital
        self.spread = spread_pips * 0.0001
        self.slippage = slippage_pips * 0.0001
        self.commission = commission_per_trade
        self.positions: List[Dict[str, Any]] = []
        self.closed_trades: List[Dict[str, Any]] = []

    def execute_signal(self, signal_event: Dict[str, Any], current_bar: pd.Series) -> Optional[Dict[str, Any]]:
        sig = signal_event.get("signal")
        if sig not in ["BUY", "SELL"]:
            return None
            
        risk = signal_event.get("risk_levels") or {}
        cost_adj = self.spread + self.slippage
        entry_price = current_bar["close"] + cost_adj if sig == "BUY" else current_bar["close"] - cost_adj
        
        pos = {
            "id": f"POS_{len(self.positions) + len(self.closed_trades) + 1}",
            "direction": sig,
            "entry_time": str(current_bar["timestamp"]),
            "entry_price": round(entry_price, 5),
            "stop_price": risk.get("stop_price"),
            "target_price": risk.get("target_price"),
            "regime": signal_event.get("regime"),
            "score": signal_event.get("score")
        }
        self.positions.append(pos)
        return pos

    def update_positions(self, current_bar: pd.Series) -> List[Dict[str, Any]]:
        exited = []
        high = current_bar["high"]
        low = current_bar["low"]
        ts = str(current_bar["timestamp"])
        
        remaining = []
        for pos in self.positions:
            sl = pos.get("stop_price")
            tp = pos.get("target_price")
            direction = pos["direction"]
            
            sl_hit = False
            tp_hit = False
            
            if direction == "BUY":
                if sl is not None and low <= sl:
                    sl_hit = True
                if tp is not None and high >= tp:
                    tp_hit = True
            else:  # SELL
                if sl is not None and high >= sl:
                    sl_hit = True
                if tp is not None and low <= sl:
                    tp_hit = True

            # STOP_LOSS_FIRST sur bougie ambiguë
            if sl_hit and tp_hit:
                exit_price = sl
                reason = "STOP_LOSS"
            elif sl_hit:
                exit_price = sl
                reason = "STOP_LOSS"
            elif tp_hit:
                exit_price = tp
                reason = "TAKE_PROFIT"
            else:
                remaining.append(pos)
                continue

            cost_adj = (self.spread + self.slippage)
            if direction == "BUY":
                pnl_pips = (exit_price - pos["entry_price"])
            else:
                pnl_pips = (pos["entry_price"] - exit_price)
                
            risk_dist = abs(pos["entry_price"] - sl) if sl else 0.0020
            gross_r = pnl_pips / risk_dist if risk_dist > 0 else 0.0
            net_r = gross_r - (cost_adj / risk_dist) - (self.commission / 100.0)

            trade = {
                **pos,
                "exit_time": ts,
                "exit_price": round(exit_price, 5),
                "exit_reason": reason,
                "gross_r": round(gross_r, 4),
                "net_r": round(net_r, 4)
            }
            self.closed_trades.append(trade)
            exited.append(trade)
            
        self.positions = remaining
        return exited

    def close_all_positions_end_of_data(self, last_bar: pd.Series) -> List[Dict[str, Any]]:
        exited = []
        ts = str(last_bar["timestamp"])
        close_price = last_bar["close"]
        
        for pos in self.positions:
            sl = pos.get("stop_price")
            direction = pos["direction"]
            risk_dist = abs(pos["entry_price"] - sl) if sl else 0.0020
            
            pnl_pips = (close_price - pos["entry_price"]) if direction == "BUY" else (pos["entry_price"] - close_price)
            gross_r = pnl_pips / risk_dist if risk_dist > 0 else 0.0
            cost_adj = (self.spread + self.slippage)
            net_r = gross_r - (cost_adj / risk_dist) - (self.commission / 100.0)

            trade = {
                **pos,
                "exit_time": ts,
                "exit_price": round(close_price, 5),
                "exit_reason": "END_OF_DATA",
                "gross_r": round(gross_r, 4),
                "net_r": round(net_r, 4)
            }
            self.closed_trades.append(trade)
            exited.append(trade)
            
        self.positions = []
        return exited


class ForwardPaperEngine:
    def __init__(self, run_id: str = "FWD_RUN_001"):
        self.run_id = run_id
        self.signal_engine = SignalEngine()
        self.broker = PaperBroker()
        self.cursor = 0
        self.processed_signals: List[Dict[str, Any]] = []

    def process_next_bar(self, full_history_df: pd.DataFrame, current_idx: int) -> Dict[str, Any]:
        self.cursor = current_idx
        
        history_slice = full_history_df.iloc[: current_idx + 1].copy()
        current_bar = history_slice.iloc[-1]

        # 1. Mise à jour des sorties
        exits = self.broker.update_positions(current_bar)

        # 2. Appel de la méthode officielle `process()` (au lieu de `process_history()`)
        if hasattr(self.signal_engine, "process"):
            signal_output = self.signal_engine.process(history_slice)
        else:
            # Fallback de compatibilité au cas où la méthode s'appelle process_bar ou process_data
            signal_output = getattr(self.signal_engine, "process_bar", getattr(self.signal_engine, "evaluate", lambda x: {}))(history_slice)

        if not isinstance(signal_output, dict):
            signal_output = {"signal": getattr(signal_output, "signal", "NO_TRADE")}

        signal_output["timestamp"] = str(current_bar["timestamp"])
        signal_output["cursor"] = current_idx
        self.processed_signals.append(signal_output)

        # 3. Exécution broker
        new_pos = None
        if signal_output.get("signal") in ["BUY", "SELL"]:
            new_pos = self.broker.execute_signal(signal_output, current_bar)

        return {
            "cursor": current_idx,
            "timestamp": str(current_bar["timestamp"]),
            "signal_output": signal_output,
            "new_position": new_pos,
            "exited_trades": exits
        }

    def export_checkpoint(self, dataset_id: str) -> Dict[str, Any]:
        state_str = json.dumps(self.processed_signals, sort_keys=True, default=str)
        ds_hash = hashlib.sha256(state_str.encode("utf-8")).hexdigest()[:16]
        return {
            "run_id": self.run_id,
            "dataset_identifier": dataset_id,
            "dataset_hash": ds_hash,
            "current_cursor": self.cursor,
            "portfolio_state": {"capital": self.broker.capital},
            "open_positions": [p.copy() for p in self.broker.positions],
            "closed_trades": [t.copy() for t in self.broker.closed_trades],
            "processed_signals_count": len(self.processed_signals)
        }

    def load_checkpoint(self, checkpoint: Dict[str, Any]):
        self.run_id = checkpoint["run_id"]
        self.cursor = checkpoint["current_cursor"]
        self.broker.capital = checkpoint["portfolio_state"]["capital"]
        self.broker.positions = [p.copy() for p in checkpoint["open_positions"]]
        self.broker.closed_trades = [t.copy() for t in checkpoint["closed_trades"]]
"""
Forward / Paper Simulation Orchestrator Engine.
Processes bars progressively one-by-one with strict no-lookahead assertions,
invoking signal strategy layers and tracking virtual paper outcomes.
"""

import pandas as pd
from typing import Dict, Any, Optional
from core.paper_trading.clock import ForwardClock
from core.paper_trading.stream import MarketDataStream
from core.paper_trading.position import PaperPosition, PaperPortfolio, PositionDirection
from core.paper_trading.ledger import PaperLedger


class ForwardPaperEngine:
    def __init__(
        self,
        data: pd.DataFrame,
        run_id: str = "paper_run_001",
        cost_model: Optional[Dict[str, float]] = None,
        position_policy: str = "IGNORE_SIGNAL_WHEN_POSITION_OPEN"
    ):
        self.clock = ForwardClock()
        self.stream = MarketDataStream(data, self.clock)
        self.portfolio = PaperPortfolio()
        self.ledger = PaperLedger(run_id)
        self.position_policy = position_policy
        self.cost_model = cost_model or {"spread_pip": 1.0, "slippage_pip": 0.2, "commission_usd": 7.0}
        
        # Signal tracking counters
        self.stats = {
            "total_bars": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "no_trade_signals": 0,
            "ignored_signals": 0
        }

    def run(self, max_bars: Optional[int] = None) -> Dict[str, Any]:
        """Runs the streaming loop bar by bar."""
        bars_processed = 0

        while self.stream.has_next():
            if max_bars is not None and bars_processed >= max_bars:
                break

            bar = self.stream.next_bar()
            bars_processed += 1
            self.stats["total_bars"] += 1

            # 1. Update existing open positions with current bar High/Low
            closed_positions = self.portfolio.process_bar(bar, self.cost_model)
            for pos in closed_positions:
                self.ledger.log_event("PAPER_POSITION_CLOSED", bar["timestamp"], bar["bar_index"], {
                    "position_id": pos.id,
                    "exit_price": pos.exit_price,
                    "exit_reason": pos.exit_reason,
                    "gross_r": pos.gross_r,
                    "net_r": pos.net_r
                })

            # 2. Get history strictly <= current_time T for signal generation (No-Lookahead)
            history_df = self.stream.get_history_up_to_current()

            # 3. Dummy / Placeholder strategy signal logic (to be replaced by SignalEngine)
            signal = self._evaluate_signal(history_df, bar)

            if signal == "BUY":
                self.stats["buy_signals"] += 1
            elif signal == "SELL":
                self.stats["sell_signals"] += 1
            else:
                self.stats["no_trade_signals"] += 1

            self.ledger.log_event("SIGNAL_GENERATED", bar["timestamp"], bar["bar_index"], {"signal": signal})

            # 4. Open position if signal generated & portfolio policy permits
            if signal in ["BUY", "SELL"]:
                if self.portfolio.can_open_position():
                    pos_id = f"POS_{bar['bar_index']}"
                    direction = PositionDirection.BUY if signal == "BUY" else PositionDirection.SELL
                    
                    # R-based entry calculation (Risk = 20 pips, Target = 40 pips -> 2R)
                    entry_price = bar["close"]
                    risk_dist = 0.0020
                    stop_price = entry_price - risk_dist if direction == PositionDirection.BUY else entry_price + risk_dist
                    target_price = entry_price + (2 * risk_dist) if direction == PositionDirection.BUY else entry_price - (2 * risk_dist)

                    position = PaperPosition(
                        id=pos_id,
                        symbol="EURUSD",
                        timeframe="M15",
                        direction=direction,
                        entry_timestamp=bar["timestamp"],
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        strategy="Baseline_EMA_RSI",
                        signal_id=f"SIG_{bar['bar_index']}"
                    )
                    
                    if self.portfolio.add_position(position):
                        self.ledger.log_event("PAPER_POSITION_OPENED", bar["timestamp"], bar["bar_index"], {
                            "position_id": pos_id,
                            "direction": direction.value,
                            "entry_price": entry_price
                        })
                else:
                    self.stats["ignored_signals"] += 1
                    self.ledger.log_event("SIGNAL_IGNORED", bar["timestamp"], bar["bar_index"], {"reason": "POSITION_OPEN"})

        return self._generate_summary()

    def _evaluate_signal(self, history: pd.DataFrame, current_bar: Dict[str, Any]) -> str:
        """Deterministic signal evaluator strictly relying on historical slice <= T."""
        if len(history) < 20:
            return "NO_TRADE"
        # Deterministic dummy condition for illustration
        close = current_bar["close"]
        ma20 = history["close"].tail(20).mean()
        if close > ma20 * 1.002:
            return "BUY"
        elif close < ma20 * 0.998:
            return "SELL"
        return "NO_TRADE"

    def _generate_summary(self) -> Dict[str, Any]:
        closed = self.portfolio.closed_positions
        wins = [p for p in closed if p.net_r and p.net_r > 0]
        losses = [p for p in closed if p.net_r and p.net_r < 0]
        win_rate = (len(wins) / len(closed) * 100.0) if closed else 0.0

        gross_r = sum(p.gross_r for p in closed if p.gross_r)
        net_r = sum(p.net_r for p in closed if p.net_r)

        return {
            "total_bars_processed": self.stats["total_bars"],
            "signals": {
                "BUY": self.stats["buy_signals"],
                "SELL": self.stats["sell_signals"],
                "NO_TRADE": self.stats["no_trade_signals"],
                "IGNORED": self.stats["ignored_signals"]
            },
            "trades": {
                "total": len(closed),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate_pct": round(win_rate, 2),
                "gross_r": round(gross_r, 2),
                "net_r": round(net_r, 2),
                "max_drawdown_r": round(self.portfolio.max_drawdown_r, 2)
            }
        }
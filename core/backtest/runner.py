"""
Backtest Runner — Orchestrates Dataset Replay, Pipeline Execution & Virtual Outcome.
"""
from datetime import datetime, timezone
from typing import List
from typing import List, Optional

from core.backtest.clock import SimulationClock
from core.backtest.dataset_validator import DatasetValidator
from core.backtest.domain import BacktestConfig, BacktestResult, VirtualTrade
from core.backtest.metrics import MetricsCalculator
from core.backtest.replay_engine import HistoricalReplayEngine
from core.backtest.virtual_outcome import VirtualOutcomeEngine
from core.features.domain.ohlcv_series import OHLCVSeries
from core.signal.domain import FinalSignal, FinalSignalDirection, NoTradeReason
from core.signal.signal_engine import SignalEngine


class BacktestRunner:
    def __init__(self, config: BacktestConfig, signal_engine: SignalEngine):
        self.config = config
        self.signal_engine = signal_engine
        self.clock = SimulationClock()

    def run(self, bars: List[OHLCVSeries], config: Optional[BacktestConfig] = None) -> BacktestResult:
        if config is not None:
            self.config = config

        valid, errors = DatasetValidator.validate(bars, self.config.symbol, self.config.timeframe)
        if not valid:
            raise ValueError(f"Invalid dataset: {', '.join(errors)}")

        replay = HistoricalReplayEngine(bars, self.clock)
        signals: List[FinalSignal] = []
        active_trades: List[VirtualTrade] = []
        completed_trades: List[VirtualTrade] = []

        bar_index = 0
        while replay.has_next():
            current_bar, history_slice = replay.next_step()
            
            # 1. Update active open trades with current bar (future data for past signals)
            updated_active = []
            for trade in active_trades:
                evaluated = VirtualOutcomeEngine.evaluate_trade(trade, current_bar, self.config.cost_model)
                if evaluated.is_open:
                    updated_active.append(evaluated)
                else:
                    completed_trades.append(evaluated)
            active_trades = updated_active

            # 2. Warm-up Period Check
            if len(history_slice) < self.config.warmup_bars:
                bar_index += 1
                continue

            # 3. Process ATIP Pipeline at T (strictly history_slice)
            #
            # SignalEngine.process(history, symbol, timeframe) renvoie un
            # dict {"signal": str, "regime": str, "score": float,
            # "risk_levels": {...}, "final_signal": FinalSignal}. Le reste
            # de cette boucle (VirtualOutcomeEngine, MetricsCalculator)
            # attend un objet FinalSignal, donc on extrait explicitement
            # result["final_signal"] plutôt que le dict brut.
            if self.signal_engine is not None:
                result = self.signal_engine.process(
                    history_slice,
                    symbol=self.config.symbol,
                    timeframe=self.config.timeframe,
                )
                signal = result["final_signal"]
            else:
                bar_ts = getattr(current_bar, "timestamp", datetime.now(timezone.utc))
                signal = FinalSignal(
                    signal_id=f"SIG-{bar_index}",
                    symbol=self.config.symbol,
                    asset_class="FX",
                    timeframe=self.config.timeframe,
                    timestamp=bar_ts,
                    direction=FinalSignalDirection.NO_TRADE,
                    no_trade_reason=NoTradeReason.NONE,
                    strategy="BASELINE",
                    market_regime="RANGING",
                    opportunity_status="N/A",
                    opportunity_score=0.0,
                    risk_status="N/A",
                    risk_score=0.0,
                    data_quality_status="VALID",
                    reasons=["Baseline replay run"],
                    evidence={},
                )
            signals.append(signal)

            # 4. If Signal émis, planifier l'entrée virtuelle à la bougie T+1
            if signal.direction in (FinalSignalDirection.BUY, FinalSignalDirection.SELL):
                # Simulated entry on current bar close or next open
                trade = VirtualOutcomeEngine.create_trade_from_signal(signal, current_bar.close, self.config.cost_model)
                if trade:
                    active_trades.append(trade)

            bar_index += 1

        all_trades = completed_trades + active_trades
        metrics = MetricsCalculator.calculate(signals, all_trades, self.config.warmup_bars)

        first_bar = bars.iloc[0] if hasattr(bars, "iloc") else bars[0]
        last_bar = bars.iloc[-1] if hasattr(bars, "iloc") else bars[-1]

        start_ts = getattr(first_bar, "timestamp", None)
        if start_ts is None and hasattr(first_bar, "__getitem__"):
            start_ts = first_bar["timestamp"]
            
        end_ts = getattr(last_bar, "timestamp", None)
        if end_ts is None and hasattr(last_bar, "__getitem__"):
            end_ts = last_bar["timestamp"]

        return BacktestResult(
            run_id=f"BT-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            config=self.config,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            signals=signals,
            trades=all_trades,
            metrics=metrics,
            warnings=errors,
        )
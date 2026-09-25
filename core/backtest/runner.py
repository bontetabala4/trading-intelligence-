"""
Backtest Runner — Orchestrates Dataset Replay, Pipeline Execution & Virtual Outcome.
"""
from datetime import datetime, timezone
from typing import List

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
   Changes to be committed:
  (use "git rm --cached <file>..." to unstage)
        new file:   .env.example
        new file:   .gitignore
        new file:   README.md
        new file:   alembic.ini
        new file:   apps/__init__.py
        new file:   apps/api/__init__.py
        new file:   apps/api/dependencies.py
        new file:   apps/api/main.py
        new file:   apps/api/routers/__init__.py
        new file:   apps/api/routers/data_pipeline.py
        new file:   apps/api/routers/execution.py
        new file:   apps/api/routers/features.py
        new file:   apps/api/routers/health.py
        new file:   apps/api/routers/market_data.py
        new file:   apps/api/routers/markets.py
        new file:   apps/api/routers/mt5.py
        new file:   apps/api/routers/regime.py
        new file:   apps/api/routers/risk.py
        new file:   apps/api/routers/signals.py
        new file:   apps/api/schemas/__init__.py
        new file:   apps/api/schemas/responses.py
        new file:   brokers/__init__.py
        new file:   brokers/base/__init__.py
        new file:   brokers/base/interface.py
        new file:   brokers/mt5/__init__.py
        new file:   brokers/mt5/adapter.py
        new file:   brokers/mt5/mock_adapter.py
        new file:   configs/__init__.py
        new file:   configs/markets.py
        new file:   configs/settings.py
        new file:   core/__init__.py
        new file:   core/backtest/audit_tool.py
        new file:   core/backtest/clock.py
        new file:   core/backtest/data_quality.py
        new file:   core/backtest/dataset_validator.py
        new file:   core/backtest/domain.py
        new file:   core/backtest/metrics.py
        new file:   core/backtest/replay_engine.py
        new file:   core/backtest/runner.py
        new file:   core/backtest/step10_evaluation.py
        new file:   core/backtest/virtual_outcome.py
        new file:   core/data/__init__.py
        new file:   core/data/collector.py
        new file:   core/data/normalizer.py
        new file:   core/data/quality_engine.py
        new file:   core/data/validator.py
        new file:   core/execution/__init__.py
        new file:   core/execution/domain/enums.py
        new file:   core/execution/domain/models.py
        new file:   core/execution/services/engine.py
        new file:   core/execution/services/mt5_executor.py
        new file:   core/features/__init__.py
        new file:   core/features/calculators/__init__.py
        new file:   core/features/calculators/base.py
        new file:   core/features/calculators/momentum.py
        new file:   core/features/calculators/price.py
        new file:   core/features/calculators/trend.py
        new file:   core/features/calculators/volatility.py
        new file:   core/features/calculators/volume.py
        new file:   core/features/calculators/vwap.py
        new file:   core/features/domain/__init__.py
        new file:   core/features/domain/ohlcv_series.py
        new file:   core/features/models.py
        new file:   core/features/registry/__init__.py
        new file:   core/features/registry/registry.py
        new file:   core/features/services/__init__.py
        new file:   core/features/services/context_builder.py
        new file:   core/features/services/feature_engine.py
        new file:   core/market/__init__.py
        new file:   core/market/calendar.py
        new file:   core/market/observer.py
        new file:   core/market/selection.py
        new file:   core/market/snapshot.py
        new file:   core/notification/service.py
        new file:   core/opportunity/__init__.py
        new file:   core/opportunity/detector.py
        new file:   core/opportunity/models.py
        new file:   core/opportunity/quantifier.py
        new file:   core/opportunity/validator.py
        new file:   core/regime/__init__.py
        new file:   core/regime/domain/enums.py
        new file:   core/regime/domain/models.py
        new file:   core/regime/services/engine.py
        new file:   core/risk/__init__.py
        new file:   core/risk/domain/enums.py
        new file:   core/risk/domain/models.py
        new file:   core/risk/services/engine.py
        new file:   core/risk/services/limits.py
        new file:   core/risk/services/sizer.py
        new file:   core/signal/__init__.py
        new file:   core/signal/domain.py
        new file:   core/signal/signal_engine.py
        new file:   core/strategy/__init__.py
        new file:   core/strategy/domain/enums.py
        new file:   core/strategy/domain/models.py
        new file:   core/strategy/services/StrategyEngine.py
        new file:   core/strategy/services/__init__.py
        new file:   core/strategy/services/engine.py
        new file:   core/strategy/strategies/base.py
        new file:   core/strategy/strategies/mean_reversion.py
        new file:   core/strategy/strategies/trend_following.py
        new file:   database/__init__.py
        new file:   database/migrations/env.py
        new file:   database/migrations/versions/0001_initial_schema.py
        new file:   database/migrations/versions/0002_etape2_data_pipeline.py
        new file:   database/models.py
        new file:   database/repositories/__init__.py
        new file:   database/repositories/asset_repository.py
        new file:   database/repositories/market_data_repository.py
        new file:   database/session.py
        new file:   docker-compose.yml
        new file:   docker/Dockerfile
        new file:   docs/architecture.md
        new file:   docs/data-pipeline.md
        new file:   docs/features.md
        new file:   docs/step8_signal_notification.md
        new file:   requirements/base.txt
        new file:   requirements/dev.txt
        new file:   scripts/validate_setup.py
        new file:   tests/__init__.py
        new file:   tests/conftest.py
        new file:   tests/test_execution_engine.py
        new file:   tests/test_regime_lookahead.py
        new file:   tests/test_risk_engine.py
        new file:   tests/test_signal_engine.py
        new file:   tests/test_step8_final_signal_notification.py
        new file:   tests/unit/__init__.py
        new file:   tests/unit/test_collector.py
        new file:   tests/unit/test_data_quality.py
        new file:   tests/unit/test_feature_engine.py
        new file:   tests/unit/test_market_observer.py
        new file:   tests/unit/test_market_selection.py
        new file:   tests/unit/test_mt5_adapter.py
        new file:   tests/unit/test_no_lookahead.py
        new file:   tests/unit/test_normalizer.py
        new file:   tests/unit/test_opportunity_engine.py
        new file:   tests/unit/test_price_features.py
        new file:   tests/unit/test_step10_1_audit.py
        new file:   tests/unit/test_step10_historical_validation.py
        new file:   tests/unit/test_trend_features.py
        new file:   tests/unit/test_validator.py
        new file:   tests/unit/test_volatility_momentum_features.py
        new file:   tests/unit/test_volume_vwap_features.py

(.venv)
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
            if self.signal_engine is not None and hasattr(self.signal_engine, "process_bar"):
                signal = self.signal_engine.process_bar(
                    current_bar=current_bar,
                    history=history_slice,
                    symbol=self.config.symbol,
                    timeframe=self.config.timeframe,
                )
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
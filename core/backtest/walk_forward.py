"""
Walk-Forward Validation Engine for Quantitative Strategies and Risk Models.

Executes rolling or anchored out-of-sample evaluations across sequential historical windows
to measure out-of-sample degradation, parameter stability, and walk-forward efficiency (WFE).
Strictly prevents lookahead bias and parameter leakage across window boundaries.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional
import pandas as pd

from core.backtest.domain import BacktestConfig, BacktestResult
from core.backtest.runner import BacktestRunner
from core.signal.signal_engine import SignalEngine


@dataclass
class WalkForwardConfig:
    train_bars: int = 500
    test_bars: int = 200
    step_bars: Optional[int] = None  # Defaults to test_bars (non-overlapping OOS)
    anchored: bool = False          # False = rolling, True = expanding train window
    min_windows: int = 1


@dataclass
class WalkForwardWindow:
    window_index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_bars: int
    test_bars: int
    is_result: BacktestResult
    oos_result: BacktestResult
    efficiency_ratio: float  # OOS net_r / max(IS net_r, 0.001)


@dataclass
class WalkForwardReport:
    symbol: str
    timeframe: str
    dataset_hash: str
    total_bars: int
    total_windows: int
    anchored: bool
    windows: List[WalkForwardWindow]
    mean_is_net_r: float
    mean_oos_net_r: float
    total_oos_net_r: float
    total_oos_trades: int
    oos_win_rate_pct: float
    oos_profit_factor: float
    oos_max_drawdown_r: float
    walk_forward_efficiency: float
    consistency_pct: float
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "dataset_hash": self.dataset_hash,
            "total_bars": self.total_bars,
            "total_windows": self.total_windows,
            "anchored": self.anchored,
            "mean_is_net_r": round(self.mean_is_net_r, 4),
            "mean_oos_net_r": round(self.mean_oos_net_r, 4),
            "total_oos_net_r": round(self.total_oos_net_r, 4),
            "total_oos_trades": self.total_oos_trades,
            "oos_win_rate_pct": round(self.oos_win_rate_pct, 2),
            "oos_profit_factor": round(self.oos_profit_factor, 2),
            "oos_max_drawdown_r": round(self.oos_max_drawdown_r, 4),
            "walk_forward_efficiency": round(self.walk_forward_efficiency, 4),
            "consistency_pct": round(self.consistency_pct, 2),
            "generated_at": self.generated_at.isoformat(),
            "windows": [
                {
                    "window_index": w.window_index,
                    "train_start": w.train_start.isoformat(),
                    "train_end": w.train_end.isoformat(),
                    "test_start": w.test_start.isoformat(),
                    "test_end": w.test_end.isoformat(),
                    "train_bars": w.train_bars,
                    "test_bars": w.test_bars,
                    "is_net_r": round(w.is_result.metrics.net_result_r, 4),
                    "is_trades": w.is_result.metrics.total_virtual_trades,
                    "oos_net_r": round(w.oos_result.metrics.net_result_r, 4),
                    "oos_trades": w.oos_result.metrics.total_virtual_trades,
                    "efficiency_ratio": round(w.efficiency_ratio, 4),
                }
                for w in self.windows
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Walk-Forward Validation Report: {self.symbol} ({self.timeframe})",
            f"- **Generated At:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"- **Dataset SHA256:** `{self.dataset_hash}`",
            f"- **Total Bars:** {self.total_bars} | **Windows:** {self.total_windows} ({'Expanding' if self.anchored else 'Rolling'})",
            f"- **Walk-Forward Efficiency (WFE):** {self.walk_forward_efficiency:.2%}",
            f"- **Consistency (Positive OOS Windows):** {self.consistency_pct:.1f}%",
            f"- **Total OOS Net R:** {self.total_oos_net_r:+.2f} R across {self.total_oos_trades} trades",
            f"- **OOS Win Rate:** {self.oos_win_rate_pct:.1f}% | **OOS Profit Factor:** {self.oos_profit_factor:.2f}",
            "",
            "## Window Breakdown",
            "| Window | In-Sample Period | IS Net R | Out-Of-Sample Period | OOS Trades | OOS Net R | WFE |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for w in self.windows:
            lines.append(
                f"| {w.window_index + 1} | "
                f"{w.train_start.strftime('%m/%d')} - {w.train_end.strftime('%m/%d')} | "
                f"{w.is_result.metrics.net_result_r:+.2f} R | "
                f"{w.test_start.strftime('%m/%d')} - {w.test_end.strftime('%m/%d')} | "
                f"{w.oos_result.metrics.total_virtual_trades} | "
                f"{w.oos_result.metrics.net_result_r:+.2f} R | "
                f"{w.efficiency_ratio:.2f} |"
            )
        return "\n".join(lines)


class WalkForwardEngine:
    """
    Executes walk-forward cross-validation on historical OHLCV data.
    """

    def __init__(self, signal_engine: SignalEngine):
        self.signal_engine = signal_engine

    @staticmethod
    def compute_dataset_hash(dataset: pd.DataFrame) -> str:
        """Computes deterministic SHA256 digest of historical bars."""
        cols = [c for c in ["timestamp", "time", "open", "high", "low", "close", "volume", "tick_volume"] if c in dataset.columns]
        if not cols:
            cols = list(dataset.columns)
        serialized = dataset[cols].to_csv(index=False).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def run(
        self,
        dataset: pd.DataFrame,
        base_config: BacktestConfig,
        wf_config: WalkForwardConfig,
    ) -> WalkForwardReport:
        """
        Executes rolling or anchored walk-forward validation across sequential segments.
        """
        if "timestamp" not in dataset.columns:
            raise ValueError("Walk-forward requires a timezone-aware 'timestamp' column.")
        if dataset["timestamp"].isna().any():
            raise ValueError("Walk-forward does not accept missing timestamps.")
        if wf_config.train_bars <= 0 or wf_config.test_bars <= 0:
            raise ValueError("train_bars and test_bars must be positive.")
        if wf_config.min_windows <= 0:
            raise ValueError("min_windows must be positive.")

        dataset_sorted = dataset.sort_values("timestamp").reset_index(drop=True)
        if dataset_sorted["timestamp"].duplicated().any():
            raise ValueError("Walk-forward does not accept duplicate timestamps.")

        total_bars = len(dataset_sorted)
        step = wf_config.step_bars if wf_config.step_bars is not None else wf_config.test_bars
        if step <= 0:
            raise ValueError("step_bars must be positive when provided.")

        min_required = wf_config.train_bars + wf_config.test_bars
        if total_bars < min_required:
            raise ValueError(
                f"Dataset length ({total_bars}) is insufficient for Walk-Forward with "
                f"train_bars={wf_config.train_bars} and test_bars={wf_config.test_bars} (min: {min_required})."
            )

        dataset_hash = self.compute_dataset_hash(dataset_sorted)
        windows: List[WalkForwardWindow] = []

        start_train_idx = 0
        window_idx = 0

        while True:
            end_train_idx = start_train_idx + wf_config.train_bars if not wf_config.anchored else wf_config.train_bars + (window_idx * step)
            start_test_idx = end_train_idx
            end_test_idx = start_test_idx + wf_config.test_bars

            if end_test_idx > total_bars:
                break

            train_df = dataset_sorted.iloc[0 if wf_config.anchored else start_train_idx : end_train_idx].copy().reset_index(drop=True)
            test_df = dataset_sorted.iloc[start_test_idx : end_test_idx].copy().reset_index(drop=True)

            # In-Sample Runner
            is_runner = BacktestRunner(base_config, self.signal_engine)
            is_result = is_runner.run(train_df)

            # Out-Of-Sample Runner: Warmup bars are prepended from train_df if needed to seed indicators
            warmup = min(base_config.warmup_bars, len(train_df))
            if warmup > 0:
                warmup_tail = train_df.iloc[-warmup:].copy()
                oos_combined = pd.concat([warmup_tail, test_df], ignore_index=True)
            else:
                oos_combined = test_df

            oos_runner = BacktestRunner(base_config, self.signal_engine)
            full_oos_result = oos_runner.run(oos_combined)

            # Filter out warmup trades/signals: only keep those evaluated during actual OOS interval
            test_start_ts = test_df["timestamp"].iloc[0] if "timestamp" in test_df.columns else None
            if test_start_ts is not None:
                oos_signals = [s for s in full_oos_result.signals if s.timestamp >= test_start_ts]
                oos_trades = [t for t in full_oos_result.trades if t.entry_timestamp >= test_start_ts]
            else:
                oos_signals = full_oos_result.signals
                oos_trades = full_oos_result.trades

            from core.backtest.metrics import MetricsCalculator
            oos_metrics = MetricsCalculator.calculate(oos_signals, oos_trades, warmup_bars=0)

            oos_result = BacktestResult(
                run_id=f"oos_{window_idx}",
                config=base_config,
                start_timestamp=full_oos_result.start_timestamp,
                end_timestamp=full_oos_result.end_timestamp,
                signals=oos_signals,
                trades=oos_trades,
                metrics=oos_metrics,
                warnings=full_oos_result.warnings,
            )

            is_net = is_result.metrics.net_result_r
            oos_net = oos_result.metrics.net_result_r
            efficiency = (oos_net / is_net) if abs(is_net) > 0.001 else (1.0 if oos_net >= 0 else 0.0)

            t_start = train_df["timestamp"].iloc[0] if "timestamp" in train_df.columns else datetime.utcnow()
            t_end = train_df["timestamp"].iloc[-1] if "timestamp" in train_df.columns else datetime.utcnow()
            oos_start = test_df["timestamp"].iloc[0] if "timestamp" in test_df.columns else datetime.utcnow()
            oos_end = test_df["timestamp"].iloc[-1] if "timestamp" in test_df.columns else datetime.utcnow()

            windows.append(
                WalkForwardWindow(
                    window_index=window_idx,
                    train_start=t_start,
                    train_end=t_end,
                    test_start=oos_start,
                    test_end=oos_end,
                    train_bars=len(train_df),
                    test_bars=len(test_df),
                    is_result=is_result,
                    oos_result=oos_result,
                    efficiency_ratio=efficiency,
                )
            )

            window_idx += 1
            if wf_config.anchored:
                # In anchored, train window expands by step
                pass
            else:
                start_train_idx += step

        if len(windows) < wf_config.min_windows:
            raise ValueError(
                f"Generated {len(windows)} windows, fewer than required min_windows ({wf_config.min_windows})."
            )

        # Aggregate Metrics across OOS windows
        total_oos_net = sum(w.oos_result.metrics.net_result_r for w in windows)
        all_oos_closed_trades = [t for w in windows for t in w.oos_result.trades if not t.is_open]
        total_oos_trades = len(all_oos_closed_trades)
        wins = [t for t in all_oos_closed_trades if (t.net_result_r or 0) > 0]
        losses = [t for t in all_oos_closed_trades if (t.net_result_r or 0) <= 0]
        tot_gain = sum(t.net_result_r or 0.0 for t in wins)
        tot_loss = abs(sum(t.net_result_r or 0.0 for t in losses))

        win_rate = (len(wins) / total_oos_trades * 100.0) if total_oos_trades > 0 else 0.0
        profit_factor = (tot_gain / tot_loss) if tot_loss > 0 else (tot_gain if tot_gain > 0 else 0.0)

        # Drawdown across concatenated OOS trades
        peak = 0.0
        cum_r = 0.0
        max_dd = 0.0
        for t in all_oos_closed_trades:
            cum_r += (t.net_result_r or 0.0)
            if cum_r > peak:
                peak = cum_r
            dd = peak - cum_r
            if dd > max_dd:
                max_dd = dd

        mean_is_net = sum(w.is_result.metrics.net_result_r for w in windows) / len(windows)
        mean_oos_net = total_oos_net / len(windows)
        wfe = (mean_oos_net / mean_is_net) if abs(mean_is_net) > 0.001 else 0.0
        positive_windows = sum(1 for w in windows if w.oos_result.metrics.net_result_r > 0)
        consistency = (positive_windows / len(windows) * 100.0) if windows else 0.0

        return WalkForwardReport(
            symbol=base_config.symbol,
            timeframe=base_config.timeframe,
            dataset_hash=dataset_hash,
            total_bars=total_bars,
            total_windows=len(windows),
            anchored=wf_config.anchored,
            windows=windows,
            mean_is_net_r=mean_is_net,
            mean_oos_net_r=mean_oos_net,
            total_oos_net_r=total_oos_net,
            total_oos_trades=total_oos_trades,
            oos_win_rate_pct=win_rate,
            oos_profit_factor=profit_factor,
            oos_max_drawdown_r=max_dd,
            walk_forward_efficiency=wfe,
            consistency_pct=consistency,
        )

"""
Step 10 Evaluation Engine: Handles Protocol Isolation, In-Sample/Out-Of-Sample Splitting,
Sensitivity Analysis, and Comprehensive Report Construction.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

from core.backtest.data_quality import DatasetMetadata, QualityMetrics, DataQualityReport
# FIX : le module s'appelle core.backtest.runner partout ailleurs dans le projet
# (tests, runner.py lui-même) — core.backtest_runner n'existe pas.
from core.backtest.runner import BacktestRunner, BacktestConfig
from core.signal.signal_engine import SignalEngine


class Step10Evaluator:
    """
    Executes methodical historical backtesting over validated datasets.
    Strictly forbids parameter tuning or rule modifications post-evaluation.
    """

    def __init__(self, signal_engine: SignalEngine):
        # FIX : on ne garde plus un BacktestRunner figé sur UN SEUL config.
        # BacktestRunner attend (config, signal_engine) à la construction, et
        # in-sample / out-of-sample / chaque scénario de coût ont chacun leur
        # propre config — donc on garde le signal_engine ici, et on construit
        # un BacktestRunner neuf pour chaque config utilisée plus bas.
        self.signal_engine = signal_engine

    def run_protocol_evaluation(
        self,
        dataset: pd.DataFrame,
        metadata: DatasetMetadata,
        quality_metrics: QualityMetrics,
        in_sample_end: datetime,
        warmup_bars: int = 200,
        cost_scenarios: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        if metadata.is_synthetic:
            raise ValueError("Step 10 requires REAL historical data. Synthetic fixtures are rejected.")

        if quality_metrics.quality_status == "INVALID":
            raise ValueError(f"Cannot run evaluation on INVALID dataset: {quality_metrics.issues}")

        cost_scenarios = cost_scenarios or {
            "ZERO_COST": 0.0,
            "LOW_COST": 0.00005,
            "BASE_COST": 0.00010,
            "HIGH_COST": 0.00025,
        }

        # Protocol Splitting
        dataset_sorted = dataset.sort_values("timestamp").reset_index(drop=True)
        in_sample_df = dataset_sorted[dataset_sorted["timestamp"] <= in_sample_end]
        out_of_sample_df = dataset_sorted[dataset_sorted["timestamp"] > in_sample_end]

        results = {
            "metadata": metadata,
            "quality_report": DataQualityReport(metadata, quality_metrics).generate_report_string(),
            "in_sample_results": {},
            "out_of_sample_results": {},
            "cost_sensitivity": {},
        }

        # Run In-Sample Evaluation
        # FIX : BacktestRunner(config, signal_engine) construit un runner lié à CE
        # config précis, puis .run(bars) ne prend plus qu'un seul argument —
        # cohérent avec la signature réelle de core/backtest/runner.py.
        is_config = BacktestConfig(warmup_bars=warmup_bars, cost_per_trade=cost_scenarios["BASE_COST"])
        results["in_sample_results"] = BacktestRunner(is_config, self.signal_engine).run(in_sample_df)

        # Run Out-Of-Sample Evaluation (if data available)
        if len(out_of_sample_df) > warmup_bars:
            oos_config = BacktestConfig(warmup_bars=warmup_bars, cost_per_trade=cost_scenarios["BASE_COST"])
            results["out_of_sample_results"] = BacktestRunner(oos_config, self.signal_engine).run(out_of_sample_df)

        # Run Cost Sensitivity Scenarios on In-Sample
        for scenario_name, cost_val in cost_scenarios.items():
            scenario_config = BacktestConfig(warmup_bars=warmup_bars, cost_per_trade=cost_val)
            scenario_run = BacktestRunner(scenario_config, self.signal_engine).run(in_sample_df)
            results["cost_sensitivity"][scenario_name] = {
                "gross_r": scenario_run.metrics.gross_r,
                "net_r": scenario_run.metrics.net_r,
                "profit_factor": scenario_run.metrics.profit_factor,
                "max_drawdown": scenario_run.metrics.max_drawdown,
            }

        return results
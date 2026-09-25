"""
ATIP Step 10.1 - Independent Backtest Audit & Metrics Recalculation Engine.
Strictly decoupled from trading logic. Used only for verification and audit.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd


@dataclass
class DatasetIdentity:
    dataset_id: str
    file_path: str
    file_size_bytes: int
    sha256_hash: str
    total_rows: int
    valid_bars: int
    first_timestamp: datetime
    last_timestamp: datetime
    timezone: str


@dataclass
class ReconciliationRow:
    metric: str
    reported: str
    recalculated: str
    status: str  # MATCH, ROUNDING DIFFERENCE, METHODOLOGY DIFFERENCE, IMPLEMENTATION BUG, REPORTING ERROR


class Step10AuditEngine:
    """Independent Audit Tooling for ATIP Step 10 Validation."""

    @staticmethod
    def compute_dataset_hash(file_path: str) -> DatasetIdentity:
        """Calculates deterministic SHA-256 hash and metadata of the dataset."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        
        df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_parquet(file_path)
        
        # Ensure timestamp sorting
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)

        return DatasetIdentity(
            dataset_id="EURUSD_M15_2022_2025_REAL",
            file_path=file_path,
            file_size_bytes=df.memory_usage(deep=True).sum(),
            sha256_hash=hasher.hexdigest(),
            total_rows=len(df),
            valid_bars=len(df.dropna()),
            first_timestamp=df['timestamp'].iloc[0],
            last_timestamp=df['timestamp'].iloc[-1],
            timezone=str(df['timestamp'].dt.tz)
        )

    @staticmethod
    def verify_profit_factor(trades_df: pd.DataFrame) -> Tuple[float, float, float]:
        """Recalculates Profit Factor strictly as Gross Winning R / Absolute Gross Losing R."""
        winning_r = trades_df[trades_df['net_r'] > 0]['net_r'].sum()
        losing_r = np.abs(trades_df[trades_df['net_r'] < 0]['net_r'].sum())
        
        pf = winning_r / losing_r if losing_r > 0 else np.nan
        return float(winning_r), float(losing_r), float(pf)

    @staticmethod
    def audit_loss_regime_distribution(trades_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Audits the claim regarding loss distribution across regimes.
        Differentiates between count of losing trades vs percentage of gross loss R.
        """
        losing_trades = trades_df[trades_df['net_r'] < 0]
        total_gross_loss_r = np.abs(losing_trades['net_r'].sum())
        total_loss_count = len(losing_trades)

        regime_breakdown = {}
        for regime, group in losing_trades.groupby('regime'):
            regime_loss_r = np.abs(group['net_r'].sum())
            regime_loss_count = len(group)
            regime_breakdown[regime] = {
                'loss_count': regime_loss_count,
                'loss_count_pct': (regime_loss_count / total_loss_count) * 100.0 if total_loss_count > 0 else 0.0,
                'loss_r': regime_loss_r,
                'loss_r_pct': (regime_loss_r / total_gross_loss_r) * 100.0 if total_gross_loss_r > 0 else 0.0,
            }

        return {
            'total_gross_loss_r': total_gross_loss_r,
            'total_loss_count': total_loss_count,
            'regimes': regime_breakdown
        }

    @staticmethod
    def recalculate_max_drawdown(trades_df: pd.DataFrame) -> Tuple[float, Optional[float]]:
        """Recalculates maximum drawdown in R and checks percentage conversion validity."""
        equity_curve = trades_df['net_r'].cumsum()
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = equity_curve - running_max
        max_dd_r = float(drawdown.min()) if len(drawdown) > 0 else 0.0
        
        # Drawdown % cannot be verified without capital/position sizing assumptions
        return max_dd_r, None
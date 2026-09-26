"""
Step 11 Test Suite.
Validates temporal streaming, no-lookahead via future data mutation,
reproducibility across runs, and absolute MT5 execution isolation.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from core.paper_trading.engine import ForwardPaperEngine


class TestStep11ForwardPaperTrading(unittest.TestCase):
    def setUp(self):
        # Generate 100 synthetic M15 bars
        timestamps = [datetime(2025, 1, 1) + timedelta(minutes=15 * i) for i in range(100)]
        np.random.seed(42)
        close_prices = 1.0800 + np.cumsum(np.random.randn(100) * 0.0005)
        
        self.df = pd.DataFrame({
            "open": close_prices - 0.0001,
            "high": close_prices + 0.0003,
            "low": close_prices - 0.0003,
            "close": close_prices,
            "volume": 100
        }, index=pd.DatetimeIndex(timestamps))

    def test_reproducibility_run_a_vs_run_b(self):
        """Validates that Run A and Run B yield identical metrics on identical data."""
        engine_a = ForwardPaperEngine(self.df, run_id="run_a")
        res_a = engine_a.run()

        engine_b = ForwardPaperEngine(self.df, run_id="run_b")
        res_b = engine_b.run()

        self.assertEqual(res_a, res_b)

    def test_no_lookahead_mutation(self):
        """Mutates future data past T=50 and asserts signal at T=50 remains unchanged."""
        engine = ForwardPaperEngine(self.df, run_id="test_lookahead")
        
        # Run up to bar 50
        engine.run(max_bars=50)
        signal_at_50 = engine.ledger.events[-1].details["signal"]

        # Mutate future bars (from index 51 to 99)
        df_mutated = self.df.copy()
        df_mutated.iloc[51:, df_mutated.columns.get_loc("close")] *= 2.0

        engine_mutated = ForwardPaperEngine(df_mutated, run_id="test_lookahead_mutated")
        engine_mutated.run(max_bars=50)
        signal_at_50_mutated = engine_mutated.ledger.events[-1].details["signal"]

        self.assertEqual(signal_at_50, signal_at_50_mutated)

    def test_no_mt5_order_send(self):
        """Ensures mt5.order_send is never imported or called."""
        import sys
        self.assertNotIn("MetaTrader5", sys.modules)


if __name__ == "__main__":
    unittest.main()
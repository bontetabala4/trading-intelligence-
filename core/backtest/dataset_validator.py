from typing import Any, List, Tuple
import pandas as pd

class DatasetValidator:

    @staticmethod
    def validate(bars: Any, expected_symbol: str, expected_timeframe: str) -> Tuple[bool, List[str]]:
        errors = []
        if bars is None:
            return False, ["Dataset is None."]

        if isinstance(bars, pd.DataFrame):
            if bars.empty:
                return False, ["Dataset is empty."]
            
            required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
            missing = required_cols - set(bars.columns)
            if missing:
                errors.append(f"Missing required columns: {missing}")
                return False, errors

            invalid_ohlc = bars[
                (bars['high'] < bars['low']) | 
                (bars['open'] > bars['high']) | 
                (bars['open'] < bars['low']) | 
                (bars['close'] > bars['high']) | 
                (bars['close'] < bars['low'])
            ]
            if not invalid_ohlc.empty:
                errors.append(f"OHLC violation found in {len(invalid_ohlc)} rows.")

            return len(errors) == 0, errors

        if len(bars) == 0:
            return False, ["Dataset is empty."]

        for i, bar in enumerate(bars):
            if getattr(bar, "symbol", expected_symbol) != expected_symbol:
                errors.append(f"Row {i}: Invalid symbol")
            if hasattr(bar, "high") and hasattr(bar, "low") and bar.high < bar.low:
                errors.append(f"Row {i}: High < Low violation")

        return len(errors) == 0, errors
"""
Market Data Stream Module for Paper Trading.
Provides a strictly sequential stream of market bars up to current time T.
Ensures no future data (T+1 ...) is accessible to strategy engines.
"""

import pandas as pd
from typing import Optional, Dict, Any
from core.paper_trading.clock import ForwardClock


class MarketDataStream:
    def __init__(self, data: pd.DataFrame, clock: ForwardClock):
        self._df = data.copy()
        if not isinstance(self._df.index, pd.DatetimeIndex):
            if 'time' in self._df.columns:
                self._df['time'] = pd.to_datetime(self._df['time'])
                self._df.set_index('time', inplace=True)
            elif 'timestamp' in self._df.columns:
                self._df['timestamp'] = pd.to_datetime(self._df['timestamp'])
                self._df.set_index('timestamp', inplace=True)
            else:
                self._df.index = pd.to_datetime(self._df.index)
        
        self._df.sort_index(inplace=True)
        self.clock = clock
        self._cursor = -1
        self._total_bars = len(self._df)

    @property
    def total_bars(self) -> int:
        return self._total_bars

    def has_next(self) -> bool:
        return (self._cursor + 1) < self._total_bars

    def next_bar(self) -> Dict[str, Any]:
        """Advance cursor by 1 and return current bar as dict."""
        if not self.has_next():
            raise StopIteration("End of market data stream reached.")
        self._cursor += 1
        current_time = self._df.index[self._cursor]
        self.clock.tick(current_time, self._cursor)
        
        row = self._df.iloc[self._cursor]
        bar = {
            'timestamp': current_time,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('volume', 0)),
            'bar_index': self._cursor
        }
        return bar

    def get_history_up_to_current(self) -> pd.DataFrame:
        """Strictly returns history from index 0 up to current_cursor."""
        if self._cursor < 0:
            return pd.DataFrame()
        return self._df.iloc[: self._cursor + 1].copy()

    def set_cursor(self, cursor: int) -> None:
        """Allow setting cursor for resume capability."""
        if 0 <= cursor < self._total_bars:
            self._cursor = cursor
            current_time = self._df.index[self._cursor]
            self.clock.tick(current_time, self._cursor)
        elif cursor == -1:
            self._cursor = -1
            self.clock.reset()
        else:
            raise ValueError(f"Invalid cursor index: {cursor}")
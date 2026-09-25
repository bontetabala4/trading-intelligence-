"""
Simulation Clock for ATIP Backtesting Engine.
Prevents dependency on system real time during replay.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """Returns current clock time."""
        pass


class RealTimeClock(Clock):
    """Real-time clock for live deployment."""
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class SimulationClock(Clock):
    """Simulation clock for historical replay."""
    def __init__(self, initial_time: datetime | None = None):
        self._current_time = initial_time or datetime(1970, 1, 1, tzinfo=timezone.utc)

    def set_time(self, current_time: datetime) -> None:
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        self._current_time = current_time

    def now(self) -> datetime:
        return self._current_time
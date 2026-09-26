"""
Paper Trading Ledger & Event Audit Log.
Tracks structured events (BAR_RECEIVED, SIGNAL_GENERATED, PAPER_POSITION_OPENED, etc.)
and supports checkpointing for run state saving and resuming.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class PaperEvent:
    event_id: int
    event_type: str
    timestamp: str
    bar_index: int
    details: Dict[str, Any]


class PaperLedger:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: List[PaperEvent] = []
        self._event_counter = 0

    def log_event(self, event_type: str, timestamp: datetime, bar_index: int, details: Dict[str, Any]) -> None:
        self._event_counter += 1
        ts_str = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
        event = PaperEvent(
            event_id=self._event_counter,
            event_type=event_type,
            timestamp=ts_str,
            bar_index=bar_index,
            details=details
        )
        self.events.append(event)

    def export_json(self, filepath: str) -> None:
        data = {
            "run_id": self.run_id,
            "total_events": len(self.events),
            "events": [asdict(e) for e in self.events]
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def get_state_checkpoint(self, last_cursor: int) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "last_cursor": last_cursor,
            "event_counter": self._event_counter,
            "events": [asdict(e) for e in self.events]
        }
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.signal.domain import FinalSignal


class SignalLifecycleState(str, Enum):
    NEW_SIGNAL = "NEW_SIGNAL"
    ACTIVE = "ACTIVE"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class SignalLifecycle:
    signal_id: str
    state: SignalLifecycleState
    reason: Optional[str] = None

    @classmethod
    def from_signal(cls, signal: FinalSignal) -> "SignalLifecycle":
        if signal.direction.value == "NO_TRADE":
            return cls(
                signal_id=signal.signal_id,
                state=SignalLifecycleState.NO_TRADE,
                reason=signal.no_trade_reason.value,
            )

        return cls(
            signal_id=signal.signal_id,
            state=SignalLifecycleState.NEW_SIGNAL,
        )

    def activate(self) -> "SignalLifecycle":
        if self.state != SignalLifecycleState.NEW_SIGNAL:
            raise ValueError(
                f"Transition invalide: {self.state.value} -> ACTIVE"
            )

        return SignalLifecycle(
            signal_id=self.signal_id,
            state=SignalLifecycleState.ACTIVE,
        )

    def invalidate(self, reason: str) -> "SignalLifecycle":
        if self.state not in (
            SignalLifecycleState.NEW_SIGNAL,
            SignalLifecycleState.ACTIVE,
        ):
            raise ValueError(
                f"Transition invalide: {self.state.value} -> INVALIDATED"
            )

        if not reason.strip():
            raise ValueError("Une raison d'invalidation est obligatoire.")

        return SignalLifecycle(
            signal_id=self.signal_id,
            state=SignalLifecycleState.INVALIDATED,
            reason=reason,
        )

    def expire(self, reason: str = "Signal expiré.") -> "SignalLifecycle":
        if self.state not in (
            SignalLifecycleState.NEW_SIGNAL,
            SignalLifecycleState.ACTIVE,
        ):
            raise ValueError(
                f"Transition invalide: {self.state.value} -> EXPIRED"
            )

        return SignalLifecycle(
            signal_id=self.signal_id,
            state=SignalLifecycleState.EXPIRED,
            reason=reason,
        )
from __future__ import annotations

import math

from core.risk.domain.models import AccountState
from core.risk.domain.enums import RiskRejectReason


class RiskLimitsChecker:
    def __init__(
        self,
        max_daily_drawdown_pct: float = 0.05,
        max_open_positions: int = 3,
        max_spread_pips: float = 3.0,
        max_spread_to_stop_ratio: float = 0.10,
    ):
        self.max_daily_drawdown_pct = max_daily_drawdown_pct
        self.max_open_positions = max_open_positions
        self.max_spread_pips = max_spread_pips
        self.max_spread_to_stop_ratio = max_spread_to_stop_ratio

    def validate(
        self,
        account: AccountState,
        current_spread_pips: float | None,
        *,
        current_spread_price: float | None = None,
        stop_distance_price: float | None = None,
    ) -> RiskRejectReason:
        max_allowed_loss = account.balance * self.max_daily_drawdown_pct
        if account.daily_pnl < 0 and abs(account.daily_pnl) >= max_allowed_loss:
            return RiskRejectReason.MAX_DAILY_DRAWDOWN_REACHED

        if account.open_positions_count >= self.max_open_positions:
            return RiskRejectReason.MAX_OPEN_POSITIONS_REACHED

        if current_spread_pips is None and current_spread_price is None:
            return RiskRejectReason.MISSING_RISK_INPUTS

        if current_spread_pips is not None:
            if not math.isfinite(current_spread_pips) or current_spread_pips < 0:
                return RiskRejectReason.MISSING_RISK_INPUTS
            if current_spread_pips > self.max_spread_pips:
                return RiskRejectReason.SPREAD_TOO_HIGH

        # For non-FX instruments, compare price-denominated spread to stop
        # distance instead of incorrectly treating points as FX pips.
        if current_spread_price is not None:
            if (
                not math.isfinite(current_spread_price)
                or current_spread_price < 0
                or stop_distance_price is None
                or not math.isfinite(stop_distance_price)
                or stop_distance_price <= 0
            ):
                return RiskRejectReason.MISSING_RISK_INPUTS
            if current_spread_price / stop_distance_price > self.max_spread_to_stop_ratio:
                return RiskRejectReason.SPREAD_TOO_HIGH

        return RiskRejectReason.NONE

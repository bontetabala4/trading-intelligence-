from core.risk.domain.models import AccountState
from core.risk.domain.enums import RiskRejectReason

class RiskLimitsChecker:
    def __init__(self, max_daily_drawdown_pct: float = 0.05, max_open_positions: int = 3, max_spread_pips: float = 3.0):
        self.max_daily_drawdown_pct = max_daily_drawdown_pct
        self.max_open_positions = max_open_positions
        self.max_spread_pips = max_spread_pips

    def validate(self, account: AccountState, current_spread_pips: float) -> RiskRejectReason:
        # Check Daily Drawdown Limit
        max_allowed_loss = account.balance * self.max_daily_drawdown_pct
        if account.daily_pnl < 0 and abs(account.daily_pnl) >= max_allowed_loss:
            return RiskRejectReason.MAX_DAILY_DRAWDOWN_REACHED

        # Check Open Positions Count
        if account.open_positions_count >= self.max_open_positions:
            return RiskRejectReason.MAX_OPEN_POSITIONS_REACHED

        # Check Spread
        if current_spread_pips > self.max_spread_pips:
            return RiskRejectReason.SPREAD_TOO_HIGH

        return RiskRejectReason.NONE
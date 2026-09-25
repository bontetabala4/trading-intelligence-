import math

class PositionSizer:
    def __init__(self, risk_per_trade_pct: float = 0.01, min_lot: float = 0.01, max_lot: float = 10.0, lot_step: float = 0.01):
        self.risk_per_trade_pct = risk_per_trade_pct
        self.min_lot = min_lot
        self.max_lot = max_lot
        self.lot_step = lot_step

    def calculate_lot_size(self, balance: float, sl_pips: float, pip_value_per_lot: float = 10.0) -> float:
        if sl_pips <= 0 or balance <= 0:
            return 0.0

        risk_amount = balance * self.risk_per_trade_pct
        risk_per_pip = sl_pips * pip_value_per_lot
        raw_lots = risk_amount / risk_per_pip

        # Arrondi au pas inférieur (lot_step)
        steps = math.floor(raw_lots / self.lot_step)
        calculated_lots = round(steps * self.lot_step, 2)

        # Application des limites min/max
        if calculated_lots < self.min_lot:
            return 0.0
        return min(calculated_lots, self.max_lot)
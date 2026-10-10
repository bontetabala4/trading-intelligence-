import math

from brokers.base.interface import SymbolInfo


class PositionSizer:

    def __init__(
        self,
        risk_per_trade_pct: float = 0.01,
        min_lot: float = 0.01,
        max_lot: float = 10.0,
        lot_step: float = 0.01,
        risk_mode: str = "PERCENTAGE",
        fixed_risk_amount: float | None = None,
    ):
        normalized_mode = risk_mode.upper()

        if normalized_mode not in {"PERCENTAGE", "FIXED_AMOUNT"}:
            raise ValueError(
                "risk_mode doit être 'PERCENTAGE' ou 'FIXED_AMOUNT'."
            )

        if normalized_mode == "PERCENTAGE" and risk_per_trade_pct <= 0:
            raise ValueError(
                "risk_per_trade_pct doit être strictement positif."
            )

        if normalized_mode == "FIXED_AMOUNT":
            if fixed_risk_amount is None or fixed_risk_amount <= 0:
                raise ValueError(
                    "fixed_risk_amount doit être strictement positif "
                    "en mode FIXED_AMOUNT."
                )

        self.risk_mode = normalized_mode
        self.risk_per_trade_pct = risk_per_trade_pct
        self.fixed_risk_amount = fixed_risk_amount
        self.min_lot = min_lot
        self.max_lot = max_lot
        self.lot_step = lot_step

    def get_risk_amount(self, balance: float) -> float:
        if balance <= 0:
            return 0.0

        if self.risk_mode == "FIXED_AMOUNT":
            return float(self.fixed_risk_amount)

        return balance * self.risk_per_trade_pct

    def get_risk_percentage(self) -> float:
        if self.risk_mode == "FIXED_AMOUNT":
            return 0.0

        return self.risk_per_trade_pct * 100.0

    def calculate_lot_size(
        self,
        balance: float,
        sl_distance: float,
        symbol_info: SymbolInfo | None = None,
        pip_size: float = 0.0001,
        pip_value_per_lot: float = 10.0,
    ) -> float:

        if balance <= 0 or sl_distance <= 0:
            return 0.0

        risk_amount = self.get_risk_amount(balance)

        if risk_amount <= 0:
            return 0.0

        # ==============================================================
        # MODE MT5 : calcul basé sur les spécifications réelles du symbole
        # ==============================================================

        if symbol_info is not None:

            tick_size = symbol_info.trade_tick_size
            tick_value = symbol_info.trade_tick_value

            if (
                tick_size is None
                or tick_value is None
                or tick_size <= 0
                or tick_value <= 0
            ):
                return 0.0

            ticks = sl_distance / tick_size
            risk_per_lot = ticks * tick_value

            if risk_per_lot <= 0:
                return 0.0

            raw_lots = risk_amount / risk_per_lot

            min_lot = (
                symbol_info.volume_min
                if symbol_info.volume_min is not None
                else self.min_lot
            )

            max_lot = (
                symbol_info.volume_max
                if symbol_info.volume_max is not None
                else self.max_lot
            )

            lot_step = (
                symbol_info.volume_step
                if symbol_info.volume_step is not None
                and symbol_info.volume_step > 0
                else self.lot_step
            )

        # ==============================================================
        # MODE COMPATIBILITÉ
        # ==============================================================

        else:

            sl_pips = sl_distance / pip_size
            risk_per_pip = sl_pips * pip_value_per_lot

            if risk_per_pip <= 0:
                return 0.0

            raw_lots = risk_amount / risk_per_pip

            min_lot = self.min_lot
            max_lot = self.max_lot
            lot_step = self.lot_step

        # ==============================================================
        # ARRONDI AU PAS INFÉRIEUR
        # ==============================================================

        steps = math.floor(raw_lots / lot_step)

        calculated_lots = steps * lot_step

        # Évite les erreurs flottantes du type 0.30000000004
        calculated_lots = round(calculated_lots, 8)

        if calculated_lots < min_lot:
            return 0.0

        return min(calculated_lots, max_lot)

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

        try:
            risk_per_trade_pct = float(risk_per_trade_pct)
            min_lot = float(min_lot)
            max_lot = float(max_lot)
            lot_step = float(lot_step)
            if fixed_risk_amount is not None:
                fixed_risk_amount = float(fixed_risk_amount)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Les paramètres du PositionSizer doivent être numériques.") from exc

        if not all(math.isfinite(value) for value in (risk_per_trade_pct, min_lot, max_lot, lot_step)):
            raise ValueError("Les paramètres du PositionSizer doivent être finis.")
        if min_lot <= 0 or max_lot <= 0 or lot_step <= 0 or min_lot > max_lot:
            raise ValueError("Les limites de lots et lot_step doivent être positives et cohérentes.")
        if normalized_mode == "FIXED_AMOUNT" and (
            fixed_risk_amount is None
            or not math.isfinite(fixed_risk_amount)
            or fixed_risk_amount <= 0
        ):
            raise ValueError("fixed_risk_amount doit être strictement positif et fini en mode FIXED_AMOUNT.")

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
        """Calculate a risk-bounded volume, rounded DOWN to a valid lot step.

        When broker symbol information is supplied, every sizing field must be
        present and finite. The legacy pip-based fallback is retained only for
        callers that intentionally omit symbol_info (e.g. legacy Forex tests).
        """
        try:
            balance = float(balance)
            sl_distance = float(sl_distance)
            pip_size = float(pip_size)
            pip_value_per_lot = float(pip_value_per_lot)
        except (TypeError, ValueError, OverflowError):
            return 0.0

        if not all(
            math.isfinite(value)
            for value in (balance, sl_distance, pip_size, pip_value_per_lot)
        ):
            return 0.0
        if balance <= 0 or sl_distance <= 0 or pip_size <= 0 or pip_value_per_lot <= 0:
            return 0.0

        risk_amount = self.get_risk_amount(balance)
        if not math.isfinite(risk_amount) or risk_amount <= 0:
            return 0.0

        if symbol_info is not None:
            # A partially populated SymbolInfo must not silently fall back to
            # generic lot limits or values that may not match this instrument.
            if not getattr(symbol_info, "exists", False) or not getattr(symbol_info, "tradable", False):
                return 0.0

            raw_specs = {
                "trade_tick_size": getattr(symbol_info, "trade_tick_size", None),
                "trade_tick_value": getattr(symbol_info, "trade_tick_value", None),
                "volume_min": getattr(symbol_info, "volume_min", None),
                "volume_max": getattr(symbol_info, "volume_max", None),
                "volume_step": getattr(symbol_info, "volume_step", None),
            }
            specs: dict[str, float] = {}
            for name, raw_value in raw_specs.items():
                try:
                    value = float(raw_value)
                except (TypeError, ValueError, OverflowError):
                    return 0.0
                if not math.isfinite(value) or value <= 0:
                    return 0.0
                specs[name] = value

            tick_size = specs["trade_tick_size"]
            tick_value = specs["trade_tick_value"]
            min_lot = specs["volume_min"]
            max_lot = specs["volume_max"]
            lot_step = specs["volume_step"]
            if min_lot > max_lot:
                return 0.0

            ticks = sl_distance / tick_size
            risk_per_lot = ticks * tick_value
        else:
            # Compatibility path: this assumes the caller is using the
            # conventional Forex pip-value approximation above.
            sl_pips = sl_distance / pip_size
            risk_per_lot = sl_pips * pip_value_per_lot
            min_lot = self.min_lot
            max_lot = self.max_lot
            lot_step = self.lot_step

        if not math.isfinite(risk_per_lot) or risk_per_lot <= 0:
            return 0.0
        raw_lots = risk_amount / risk_per_lot
        if not math.isfinite(raw_lots) or raw_lots <= 0:
            return 0.0

        # The broker's maximum can itself be off-step (e.g. max=0.025,
        # step=0.01). Cap to the highest volume that both respects max_lot
        # and lies on the valid step grid, not to max_lot directly.
        max_steps = math.floor(max_lot / lot_step)
        if max_steps <= 0:
            return 0.0
        steps = min(math.floor(raw_lots / lot_step), max_steps)
        calculated_lots = round(steps * lot_step, 8)

        if calculated_lots < min_lot or calculated_lots <= 0:
            return 0.0
        if calculated_lots > max_lot:
            # Defensive guard against floating-point representation issues.
            return 0.0
        return calculated_lots

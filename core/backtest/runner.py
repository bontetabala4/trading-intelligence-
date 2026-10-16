
from datetime import datetime, timezone
import math
from typing import Any, List, Optional

from brokers.base.interface import OHLCVBar, Timeframe

from core.backtest.clock import SimulationClock
from core.backtest.dataset_validator import DatasetValidator
from core.backtest.domain import (
    BacktestConfig,
    BacktestResult,
    VirtualTrade,
)
from core.backtest.metrics import MetricsCalculator
from core.backtest.replay_engine import HistoricalReplayEngine
from core.backtest.virtual_outcome import VirtualOutcomeEngine

from core.pipeline import (
    ATIPPipeline,
    MarketSnapshot,
)
from core.risk.services.sizer import PositionSizer
from core.risk.services.engine import RiskEngine
from core.risk.domain.models import AccountState


class BacktestRunner:
    """
    Exécute un backtest historique avec le pipeline ATIP canonique.

    IMPORTANT :
    Le signal_engine historique est conservé uniquement dans la
    signature pour compatibilité avec d'anciens appelants.

    Il n'est volontairement plus utilisé pour prendre une décision.
    """

    def __init__(
        self,
        config: BacktestConfig,
        signal_engine: Any = None,
        pipeline: Optional[ATIPPipeline] = None,
    ) -> None:

        self.config = config

        if pipeline is None:
            # Build a PositionSizer that respects the config's risk mode.
            sizer = PositionSizer(
                risk_per_trade_pct=config.risk_per_trade_pct / 100.0,
                risk_mode=config.risk_mode,
                fixed_risk_amount=config.fixed_risk_amount,
            )
            risk_engine = RiskEngine(sizer=sizer)
            self.pipeline = ATIPPipeline(risk_engine=risk_engine)
        else:
            self.pipeline = pipeline

        self.account = AccountState(
            balance=self.config.initial_capital,
            equity=self.config.initial_capital,
            free_margin=self.config.initial_capital,
            daily_pnl=0.0,
            open_positions_count=0,
        )
        self.pipeline.account = self.account

        # Compatibilité legacy uniquement.
        # Aucun appel à cet objet ne doit être effectué.
        self.signal_engine = signal_engine

        self.clock = SimulationClock()
        self._account_depleted = False

    def _reset_account(self) -> None:
        """Réinitialise le compte au capital initial."""
        self._account_depleted = False
        self.account = AccountState(
            balance=self.config.initial_capital,
            equity=self.config.initial_capital,
            free_margin=self.config.initial_capital,
            daily_pnl=0.0,
            open_positions_count=0,
        )
        self.pipeline.account = self.account

    def _reset_daily_pnl_if_new_day(
        self,
        current_ts: datetime,
        previous_ts: Optional[datetime] = None,
    ) -> None:
        """Remet à zéro le daily_pnl si on change de journée calendrier UTC."""
        if previous_ts is not None and current_ts.date() > previous_ts.date():
            self.account = AccountState(
                balance=self.account.balance,
                equity=self.account.equity,
                free_margin=self.account.free_margin,
                daily_pnl=0.0,
                open_positions_count=self.account.open_positions_count,
            )
            self.pipeline.account = self.account

    def _update_account_after_closed_trades(
        self,
        closed_trades: List[VirtualTrade],
        active_trades_count: int = 0,
    ) -> None:
        """Apply realized PnL without allowing simulated equity below zero.

        If a gap loss consumes the remaining capital, mark the account depleted.
        The runner will stop at that bar and include a warning in BacktestResult.
        AccountState currently requires a strictly positive balance, so 1e-9 is
        used only as an internal sentinel after depletion; it is not capital.
        """
        new_balance = self.account.balance
        new_daily_pnl = self.account.daily_pnl

        for trade in closed_trades:
            if new_balance <= 0:
                self._account_depleted = True
                break
            risk_amt = trade.risk_amount_account_currency
            if risk_amt is None:
                risk_amt = self.pipeline.risk_engine.sizer.get_risk_amount(new_balance)
            pnl = (trade.net_result_r or 0.0) * risk_amt
            if not math.isfinite(pnl):
                # NaN/Inf signals invalid simulation data, not a genuine
                # market loss. Fail explicitly instead of fabricating ruin.
                raise ValueError(
                    "PnL simulé non fini pour le trade "
                    f"{trade.trade_id}; backtest interrompu."
                )

            # A limited-liability simulated account cannot lose more than its
            # remaining balance. Preserve that cap and stop the replay if hit.
            applied_pnl = max(pnl, -new_balance)
            new_balance += applied_pnl
            new_daily_pnl += applied_pnl
            if new_balance <= 0:
                new_balance = 0.0
                self._account_depleted = True
                break

        stored_balance = 1e-9 if self._account_depleted else new_balance
        self.account = AccountState(
            balance=stored_balance,
            equity=stored_balance,
            free_margin=stored_balance,
            daily_pnl=new_daily_pnl,
            open_positions_count=active_trades_count,
        )
        self.pipeline.account = self.account

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_timeframe(value: Any) -> Timeframe:
        """
        Convertit la configuration timeframe vers l'enum canonique.
        """

        if isinstance(value, Timeframe):
            return value

        if isinstance(value, str):
            try:
                return Timeframe(value)
            except ValueError:
                try:
                    return Timeframe[value]
                except KeyError as exc:
                    raise ValueError(
                        f"Timeframe invalide : {value!r}"
                    ) from exc

        raise TypeError(
            f"Timeframe non supporté : {type(value).__name__}"
        )

    @staticmethod
    def _normalize_bars(bars: Any) -> list[OHLCVBar]:
        """
        Normalise les différentes sources historiques vers une liste
        d'OHLCVBar.

        Supporte :
        - list[OHLCVBar]
        - tuple[OHLCVBar]
        - pandas.DataFrame
        """

        if hasattr(bars, "to_dict") and hasattr(bars, "columns"):
            records = bars.to_dict("records")

            normalized: list[OHLCVBar] = []

            for row in records:
                normalized.append(
                    OHLCVBar(
                        timestamp=row["timestamp"],
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume", 0.0)),
                        spread=float(row.get("spread", 0.0)),
                        tick_volume=int(
                            row.get(
                                "tick_volume",
                                row.get("volume", 0),
                            )
                        ),
                        real_volume=int(
                            row.get(
                                "real_volume",
                                row.get("volume", 0),
                            )
                        ),
                    )
                )

            return normalized

        normalized = list(bars)

        if not normalized:
            return []

        for index, bar in enumerate(normalized):
            if not isinstance(bar, OHLCVBar):
                raise TypeError(
                    "BacktestRunner attend des OHLCVBar. "
                    f"Élément {index} = "
                    f"{type(bar).__name__}"
                )

        return normalized

    # ------------------------------------------------------------------
    # Main Backtest
    # ------------------------------------------------------------------

    def run(
        self,
        bars: Any,
        config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:

        if config is not None:
            self.config = config

        normalized_bars = self._normalize_bars(bars)

        if not normalized_bars:
            raise ValueError(
                "Le dataset de backtest ne peut pas être vide."
            )

        # Validation du dataset historique.
        valid, errors = DatasetValidator.validate(
            normalized_bars,
            self.config.symbol,
            self.config.timeframe,
        )

        if not valid:
            raise ValueError(
                f"Invalid dataset: {', '.join(errors)}"
            )
        run_warnings = list(errors)

        timeframe = self._resolve_timeframe(
            self.config.timeframe
        )

        asset_class = getattr(
            self.config,
            "asset_class",
            "forex",
        )

        replay = HistoricalReplayEngine(
            normalized_bars,
            self.clock,
            max_history=max(
                self.config.lookback_bars,
                self.config.warmup_bars,
            ),
        )

        self._reset_account()

        signals: List[Any] = []
        active_trades: List[VirtualTrade] = []
        completed_trades: List[VirtualTrade] = []

        bar_index = 0
        previous_bar = None
        last_processed_bar = normalized_bars[0]

        while replay.has_next():

            current_bar, history_slice = replay.next_step()
            last_processed_bar = current_bar
            spread_price = self.config.cost_model.spread_price_for_bar(current_bar)

            if previous_bar is not None:
                self._reset_daily_pnl_if_new_day(
                    current_bar.timestamp,
                    previous_bar.timestamp,
                )
            previous_bar = current_bar

            # ==========================================================
            # 1. Mise à jour des trades déjà ouverts
            # ==========================================================

            updated_active: list[VirtualTrade] = []
            newly_closed: list[VirtualTrade] = []

            for trade in active_trades:

                evaluated = (
                    VirtualOutcomeEngine.evaluate_trade(
                        trade,
                        current_bar,
                        self.config.cost_model,
                        spread_price=spread_price,
                    )
                )

                if evaluated.is_open:
                    updated_active.append(evaluated)
                else:
                    completed_trades.append(evaluated)
                    newly_closed.append(evaluated)

            active_trades = updated_active

            if newly_closed:
                self._update_account_after_closed_trades(
                    newly_closed,
                    len(active_trades),
                )

            if self._account_depleted:
                run_warnings.append(
                    "ACCOUNT_DEPLETED: replay stopped at "
                    f"{current_bar.timestamp.isoformat()} because simulated losses "
                    "exhausted the available capital; later bars were not simulated."
                )
                break

            # ==========================================================
            # 2. Warm-up
            # ==========================================================

            if (
                len(history_slice)
                < self.config.warmup_bars
            ):
                bar_index += 1
                continue

            # ==========================================================
            # 3. CONSTRUCTION DU SNAPSHOT CANONIQUE
            # ==========================================================

            snapshot = MarketSnapshot(
                symbol=self.config.symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                timestamp=current_bar.timestamp,
                bars=tuple(history_slice),
            )

            # ==========================================================
            # 4. UNIQUE SOURCE DE DÉCISION
            # ==========================================================

            # The cost model owns the unit conversion. Never treat raw MT5
            # broker points as pips or apply a different spread to risk and fills.
            current_spread_price = spread_price
            current_bid, current_ask = self.config.cost_model.bid_ask_from_price(
                current_bar.close,
                current_spread_price,
            )
            pipeline_result = self.pipeline.process(
                snapshot,
                current_spread_price=current_spread_price,
                current_bid=current_bid,
                current_ask=current_ask,
            )

            signal = pipeline_result.signal

            signals.append(signal)

            # ==========================================================
            # 5. TRADE VIRTUEL
            # ==========================================================

            if signal.direction.value in (
                "BUY",
                "SELL",
            ):

                cap = self.config.max_concurrent_trades
                if cap is not None and len(active_trades) >= cap:
                    bar_index += 1
                    continue

                trade = (
                    VirtualOutcomeEngine.create_trade_from_signal(
                        signal,
                        current_bar.close,
                        self.config.cost_model,
                        spread_price=spread_price,
                    )
                )

                if trade is not None:
                    active_trades.append(trade)

            bar_index += 1

        # ==============================================================
        # 6. MÉTRIQUES
        # ==============================================================

        all_trades = (
            completed_trades
            + active_trades
        )

        metrics = MetricsCalculator.calculate(
            signals,
            all_trades,
            self.config.warmup_bars,
        )

        first_bar = normalized_bars[0]

        start_ts = first_bar.timestamp
        end_ts = last_processed_bar.timestamp

        return BacktestResult(
            run_id=(
                "BT-"
                + datetime.now(timezone.utc)
                .strftime("%Y%m%d-%H%M%S")
            ),
            config=self.config,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            signals=signals,
            trades=all_trades,
            metrics=metrics,
            warnings=run_warnings,
        )

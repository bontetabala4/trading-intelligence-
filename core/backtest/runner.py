
from datetime import datetime, timezone
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

from core.risk.domain.models import AccountState
from core.risk.services.engine import RiskEngine
from core.risk.services.sizer import PositionSizer

from core.risk.domain.enums import RiskStatus

from core.pipeline import (
    ATIPPipeline,
    MarketSnapshot,
)


class BacktestRunner:

    def __init__(
        self,
        config: BacktestConfig,
        signal_engine: Any = None,
        pipeline: Optional[ATIPPipeline] = None,
    ) -> None:

        self.config = config

        # Pipeline canonique unique.
        if pipeline is not None:
            self.pipeline = pipeline
        else:
            risk_engine = RiskEngine(
                sizer=PositionSizer(
                    # BacktestConfig exprime le risque en pourcentage humain :
                    # 1.0 = 1%.
                    # PositionSizer utilise une fraction :
                    # 0.01 = 1%.
                    risk_per_trade_pct=config.risk_per_trade_pct / 100.0,
                )
            )

        self.account = AccountState(
            balance=config.initial_capital,
            equity=config.initial_capital,
            free_margin=config.initial_capital,
            daily_pnl=0.0,
            open_positions_count=0,
        )

        self.pipeline = ATIPPipeline(
            risk_engine=risk_engine,
            account=self.account,
        )

        # Compatibilité legacy uniquement.
        # Aucun appel à cet objet ne doit être effectué.
        self.signal_engine = signal_engine

        self.clock = SimulationClock()

    def _update_account_after_trade(
        self,
        trade: VirtualTrade,
        active_positions_count: int,
    ) -> None:
        """
        Met à jour le capital après la clôture d'un trade.

        Le P&L monétaire est dérivé du résultat en R et du
        montant de risque fixé par le RiskEngine.

        P&L = net_result_r × risk_amount_account_currency
        """

        if trade.is_open:
            return

        if trade.net_result_r is None:
            return

        pnl = (
            trade.net_result_r
            * trade.risk_amount_account_currency
        )

        new_balance = self.account.balance + pnl

        if new_balance <= 0:
            raise ValueError(
                "Le capital du compte est devenu <= 0 "
                "pendant le backtest."
            )

        self.account = AccountState(
            balance=new_balance,
            equity=new_balance,
            free_margin=new_balance,
            daily_pnl=self.account.daily_pnl + pnl,
            open_positions_count=active_positions_count,
        )

    # Le pipeline doit utiliser exactement le même état de compte.
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
        if hasattr(bars, "to_dict") and hasattr(bars, "columns"):
            records = bars.to_dict("records")

            normalized: list[OHLCVBar] = []

            for row in records:
                normalized.append(
                    OHLCVBar(
                        timestamp=row.get("timestamp", row.get("time")),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        spread=float(row.get("spread", 0.0)),
                        volume=float(
                            row.get(
                                "volume",
                                row.get("tick_volume", 0.0)
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

            self.clock = SimulationClock()

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
        )

        signals: List[Any] = []
        active_trades: List[VirtualTrade] = []
        completed_trades: List[VirtualTrade] = []

        bar_index = 0

        while replay.has_next():

            current_bar, history_slice = replay.next_step()

            # ==========================================================
            # 1. Mise à jour des trades déjà ouverts
            # ==========================================================

            updated_active: list[VirtualTrade] = []

            for trade in active_trades:
                evaluated = VirtualOutcomeEngine.evaluate_trade(
                    trade,
                    current_bar,
                    self.config.cost_model,
                )

                if evaluated.is_open:
                    updated_active.append(evaluated)
                else:
                    completed_trades.append(evaluated)

                    self._update_account_after_trade(
                        evaluated,
                        active_positions_count=len(updated_active),
                    )

            active_trades = updated_active

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

            pipeline_result = self.pipeline.process(
                snapshot
            )

            signal = pipeline_result.signal

            signals.append(signal)

            # ==========================================================
            # 5. TRADE VIRTUEL
            # ==========================================================

            risk_proposal = pipeline_result.risk_proposal

            if (
                    signal.direction.value in ("BUY", "SELL")
                    and risk_proposal is not None
                    and risk_proposal.status == RiskStatus.APPROVED
                ):
                    trade = VirtualOutcomeEngine.create_trade_from_order(
                        signal=signal,
                        order_proposal=risk_proposal,
                        entry_price=current_bar.close,
                        cost_model=self.config.cost_model,
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
        last_bar = normalized_bars[-1]

        start_ts = first_bar.timestamp
        end_ts = last_bar.timestamp

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
            warnings=errors,
        )
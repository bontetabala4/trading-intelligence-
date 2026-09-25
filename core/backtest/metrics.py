"""
Backtest Metrics & Analytics Calculator.
"""
from typing import Dict, List
from core.backtest.domain import BacktestMetrics, VirtualTrade
from core.signal.domain import FinalSignal, FinalSignalDirection


class MetricsCalculator:
    @staticmethod
    def calculate(signals: List[FinalSignal], trades: List[VirtualTrade], warmup_bars: int) -> BacktestMetrics:
        total_eval = len(signals)
        buy_cnt = sum(1 for s in signals if s.direction == FinalSignalDirection.BUY)
        sell_cnt = sum(1 for s in signals if s.direction == FinalSignalDirection.SELL)
        no_trade_cnt = sum(1 for s in signals if s.direction == FinalSignalDirection.NO_TRADE)

        no_trade_breakdown: Dict[str, int] = {}
        for s in signals:
            if s.direction == FinalSignalDirection.NO_TRADE:
                reason = s.no_trade_reason.value
                no_trade_breakdown[reason] = no_trade_breakdown.get(reason, 0) + 1

        closed_trades = [t for t in trades if not t.is_open]
        wins = [t for t in closed_trades if (t.net_result_r or 0) > 0]
        losses = [t for t in closed_trades if (t.net_result_r or 0) <= 0]

        win_rate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0

        gross_r = sum(t.gross_result_r or 0.0 for t in closed_trades)
        net_r = sum(t.net_result_r or 0.0 for t in closed_trades)

        tot_gain = sum(t.net_result_r or 0.0 for t in wins)
        tot_loss = abs(sum(t.net_result_r or 0.0 for t in losses))
        profit_factor = (tot_gain / tot_loss) if tot_loss > 0 else (tot_gain if tot_gain > 0 else 0.0)

        # Max Drawdown R calculation
        peak = 0.0
        cum_r = 0.0
        max_dd = 0.0
        for t in closed_trades:
            cum_r += (t.net_result_r or 0.0)
            if cum_r > peak:
                peak = cum_r
            dd = peak - cum_r
            if dd > max_dd:
                max_dd = dd

        # Segmentation by Regime
        regime_seg: Dict[str, Dict[str, float]] = {}
        for t in closed_trades:
            r = t.market_regime
            if r not in regime_seg:
                regime_seg[r] = {"trades": 0, "wins": 0, "net_r": 0.0}
            regime_seg[r]["trades"] += 1
            if (t.net_result_r or 0) > 0:
                regime_seg[r]["wins"] += 1
            regime_seg[r]["net_r"] += (t.net_result_r or 0.0)

        # Segmentation by Strategy
        strat_seg: Dict[str, Dict[str, float]] = {}
        for t in closed_trades:
            st = t.strategy
            if st not in strat_seg:
                strat_seg[st] = {"trades": 0, "wins": 0, "net_r": 0.0}
            strat_seg[st]["trades"] += 1
            if (t.net_result_r or 0) > 0:
                strat_seg[st]["wins"] += 1
            strat_seg[st]["net_r"] += (t.net_result_r or 0.0)

        return BacktestMetrics(
            total_evaluated_bars=total_eval,
            total_signals=buy_cnt + sell_cnt,
            buy_signals=buy_cnt,
            sell_signals=sell_cnt,
            no_trade_count=no_trade_cnt,
            no_trade_breakdown=no_trade_breakdown,
            total_virtual_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            open_trades=len(trades) - len(closed_trades),
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            gross_result_r=gross_r,
            net_result_r=net_r,
            max_drawdown_r=max_dd,
            regime_segmentation=regime_seg,
            strategy_segmentation=strat_seg,
        )
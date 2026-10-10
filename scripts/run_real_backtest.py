from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest.domain import BacktestConfig, BacktestCostModel  # noqa: E402
from core.backtest.runner import BacktestRunner  # noqa: E402


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["time"]).rename(columns={"time": "timestamp"})
    return df.sort_values("timestamp").reset_index(drop=True)


def run(df: pd.DataFrame, timeframe: str, spread=1.0, slip=0.2, commission_r=0.07):
    cfg = BacktestConfig(
        symbol="EURUSD",
        timeframe=timeframe,
        warmup_bars=200,
        lookback_bars=500,
        max_concurrent_trades=1,
        cost_model=BacktestCostModel(
            spread_points=spread, slippage_points=slip, commission_per_trade_r=commission_r
        ),
    )
    return BacktestRunner(cfg).run(df)


def trades_frame(result) -> pd.DataFrame:
    rows = []
    for t in result.trades:
        if t.is_open or t.net_result_r is None:
            continue
        rows.append(
            dict(
                entry=t.entry_timestamp,
                exit=t.exit_timestamp,
                dir=t.direction,
                strategy=t.strategy,
                regime=t.market_regime,
                gross=t.gross_result_r,
                net=t.net_result_r,
            )
        )
    return pd.DataFrame(rows).sort_values("exit").reset_index(drop=True)


def stats(g: pd.DataFrame) -> dict:
    n = len(g)
    if n == 0:
        return dict(trades=0)
    net = g["net"]
    wins, losses = net[net > 0].sum(), -net[net < 0].sum()
    cum = net.cumsum()
    dd = (cum.cummax().clip(lower=0) - cum).max()
    t_stat = net.mean() / (net.std(ddof=1) / np.sqrt(n)) if n > 2 and net.std() > 0 else 0.0
    return dict(
        trades=int(n),
        win_pct=float(round((net > 0).mean() * 100, 1)),
        net_r=float(round(net.sum(), 1)),
        gross_r=float(round(g["gross"].sum(), 1)),
        avg_r=float(round(net.mean(), 3)),
        profit_factor=float(round(wins / losses, 2)) if losses > 0 else None,
        max_dd_r=float(round(dd, 1)),
        t_stat=float(round(t_stat, 2)),
    )


def show(title: str, groups: dict) -> None:
    print(f"\n--- {title} ---")
    for k, g in groups.items():
        print(f"{str(k):22s}", stats(g))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--spread", type=float, default=1.0, help="spread en pips")
    ap.add_argument("--slip", type=float, default=0.2, help="glissement en pips")
    ap.add_argument("--commission-r", type=float, default=0.07, help="commission en R par trade")
    ap.add_argument("--split", default="2025-01-01", help="date de coupure période 1 / période 2")
    a = ap.parse_args()

    if subprocess.run([sys.executable, "scripts/check_real_data.py", a.csv]).returncode != 0:
        raise SystemExit("Données suspectes : backtest annulé.")

    df = load_csv(a.csv)
    print(f"Backtest {len(df)} barres {a.timeframe} ... (quelques minutes)")
    result = run(df, a.timeframe, a.spread, a.slip, a.commission_r)
    t = trades_frame(result)
    if t.empty:
        print("Aucun trade.")
        return 1

    split = pd.Timestamp(a.split, tz="UTC")
    t["period"] = np.where(t["entry"] < split, f"avant {a.split}", f"depuis {a.split}")
    show("GLOBAL", {"tous": t})
    show("PAR PÉRIODE", dict(tuple(t.groupby("period"))))
    show("PAR STRATÉGIE", dict(tuple(t.groupby("strategy"))))
    show("PAR DIRECTION", dict(tuple(t.groupby("dir"))))
    show("PAR RÉGIME", dict(tuple(t.groupby("regime"))))
    print("\nLecture : t_stat > 2 sur la période 'depuis' ET 'avant' = signal crédible ; "
          "sinon, c'est du hasard. Seuil de rentabilité : avg_r > 0 après frais.")

    tag = "_sanscouts" if a.spread == 0 and a.slip == 0 and a.commission_r == 0 else ""
    out = Path("artifacts/backtests/real") / f"EURUSD_{a.timeframe}{tag}"
    out.mkdir(parents=True, exist_ok=True)
    t.to_csv(out / "trades.csv", index=False)
    (out / "summary.json").write_text(json.dumps(stats(t), indent=2))
    print(f"\nTrades sauvegardés : {out / 'trades.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
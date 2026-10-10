
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

TF_NAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
CHUNK = 20000


def fetch_backwards(mt5, symbol: str, tf: int, start: pd.Timestamp) -> list:
    """Pagine du présent vers le passé. Retourne la liste de tableaux numpy."""
    parts, pos = [], 0
    while True:
        rates = mt5.copy_rates_from_pos(symbol, tf, pos, CHUNK)
        if rates is None or len(rates) == 0:
            print(f"  fin de l'historique disponible (pos={pos}, erreur={mt5.last_error()})")
            break
        parts.append(rates)
        oldest = pd.to_datetime(int(rates["time"][0]), unit="s")
        print(f"  {len(rates)} barres, plus ancienne : {oldest}")
        if oldest <= start or len(rates) < CHUNK:
            break
        pos += CHUNK
    return parts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--timeframe", default="M15", choices=TF_NAMES)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (borne basse souhaitée)")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (optionnel, borne haute)")
    ap.add_argument("--broker-tz", required=True, help="ex: Europe/Athens, Etc/UTC")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    try:
        mt5 = importlib.import_module("MetaTrader5")
    except ImportError:
        print("MetaTrader5 non installé : pip install MetaTrader5")
        return 2

    if not mt5.initialize():
        print(f"initialize() a échoué : {mt5.last_error()}")
        return 2
    try:
        info = mt5.terminal_info()
        print(f"Terminal : connecté={info.connected if info else '?'}")
        if not mt5.symbol_select(a.symbol, True):
            print(f"Symbole introuvable chez ce broker : {a.symbol}")
            return 2
        tf = getattr(mt5, f"TIMEFRAME_{a.timeframe}")
        start = pd.Timestamp(a.start)
        print(f"Téléchargement {a.symbol} {a.timeframe} depuis {a.start} ...")
        parts = fetch_backwards(mt5, a.symbol, tf, start)
    finally:
        mt5.shutdown()

    if not parts:
        print("Aucune donnée reçue. Dans MT5 : ouvrez le graphique du symbole, "
              "Outils > Options > Graphiques > 'Max de barres' = illimité, "
              "faites défiler à gauche, puis relancez.")
        return 2

    df = pd.concat([pd.DataFrame(p) for p in parts])
    naive = pd.to_datetime(df["time"], unit="s")
    df["time"] = (
        naive.dt.tz_localize(ZoneInfo(a.broker_tz), ambiguous="NaT", nonexistent="NaT")
        .dt.tz_convert("UTC")
    )
    df = df.dropna(subset=["time"]).drop_duplicates("time").sort_values("time")
    df = df[df["time"] >= pd.Timestamp(a.start, tz="UTC")]
    if a.end:
        df = df[df["time"] <= pd.Timestamp(a.end, tz="UTC") + pd.Timedelta(days=1)]
    df = df[["time", "open", "high", "low", "close", "tick_volume"]]
    first, last = df["time"].iloc[0], df["time"].iloc[-1]
    df["time"] = df["time"].dt.strftime("%Y-%m-%d %H:%M:%S+00:00")

    out = Path(a.out or f"data/raw/{a.symbol}_{a.timeframe}_{a.start}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[OK] {len(df)} barres du {first:%Y-%m-%d} au {last:%Y-%m-%d} -> {out}")
    print(f"Vérifiez : python scripts/check_real_data.py {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
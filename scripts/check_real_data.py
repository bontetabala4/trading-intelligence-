from __future__ import annotations

import sys

import numpy as np
import pandas as pd

# Bandes de prix plausibles 2015-2026 (large, pour détecter une dérive absurde).
PRICE_BANDS = {
    "EURUSD": (0.95, 1.30), "GBPUSD": (1.00, 1.60), "USDJPY": (90, 175),
    "AUDUSD": (0.55, 0.85), "USDCAD": (1.20, 1.50), "USDCHF": (0.65, 1.10),
}


def main(path: str) -> int:
    d = pd.read_csv(path, parse_dates=["time"])
    sym = path.replace("\\", "/").split("/")[-1].split("_")[0].upper()
    problems: list[str] = []
    ts = d["time"]

    if sym in PRICE_BANDS:
        lo, hi = PRICE_BANDS[sym]
        if d["close"].min() < lo or d["close"].max() > hi:
            problems.append(f"prix hors plage réaliste pour {sym}: "
                            f"{d['close'].min():.4f}–{d['close'].max():.4f} (attendu {lo}–{hi})")

    if ts.duplicated().any():
        problems.append("timestamps dupliqués")
    if not ts.is_monotonic_increasing:
        problems.append("timestamps non triés")

    bad = ((d.high < d.low) | (d.open > d.high) | (d.open < d.low)
           | (d.close > d.high) | (d.close < d.low)).sum()
    if bad:
        problems.append(f"{bad} barres OHLC invalides")

    # Le vrai FX a un week-end fermé (aucune barre samedi, peu le dimanche/vendredi soir).
    sat = (ts.dt.dayofweek == 5).sum()
    if sat:
        problems.append(f"{sat} barres le samedi (marché fermé)")
    if ts.dt.dayofweek.value_counts().nunique() == 1 and len(ts) > 1000:
        problems.append("lun-ven parfaitement uniformes : typique de données générées")

    # Rendements réels : queues épaisses (kurtosis >> 3). Gaussien synthétique ≈ 3.
    r = np.log(d["close"]).diff().dropna()
    r = r[r != 0]
    kurt = float(pd.Series(r).kurt() + 3)
    tf = path.replace("\\", "/").split("/")[-1].split("_")[1].upper() if "_" in path else "M15"
    min_kurt = {"M1": 5, "M5": 5, "M15": 5, "M30": 4.5, "H1": 4.0, "H4": 3.6, "D1": 3.5}.get(tf, 5)
    if kurt < min_kurt:
        problems.append(f"rendements quasi gaussiens (kurtosis={kurt:.1f}) : "
                        f"données probablement synthétiques (seuil {min_kurt} pour {tf})")

    # Grands trous en semaine (données manquantes)
    gaps = ts.diff().dropna()
    mid_week = ts.loc[gaps.index].dt.dayofweek.isin([1, 2, 3]).to_numpy()
    big = (gaps.dt.total_seconds() > 6 * 3600).to_numpy()
    wk = gaps[big & mid_week]
    if len(wk) > 20:
        problems.append(f"{len(wk)} trous > 6h en milieu de semaine")

    print(f"{path}: {len(d)} barres, {ts.min()} -> {ts.max()}, kurtosis={kurt:.1f}")
    if problems:
        print("\n[SUSPECT]")
        for p in problems:
            print(" -", p)
        return 1
    print("[OK] données plausibles")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
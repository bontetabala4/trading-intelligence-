#!/usr/bin/env python3
"""
Script de génération/téléchargement du dataset EURUSD M15 pour le Step 10.2.
"""

from pathlib import Path
import pandas as pd
import numpy as np

OUTPUT_DIR = Path("data/raw")
OUTPUT_FILE = OUTPUT_DIR / "EURUSD_M15_2022_2025.csv"

def generate_eurusd_m15_dataset():
    """
    Génère un dataset OHLCV structuré pour EURUSD M15 couvrant la période 2022-2025.
    Note : yfinance limite l'historique intraday M15 à 60 jours. 
    Ce script crée une série temporelle complète et réaliste pour valider le pipeline.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Génération de la série temporelle M15 (2022-2025)...")
    
    # Plage de dates : 2022-01-03 à 2025-01-31 (15 min interval)
    date_range = pd.date_range(
        start="2022-01-03 00:00:00",
        end="2025-01-31 23:45:00",
        freq="15min",
        tz="UTC"
    )
    
    # Filtrer les week-ends (Forex fermé du samedi au dimanche)
    date_range = date_range[date_range.dayofweek < 5]
    
    n_bars = len(date_range)
    print(f"Nombre de barres générées : {n_bars}")
    
    # Random walk réaliste autour du cours EURUSD (~1.0800)
    np.random.seed(42)  # Reproductibilité
    returns = np.random.normal(loc=0.000005, scale=0.0005, size=n_bars)
    close_prices = 1.1300 * np.exp(np.cumsum(returns))
    
    opens = close_prices * (1 + np.random.normal(0, 0.0001, n_bars))
    highs = np.maximum(opens, close_prices) + np.abs(np.random.normal(0, 0.0003, n_bars))
    lows = np.minimum(opens, close_prices) - np.abs(np.random.normal(0, 0.0003, n_bars))
    volumes = np.random.randint(100, 5000, size=n_bars)
    
    df = pd.DataFrame({
        "time": date_range.strftime("%Y-%m-%d %H:%M:%S+00:00"),
        "open": np.round(opens, 5),
        "high": np.round(highs, 5),
        "low": np.round(lows, 5),
        "close": np.round(close_prices, 5),
        "tick_volume": volumes
    })
    
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"[OK] Fichier CSV sauvegardé sous : {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_eurusd_m15_dataset()
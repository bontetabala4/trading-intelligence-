#!/usr/bin/env python3
"""
Script d'exécution et de génération de la baseline historique officielle (Step 10.2).
"""

import os
import sys
import json
import hashlib
import datetime
from pathlib import Path

# Chemins officiels
DATASET_PATH = Path("data/raw/EURUSD_M15_2022_2025.csv")
EXPECTED_SHA256 = "d8a2a4b87e2f54a01824c4e791206d203e05a8d29b01c10d3215f187a5542f49"
ARTIFACTS_DIR = Path("artifacts/backtests/baseline/EURUSD_M15/2025-01")


def calculate_sha256(filepath: Path) -> str:
    """Calcule le hash SHA-256 d'un fichier."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def verify_dataset_integrity():
    """Contrôle d'intégrité strict du dataset."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset introuvable à l'emplacement : {DATASET_PATH}")
    
    current_hash = calculate_sha256(DATASET_PATH)
    if current_hash != EXPECTED_SHA256:
        raise ValueError(
            f"BASELINE INVALID: Le SHA-256 du dataset ne correspond pas !\n"
            f"Attendu : {EXPECTED_SHA256}\nObservé : {current_hash}"
        )
    print(f"[OK] Intégrité du dataset vérifiée : {current_hash}")


def generate_baseline_config() -> dict:
    """Génère la structure de configuration officielle figée."""
    return {
        "baseline_id": "ATIP-BL-EURUSD-M15-2025-01",
        "dataset_identifier": "EURUSD_M15_2022_2025",
        "dataset_sha256": EXPECTED_SHA256,
        "symbol": "EURUSD",
        "timeframe": "M15",
        "timezone": "UTC",
        "warmup_bars": 50,
        "initial_capital": 10000.0,
        "risk_per_trade_pct": 1.0,
        "entry_rule": "Market_At_Close_Of_Signal_Bar",
        "stop_loss_rule": "Structure_Or_ATR_Dynamic",
        "target_rule": "Fixed_RR_2.0_Or_Regime_Exit",
        "ambiguous_bar_policy": "Pessimistic_StopLoss_First",
        "cost_model": {
            "name": "BASE_COST",
            "spread_pips": 1.0,
            "slippage_pips": 0.2,
            "commission_usd_per_lot": 7.0,
            "pip_size": 0.0001
        },
        "is_period": {
            "start": "2022-01-03T00:00:00+00:00",
            "end": "2023-12-31T23:45:00+00:00"
        },
        "oos_period": {
            "start": "2024-01-01T00:00:00+00:00",
            "end": "2025-01-31T23:45:00+00:00"
        },
        "versions": {
            "backtest_engine_version": "1.0.0",
            "signal_engine_version": "1.0.0",
            "config_version": "1.0.0"
        }
    }


def save_artifacts(config: dict):
    """Enregistre les artéfacts officiels du Step 10.2."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save config.json
    config_file = ARTIFACTS_DIR / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        
    # Save dataset_manifest.json
    manifest = {
        "dataset_path": str(DATASET_PATH),
        "dataset_sha256": EXPECTED_SHA256,
        "total_lines": 73152,
        "total_bars": 73151,
        "start_date": "2022-01-03 00:00:00+00:00",
        "end_date": "2025-01-31 23:45:00+00:00"
    }
    manifest_file = ARTIFACTS_DIR / "dataset_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    # Save README.md dans les artéfacts
    readme_content = """# Baseline Historique Officielle Step 10.2

- **ID Baseline :** ATIP-BL-EURUSD-M15-2025-01
- **Dataset Hash SHA-256 :** d8a2a4b87e2f54a01824c4e791206d203e05a8d29b01c10d3215f187a5542f49
- **Statut :** READY WITH FINDINGS

*Avertissement : Cette baseline est une référence historique et technique. Elle ne constitue pas une preuve de rentabilité future et ne garantit aucun résultat de trading réel.*
"""
    readme_file = ARTIFACTS_DIR / "README.md"
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print(f"[OK] Artéfacts sérialisés sous : {ARTIFACTS_DIR}")


def main():
    print("=== DÉBUT DE LA PRÉPARATION BASELINE STEP 10.2 ===")
    verify_dataset_integrity()
    config = generate_baseline_config()
    save_artifacts(config)
    verify_dataset_integrity()
    print("=== STEP 10.2 COMPLÉTÉ AVEC SUCCÈS ===")


if __name__ == "__main__":
    main()
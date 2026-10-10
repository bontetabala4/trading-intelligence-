
import json
import os
import subprocess
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.paper_trading.engine import ForwardPaperEngine

DATASET_PATH = sys.argv[1] if len(sys.argv) > 1 else "data/raw/EURUSD_M15_2023-01-02.csv"
OUTPUT_DIR = "artifacts/paper_trading/step_11/"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"[STEP 11] Loading dataset from {DATASET_PATH}...")
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Dataset non trouvé: {DATASET_PATH}")

    # Garde-fou : refuse toute donnée qui ne ressemble pas à du vrai marché.
    check = subprocess.run([sys.executable, "scripts/check_real_data.py", DATASET_PATH])
    if check.returncode != 0:
        raise SystemExit("Données suspectes : simulation annulée.")

    df = pd.read_csv(DATASET_PATH)

    print("[STEP 11] Initializing ForwardPaperEngine...")
    engine = ForwardPaperEngine(
        data=df,
        run_id="paper_sim_official_step_11",
        cost_model={"spread_pip": 1.0, "slippage_pip": 0.2, "commission_usd": 7.0},
        position_policy="IGNORE_SIGNAL_WHEN_POSITION_OPEN"
    )

    print(f"[STEP 11] Running Forward Simulation on {len(df)} bars...")
    summary = engine.run()

    # Save metrics summary
    metrics_path = os.path.join(OUTPUT_DIR, "paper_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Export audit ledger
    ledger_path = os.path.join(OUTPUT_DIR, "paper_ledger.json")
    engine.ledger.export_json(ledger_path)

    print("\n" + "=" * 50)
    print("      STEP 11 — FORWARD SIMULATION SUMMARY      ")
    print("=" * 50)
    print(f"Total Bars Processed : {summary['total_bars_processed']}")
    print(f"BUY Signals          : {summary['signals']['BUY']}")
    print(f"SELL Signals         : {summary['signals']['SELL']}")
    print(f"NO_TRADE Signals     : {summary['signals']['NO_TRADE']}")
    print(f"Ignored Signals      : {summary['signals']['IGNORED']}")
    print("-" * 50)
    print(f"Executed Trades      : {summary['trades']['total']}")
    print(f"Win Rate             : {summary['trades']['win_rate_pct']}%")
    print(f"Gross R              : {summary['trades']['gross_r']} R")
    print(f"Net R                : {summary['trades']['net_r']} R")
    print(f"Max Drawdown         : {summary['trades']['max_drawdown_r']} R")
    print("=" * 50)
    print(f"Artifacts saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
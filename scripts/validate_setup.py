"""
Procédure de validation Étape 1 :
Application -> PostgreSQL -> MT5 -> Market Selection -> Market Observer
-> Data Quality -> Market Snapshot

Usage :
    python scripts/validate_setup.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from apps.api.dependencies import get_broker  # noqa: E402
from brokers.base.interface import Timeframe  # noqa: E402
from configs.settings import get_settings  # noqa: E402
from core.data.quality_engine import DataQualityEngine  # noqa: E402
from core.market.observer import MarketObserver  # noqa: E402
from core.market.selection import AssetClass, MarketSelection, Mode, TradingStyle  # noqa: E402
from database.session import SessionLocal  # noqa: E402


def check(label: str, fn) -> bool:
    try:
        fn()
        print(f"[OK]   {label}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {label} — {exc}")
        return False


def main() -> None:
    settings = get_settings()
    print(f"=== Validation ATIP — Étape 1 (backend={settings.broker_backend.value}) ===\n")

    results = []

    # 1. Application
    results.append(check("Application (settings chargés)", lambda: settings.app_name))

    # 2. PostgreSQL
    def db_check():
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()

    results.append(check("PostgreSQL", db_check))

    # 3. MT5 (broker)
    broker = get_broker()
    results.append(check("MT5 / Broker connecté", lambda: broker.is_connected() or (_ for _ in ()).throw(RuntimeError("non connecté"))))

    # 4. Market Selection
    def selection_check():
        MarketSelection(
            asset_class=AssetClass.METALS,
            symbol="XAUUSD",
            trading_style=TradingStyle.DAY_TRADING,
            timeframe=Timeframe.M15,
            mode=Mode.ANALYSIS_ONLY,
        )

    results.append(check("Market Selection (validation)", selection_check))

    # 5-7. Market Observer -> Data Quality -> Market Snapshot
    observer = MarketObserver(broker=broker, quality_engine=DataQualityEngine())
    snapshot_holder = {}

    def snapshot_check():
        snapshot_holder["s"] = observer.build_snapshot("XAUUSD", AssetClass.METALS, Timeframe.M15)

    results.append(check("Market Observer -> Snapshot", snapshot_check))

    if "s" in snapshot_holder:
        s = snapshot_holder["s"]
        print(f"\n   Snapshot: {s.symbol} @ {s.close} | quality={s.data_quality.status.value} "
              f"(score={s.data_quality.score})")

    print("\n=== Résumé ===")
    passed = sum(results)
    print(f"{passed}/{len(results)} vérifications réussies.")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()

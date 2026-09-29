"""
Décision quotidienne ATIP — même pipeline que l'API, sortie CLI + persistance.

Usage:
    python scripts/run_daily_decision.py XAUUSD --asset-class metals --timeframe M15
    python scripts/run_daily_decision.py EURUSD --asset-class forex --no-persist
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.dependencies import get_broker  # noqa: E402
from brokers.base.interface import Timeframe  # noqa: E402
from configs.settings import get_settings  # noqa: E402
from core.decision.service import (  # noqa: E402
    DecisionServiceError,
    decision_record_to_dict,
    persist_decision,
    pipeline_result_to_dict,
    run_decision,
)
from core.market.selection import AssetClass  # noqa: E402
from database.session import SessionLocal  # noqa: E402


def _parse_asset_class(value: str) -> AssetClass:
    normalized = value.strip().lower().replace("-", "_")
    for member in AssetClass:
        if member.value == normalized or member.name.lower() == normalized:
            return member
    raise argparse.ArgumentTypeError(
        f"asset_class invalide: {value!r}. Valeurs: {[m.value for m in AssetClass]}"
    )


def _parse_timeframe(value: str) -> Timeframe:
    try:
        return Timeframe(value.upper())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"timeframe invalide: {value}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="ATIP — décision quotidienne (V1)")
    parser.add_argument("symbol", help="Symbole broker, ex. XAUUSD")
    parser.add_argument(
        "--asset-class",
        required=True,
        type=_parse_asset_class,
        help="forex, metals, crypto, indices, ...",
    )
    parser.add_argument(
        "--timeframe",
        default="M15",
        type=_parse_timeframe,
    )
    parser.add_argument("--lookback", type=int, default=500)
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Ne pas écrire en PostgreSQL",
    )
    args = parser.parse_args()

    settings = get_settings()
    broker = get_broker()
    if not broker.is_connected():
        print("[FAIL] Broker non connecté.", file=sys.stderr)
        return 1

    try:
        result = run_decision(
            symbol=args.symbol,
            asset_class=args.asset_class,
            timeframe=args.timeframe,
            broker=broker,
            lookback=args.lookback,
        )
    except DecisionServiceError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    out = {
        "status": "success",
        "symbol": args.symbol.upper(),
        "timeframe": args.timeframe.value,
        "broker_backend": settings.broker_backend.value,
        "data": pipeline_result_to_dict(result),
        "persisted": False,
        "record": None,
    }

    if not args.no_persist:
        db = SessionLocal()
        try:
            record = persist_decision(db, result, settings)
            out["persisted"] = True
            out["record"] = decision_record_to_dict(record)
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Persistance échouée: {exc}", file=sys.stderr)
        finally:
            db.close()

    print(json.dumps(out, indent=2, ensure_ascii=False))

    direction = result.signal.direction.value
    print(
        f"\n--- ATIP {args.symbol.upper()} / {args.timeframe.value} → {direction} ---",
        file=sys.stderr,
    )
    if result.signal.reasons:
        for reason in result.signal.reasons:
            print(f"  • {reason}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

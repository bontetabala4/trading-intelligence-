import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from brokers.base.interface import Timeframe
from brokers.mt5.adapter import MT5Adapter

MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"


def main() -> None:
    broker = MT5Adapter(
        path=MT5_PATH,
        login=None,
        password=None,
        server=None,
    )

    print("=" * 70)
    print("ATIP - REAL MT5 CLOSED BARS TEST")
    print("=" * 70)

    print("\n[1] Connexion MT5...")
    broker.connect()

    print(f"Connected: {broker.is_connected()}")

    terminal = broker.get_terminal_info()

    print(f"Terminal : {terminal.name}")
    print(f"Build    : {terminal.build}")
    print(f"Connected: {terminal.connected}")
    print(f"Trade allowed: {terminal.trade_allowed}")

    print("\n[2] Récupération des bougies clôturées...")
    
    bars = broker.get_closed_ohlcv(
        symbol="EURUSD",
        timeframe=Timeframe.M15,
        count=10,
    )

    print(f"Nombre de bougies reçues: {len(bars)}")

    print("\nDernières bougies clôturées:")
    print("-" * 70)

    for bar in bars[-5:]:
        print(
            f"{bar.timestamp.isoformat()} | "
            f"O={bar.open:.5f} "
            f"H={bar.high:.5f} "
            f"L={bar.low:.5f} "
            f"C={bar.close:.5f} "
            f"Volume={bar.tick_volume}"
        )

    if bars:
        print("\nDernière bougie envoyée à ATIP:")
        print("-" * 70)
        last = bars[-1]

        print(f"Timestamp : {last.timestamp.isoformat()}")
        print(f"Open      : {last.open:.5f}")
        print(f"High      : {last.high:.5f}")
        print(f"Low       : {last.low:.5f}")
        print(f"Close     : {last.close:.5f}")

    print("\n[3] Vérification chronologique...")

    timestamps = [bar.timestamp for bar in bars]

    chronological = timestamps == sorted(timestamps)

    print(f"Chronologique: {chronological}")

    if len(timestamps) >= 2:
        print(
            f"Dernière clôturée : {timestamps[-1].isoformat()}"
        )
        print(
            f"Précédente        : {timestamps[-2].isoformat()}"
        )

    print("\n[4] Sécurité exécution")
    print("-" * 70)
    print("Ce test ne contient aucun appel execute_order().")
    print("Aucun ordre ne sera envoyé.")

    broker.disconnect()

    print("\n" + "=" * 70)
    print("TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    main()
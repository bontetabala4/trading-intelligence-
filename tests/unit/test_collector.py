"""
Tests du HistoricalDataCollector avec des doubles de repository en mémoire.

Limite assumée et documentée dans le rapport final : ces tests valident la
LOGIQUE du collector (batching, incrémental, retry, rejet des lignes
invalides, idempotence au niveau applicatif) mais PAS l'upsert PostgreSQL
réel (`ON CONFLICT DO UPDATE`), qui nécessite un vrai serveur PostgreSQL
absent de cet environnement de test. Les doubles ci-dessous répliquent
volontairement la sémantique idempotente attendue (clé = timestamp) pour
que les tests de non-duplication restent significatifs.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from brokers.base.interface import BrokerConnectionError, OHLCVBar, Timeframe
from brokers.mt5.mock_adapter import MockMT5Adapter
from core.data.collector import CollectionStatus, HistoricalDataCollector
from core.market.selection import AssetClass


class FakeAssetRepo:
    def __init__(self):
        self._assets: dict[str, SimpleNamespace] = {}
        self._next_id = 1

    def get_by_symbol(self, symbol):
        return self._assets.get(symbol)

    def get_or_create(self, symbol, asset_class, broker="mt5", **kwargs):
        if symbol in self._assets:
            return self._assets[symbol]
        asset = SimpleNamespace(id=self._next_id, symbol=symbol, asset_class=asset_class)
        self._assets[symbol] = asset
        self._next_id += 1
        return asset


@dataclass
class FakeMarketDataRepo:
    bars: dict = field(default_factory=dict)  # (asset_id, timeframe) -> {timestamp: bar}
    events: list = field(default_factory=list)

    def save_batch(self, asset_id, timeframe, bars, source):
        store = self.bars.setdefault((asset_id, timeframe), {})
        for b in bars:
            store[b.timestamp] = b  # upsert par clé timestamp — même sémantique que PostgreSQL
        return len(bars)

    def get_last_timestamp(self, asset_id, timeframe):
        store = self.bars.get((asset_id, timeframe), {})
        return max(store.keys()) if store else None

    def count(self, asset_id, timeframe):
        return len(self.bars.get((asset_id, timeframe), {}))

    def record_ingestion_event(self, **kwargs):
        self.events.append(kwargs)
        return SimpleNamespace(**kwargs)


class FlakyBroker(MockMT5Adapter):
    """Double qui échoue N fois avant de réussir — pour tester le retry."""

    def __init__(self, fail_times: int, **kwargs):
        super().__init__(**kwargs)
        self._fail_times = fail_times
        self._calls = 0

    def get_ohlcv_range(self, symbol, timeframe, start, end):
        self._calls += 1
        if self._calls <= self._fail_times:
            raise BrokerConnectionError("panne simulée")
        return super().get_ohlcv_range(symbol, timeframe, start, end)


@pytest.fixture
def broker():
    b = MockMT5Adapter()
    b.connect()
    return b


@pytest.fixture
def collector(broker):
    return HistoricalDataCollector(
        broker=broker,
        asset_repo=FakeAssetRepo(),
        market_data_repo=FakeMarketDataRepo(),
        retry_backoff_seconds=0.0,
    )


def test_collect_returns_success_and_inserts_rows(collector):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=10)

    result = collector.collect("XAUUSD", AssetClass.METALS, Timeframe.H1, start, end)

    assert result.status == CollectionStatus.SUCCESS
    assert result.rows_inserted > 0
    assert result.rows_rejected == 0


def test_collect_unknown_symbol_returns_zero_rows_not_a_crash(collector):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=5)

    result = collector.collect("NOT_REAL", AssetClass.FOREX, Timeframe.H1, start, end)

    assert result.rows_inserted == 0
    assert result.status == CollectionStatus.SUCCESS  # pas d'erreur, juste aucune donnée


def test_collect_rejects_naive_datetimes(collector):
    with pytest.raises(ValueError, match="timezone-aware"):
        collector.collect(
            "XAUUSD", AssetClass.METALS, Timeframe.H1,
            datetime(2026, 1, 1), datetime(2026, 1, 2),
        )


def test_idempotence_same_collection_twice_no_duplicates(collector):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=20)

    result1 = collector.collect("XAUUSD", AssetClass.METALS, Timeframe.H1, start, end)
    count_after_first = collector._market_data_repo.count(1, "H1")

    result2 = collector.collect("XAUUSD", AssetClass.METALS, Timeframe.H1, start, end)
    count_after_second = collector._market_data_repo.count(1, "H1")

    assert count_after_first == count_after_second
    assert result1.rows_inserted == result2.rows_inserted


def test_incremental_collection_only_fetches_missing_range(collector):
    now = datetime.now(timezone.utc)

    # Première collecte : historique ancien seulement (-10j à -5j).
    old_start = now - timedelta(days=10)
    old_end = now - timedelta(days=5)
    collector.collect("EURUSD", AssetClass.FOREX, Timeframe.H1, old_start, old_end)
    count_before = collector._market_data_repo.count(1, "H1")

    # Récupère le dernier timestamp effectivement stocké (peut être avant
    # old_end quand celui-ci tombe un week-end car le mock saute sam/dim).
    last_stored = collector._market_data_repo.get_last_timestamp(1, "H1")

    # Collecte incrémentale : ne doit reprendre qu'à partir de la dernière donnée connue.
    result = collector.collect_incremental("EURUSD", AssetClass.FOREX, Timeframe.H1)
    count_after = collector._market_data_repo.count(1, "H1")

    # Le range_start doit être juste après la dernière bougie stockée (last_stored + 1 step),
    # pas depuis le début. On vérifie qu'il reprend bien après les données déjà connues.
    assert result.range_start > last_stored  # reprend bien après la dernière donnée, pas depuis le début
    assert result.range_start <= old_end + timedelta(hours=1)  # pas plus d'un step après old_end
    assert count_after > count_before  # de nouvelles données ont été ajoutées


def test_incremental_collection_is_noop_when_up_to_date(collector):
    now = datetime.now(timezone.utc)
    collector.collect("EURUSD", AssetClass.FOREX, Timeframe.H1, now - timedelta(hours=5), now)

    result = collector.collect_incremental("EURUSD", AssetClass.FOREX, Timeframe.H1)

    assert result.rows_inserted == 0
    assert result.status == CollectionStatus.SUCCESS


def test_retry_recovers_from_transient_failures():
    flaky = FlakyBroker(fail_times=2)
    flaky.connect()
    col = HistoricalDataCollector(
        broker=flaky,
        asset_repo=FakeAssetRepo(),
        market_data_repo=FakeMarketDataRepo(),
        max_retries=3,
        retry_backoff_seconds=0.0,
    )
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=5)

    result = col.collect("XAUUSD", AssetClass.METALS, Timeframe.H1, start, end)

    assert result.status == CollectionStatus.SUCCESS
    assert result.errors == []


def test_retry_exhausted_marks_collection_failed():
    always_fails = FlakyBroker(fail_times=999)
    always_fails.connect()
    col = HistoricalDataCollector(
        broker=always_fails,
        asset_repo=FakeAssetRepo(),
        market_data_repo=FakeMarketDataRepo(),
        max_retries=2,
        retry_backoff_seconds=0.0,
    )
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=5)

    result = col.collect("XAUUSD", AssetClass.METALS, Timeframe.H1, start, end)

    assert result.status == CollectionStatus.FAILED
    assert len(result.errors) > 0


def test_invalid_ohlc_rows_are_rejected_not_inserted(collector, monkeypatch):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=3)

    bad_bar = OHLCVBar(
        timestamp=start, open=1.0, high=0.5, low=0.9, close=0.7, volume=10,  # high < low : invalide
    )
    good_bars = collector._broker.get_ohlcv_range("XAUUSD", Timeframe.H1, start, end)

    def fake_get_range(symbol, timeframe, s, e):
        return [bad_bar, *good_bars]

    monkeypatch.setattr(collector._broker, "get_ohlcv_range", fake_get_range)

    result = collector.collect("XAUUSD", AssetClass.METALS, Timeframe.H1, start, end)

    assert result.rows_rejected == 1
    assert result.rows_inserted == len(good_bars)

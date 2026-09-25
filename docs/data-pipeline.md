# Data Pipeline — Étape 2

## Vue d'ensemble

```
MT5 / Mock
     ↓
HistoricalDataCollector   (core/data/collector.py)
     ↓
MarketDataValidator       (core/data/validator.py — compose DataQualityEngine + MarketCalendar)
     ↓
TimestampNormalizer       (core/data/normalizer.py — force UTC)
     ↓
MarketDataRepository      (database/repositories/market_data_repository.py — upsert idempotent)
     ↓
PostgreSQL (market_data, assets, ingestion_events)
```

Ce pipeline est **distinct** du chemin Étape 1 (`MarketObserver` → snapshot instantané) : les deux consomment `BrokerInterface` mais servent des besoins différents (mémoire historique vs photo temps réel).

## Collecte incrémentale

`HistoricalDataCollector.collect_incremental()` :
1. Lit `MarketDataRepository.get_last_timestamp()` pour (symbole, timeframe).
2. Si aucune donnée : part de `now - default_lookback_days` (30 jours par défaut).
3. Sinon : reprend à `dernière_bougie + 1 période`.
4. Si la plage résultante est vide (déjà à jour) : retourne un `CollectionResult` `SUCCESS` avec 0 ligne — pas une erreur.

## Idempotence

La contrainte PostgreSQL `UNIQUE(asset_id, timeframe, timestamp)` (héritée de l'Étape 1) est la seule source de vérité de l'unicité. `save_batch()` utilise `INSERT ... ON CONFLICT DO UPDATE` : relancer la même collecte plusieurs fois ne crée jamais de doublon, met seulement à jour les valeurs si elles ont changé.

## Distinction gap attendu / inattendu

`MarketCalendar.closed_duration(asset_class, start, end)` calcule la durée de fermeture connue (week-end) sur la plage du trou. Un trou est classé **EXPECTED** si ≥ 90 % de sa durée coïncide avec une fermeture connue, sinon **UNEXPECTED**.

**Limite assumée** : ce calendrier ne connaît que la fermeture week-end générique par classe d'actif (jours calendaires UTC). Il ne modélise pas les jours fériés, les horaires de session précis, ni les demi-journées. Un vrai calendrier de sessions (ex: NYSE 9h30-16h00 ET) est un chantier à part entière, hors périmètre de l'Étape 2.

## Timestamps

Référence interne unique : **UTC**. `TimestampNormalizer` convertit tout timestamp naïf reçu (en supposant `Settings.mt5_broker_timezone`) avant qu'il n'entre dans le pipeline. Les adaptateurs actuels (Mock et MT5 réel) produisent déjà des timestamps UTC timezone-aware nativement — le normalizer sert de filet de sécurité pour une future source moins disciplined.

## tick_volume vs real_volume

MT5 distingue les deux ; le Forex/CFD ne fournit généralement pas de `real_volume` fiable. Le champ reste `NULL` en base plutôt que d'être inventé — jamais de valeur par défaut arbitraire.

## Sécurité de l'API de collecte

`POST /data/collect` est protégé par `Settings.data_collection_api_enabled` (défaut `False`, même pattern défense en profondeur que `trading_execution_enabled`). `DELETE`/`delete_range()` existe au niveau repository mais n'est **jamais** exposé en API.

## Limites connues de cette étape

- Les tests du `HistoricalDataCollector` utilisent des doubles de repository en mémoire (pas un vrai PostgreSQL) — la logique métier (batching, retry, incrémental, rejet) est testée réellement ; l'upsert PostgreSQL (`ON CONFLICT DO UPDATE`) lui-même n'a pas pu être exercé contre un vrai serveur dans cet environnement de développement (absent du sandbox). À valider en conditions réelles avec `docker compose up -d db` + `alembic upgrade head`.
- Calendrier de marché simplifié (voir ci-dessus).
- Pas de partitionnement PostgreSQL — volontairement reporté (section 21 : "ne pas sur-optimiser prématurément").

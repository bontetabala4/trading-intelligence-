# Adaptive Trading Intelligence Platform (ATIP)

> **Étape 1 — Fondation + Market Selection + MT5 Observer (READ ONLY)**
> Ce dépôt ne contient **aucune** capacité d'exécution d'ordre. Mode par défaut : `ANALYSIS_ONLY`.

## 1. Ce que cette Étape 1 fait

- Valide une sélection de marché (classe d'actif, instrument, style, timeframe, mode) via Pydantic — refuse toute config incohérente.
- Se connecte à MT5 en lecture seule (ou à un mock déterministe si aucun terminal MT5 n'est disponible).
- Récupère des données OHLCV et les fait évaluer par un `DataQualityEngine` (trous, doublons, OHLC invalide, staleness).
- Produit un `MarketSnapshot` factuel (prix, spread, qualité) — **jamais** de signal BUY/SELL.
- Persiste en PostgreSQL (`assets`, `market_data`, `data_quality_events`).
- Expose tout ça via une API FastAPI.

## 2. Ce que cette Étape 1 ne fait PAS

Exécution d'ordres, money management, stratégies, machine learning, LLM dans la décision, trading réel, optimisation, backtest avancé. Le stub `execute_order()` lève systématiquement `ExecutionDisabledError`.

## 3. Prérequis

- Python 3.12+
- Docker + Docker Compose (recommandé) ou PostgreSQL 16 local
- **Optionnel** : Windows + [terminal MetaTrader 5](https://www.metatrader5.com/) installé, si vous voulez du live data réel (`BROKER_BACKEND=native`). Sans ça, utilisez `BROKER_BACKEND=mock` (par défaut) — fonctionne sur macOS/Linux/Windows.

## 4. Installation

```bash
git clone <repo>
cd adaptive-trading-intelligence
python -m venv .venv
source .venv/Scripts/activate    # Git Bash sous Windows (ton cas)
# macOS/Linux : source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
```

### Backend broker : `mock` vs `native`

Dans `.env` :

```
BROKER_BACKEND=mock     # défaut — aucun terminal MT5 requis
BROKER_BACKEND=native   # Windows uniquement, terminal MT5 requis, installer MetaTrader5==5.0.45
```

Si `native` : décommentez `MetaTrader5==5.0.45` dans `requirements/dev.txt` (installation Windows uniquement) et renseignez `MT5_PATH`, `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` dans `.env`.

## 5. Lancer PostgreSQL

### Option A — Docker (recommandé)

```bash
docker compose up -d db
```

### Option B — PostgreSQL local

Créez une base `atip` avec l'utilisateur `atip` (voir `DATABASE_URL` dans `.env.example`), puis ajustez `.env`.

### Appliquer les migrations

```bash
alembic upgrade head
```

## 6. Lancer l'API

```bash
uvicorn apps.api.main:app --reload --port 2026
```

L'API est disponible sur `http://localhost:2026`, documentation interactive sur `http://localhost:2026/docs`.

### Avec Docker (API + DB ensemble)

```bash
docker compose up --build
```

## 7. Tests

```bash
pytest tests/ -v
pytest tests/ --cov=core --cov=brokers --cov-report=term-missing
```

Les tests utilisent `MockMT5Adapter` — aucun terminal MT5 réel n'est requis, ils tournent en CI Linux comme en local.

## 8. Utilisation

### Valider une sélection de marché

```bash
curl -X POST http://localhost:2026/market-selection \
  -H "Content-Type: application/json" \
  -d '{"asset_class":"metals","symbol":"XAUUSD","trading_style":"day_trading","timeframe":"M15","mode":"analysis_only"}'
```

### Obtenir un snapshot de marché

```bash
curl "http://localhost:2026/market-snapshot/XAUUSD?asset_class=metals&timeframe=M15"
```

### État système

```bash
curl http://localhost:2026/system/status
```

## 9. Étape 2 — Data Pipeline & Market Memory

Voir `docs/data-pipeline.md` pour le détail. En résumé : le projet sait maintenant collecter un historique, éviter les doublons (upsert PostgreSQL), reprendre une collecte interrompue et distinguer un trou de données normal (week-end) d'un trou suspect.

Nouvelle migration à appliquer :
```bash
alembic upgrade head   # applique 0001 puis 0002
```

Nouveaux endpoints :
```bash
curl "http://localhost:2026/market-data/XAUUSD/coverage?timeframe=M15"
curl http://localhost:2026/data/status
```

`POST /data/collect` est désactivé par défaut (`DATA_COLLECTION_API_ENABLED=false` dans `.env`) — à activer explicitement en dev pour déclencher une collecte via l'API :
```bash
curl -X POST http://localhost:2026/data/collect \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD","asset_class":"metals","timeframe":"M15"}'
```
Sans `start`/`end`, la collecte est incrémentale (reprend depuis la dernière donnée connue). Avec `start`/`end` (ISO 8601), elle collecte la plage demandée.

## 10. Étape 3 — Feature Engineering & Market Context

Voir `docs/features.md` pour le détail complet. En résumé : le système calcule maintenant des features quantitatives (prix, tendance, volatilité, momentum, volume, VWAP) à partir des données historiques collectées à l'Étape 2 — sans jamais produire de décision BUY/SELL.

```bash
curl "http://localhost:2026/features/XAUUSD?asset_class=metals&timeframe=M15"
```

Nécessite d'avoir collecté de l'historique au préalable (`POST /data/collect`, Étape 2) — sinon `404`.

## 11. Endpoints disponibles

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | Ping applicatif |
| GET | `/system/status` | État agrégé : app, DB, MT5, mode |
| GET | `/mt5/status` | État du terminal MT5 |
| GET | `/mt5/account` | Infos du compte connecté |
| GET | `/markets` | Liste des symboles disponibles chez le broker |
| GET | `/markets/{symbol}` | Détail d'un symbole |
| POST | `/market-selection` | Validation d'une config utilisateur |
| GET | `/market-data/{symbol}` | Série OHLCV brute |
| GET | `/market-snapshot/{symbol}` | Photographie factuelle du marché (persistée en DB) |
| GET | `/data-quality/{symbol}` | Rapport de qualité des données |
| GET | `/market-data/{symbol}/coverage` | Couverture réelle en base (première/dernière bougie, nombre de lignes) |
| POST | `/data/collect` | Déclenche une collecte historique/incrémentale (désactivé par défaut) |
| GET | `/data/status` | Historique des derniers événements de collecte |
| GET | `/features/{symbol}` | Features quantitatives calculées (prix, tendance, volatilité, momentum, volume, VWAP) |

## 12. Architecture

Voir `docs/architecture.md`. Résumé du flux Étape 1 :

```
Market Selection (validation Pydantic)
        ↓
BrokerInterface (MT5Adapter ou MockMT5Adapter)
        ↓
MarketObserver → récupère OHLCV, orchestre la qualité
        ↓
DataQualityEngine → VALID / WARNING / INVALID
        ↓
MarketSnapshot (DTO factuel, pas de signal)
        ↓
Repositories → PostgreSQL (assets, market_data, data_quality_events)
        ↓
API FastAPI
```

## 13. Procédure de validation complète

```bash
python scripts/validate_setup.py
```

Vérifie dans l'ordre : Application → PostgreSQL → MT5/Broker → Market Selection → Market Observer → Data Quality → Market Snapshot. Sortie non-zéro si une étape échoue.

## 14. Sécurité

- Aucun secret dans le code ou les logs (le champ `mt5_password` a `repr=False`, jamais loggé).
- `.env` dans `.gitignore`.
- `TRADING_EXECUTION_ENABLED=false` par défaut, et `execute_order()` lève une exception quel que soit ce flag — double garde-fou.
- Mode `LIVE` explicitement rejeté par la validation Pydantic à cette étape.

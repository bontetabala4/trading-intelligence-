# Architecture — Étape 1

## Principe

Chaque couche ne connaît que la couche immédiatement en dessous, via une interface.
Le reste du système ne parle jamais directement à MT5 : tout passe par `BrokerInterface`.

## Couches

1. **`brokers/`** — abstraction broker. `BrokerInterface` (contrat), `MT5Adapter` (implémentation réelle, Windows + terminal requis), `MockMT5Adapter` (double déterministe, tests/CI/dev multi-OS).
2. **`core/market/`** — logique métier d'observation. `MarketSelection` (validation), `MarketObserver` (orchestration), `MarketSnapshot` (DTO factuel).
3. **`core/data/`** — `DataQualityEngine`, règles déterministes de validation OHLCV.
4. **`database/`** — modèles SQLAlchemy + repositories (pattern Repository, isole le SQL du métier) + migrations Alembic.
5. **`apps/api/`** — FastAPI. Les routes ne contiennent aucune logique métier ; elles appellent les services via dependency injection (`Depends`).
6. **`configs/`** — `Settings` (pydantic-settings), source unique de vérité pour la config, jamais de secret hardcodé.

## Garde-fou d'exécution (défense en profondeur)

Trois niveaux indépendants empêchent toute exécution réelle à l'Étape 1 :

1. `MarketSelection` rejette le mode `LIVE` au niveau validation (avant même la connexion broker).
2. `Settings.trading_execution_enabled` vaut `False` par défaut.
3. `BrokerInterface.execute_order()` lève `ExecutionDisabledError` inconditionnellement — aucun adaptateur concret ne le surcharge à cette étape.

Un attaquant ou un bug devrait contourner les trois niveaux simultanément pour déclencher un ordre réel, ce qui est structurellement impossible tant que `execute_order()` n'est pas explicitement réimplémenté dans une étape future.

## Modules vides préparés pour les étapes futures

`core/features/`, `core/regime/`, `core/strategies/`, `core/signals/`, `core/risk/`, `core/execution/` existent déjà dans l'arborescence (vides, avec `__init__.py`) pour matérialiser la chaîne cible :

```
Market Selection → Market Observer → Data Quality → Feature Engine → Macro Engine
→ Market Regime Engine → Strategy Selector → Quant Engine → ML Engine → Signal Engine
→ Risk Engine → [NO TRADE | APPROVED → Execution Engine → Broker Adapter → MT5]
```

Le Risk Engine aura, dans une étape future, un droit de veto sur toute décision d'exécution.

## Choix broker_backend : mock / native / bridge

`MetaTrader5` (le package Python) ne fonctionne que sous Windows avec un terminal installé. Pour ne pas bloquer le développement et les tests sur macOS/Linux/CI, `Settings.broker_backend` sélectionne l'implémentation :

- `mock` (défaut) : `MockMT5Adapter`, données synthétiques déterministes, aucune dépendance externe.
- `native` : `MT5Adapter` réel, nécessite Windows + terminal MT5.
- `bridge` : réservé pour une future implémentation pont réseau (RPC vers une machine Windows distante) — lève `NotImplementedError` si sélectionné à ce stade.

Cette séparation permet à l'ensemble de la suite de tests de tourner en CI Linux tout en gardant un chemin de bascule direct vers de vraies données MT5 en changeant une seule variable d'environnement.

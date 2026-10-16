# ATIP — Audit Technique Initial & État Réel du Dépôt (Phase 0)

> **Date :** 16 Octobre 2026  
> **Workspace :** `c:\Users\admin\Desktop\bonte\adaptive-trading-intelligence`  
> **Environnement :** Python 3.14 (.venv), PostgreSQL, pytest 8.3.3  
> **Branche :** `main`  
> **Statut de la suite de tests :** **213/213 tests passés (100% vert)**

---

## 1. Inventaire Exhaustif des Composants Présents

### 1.1 Backend & Modules Principaux (Python / FastAPI)
- **`apps/api/`** :
  - `main.py` : assemble les routeurs de données et le chemin décisionnel canonique versionné sous `/api/v1`.
  - Les anciennes routes `signals`, `regime` et `risk` à valeurs factices sont conservées comme code historique mais ne sont plus montées dans l'application publique.
  - `routers/execution.py` : **Volontairement non enregistré** dans `main.py` (conformément à la règle de sécurité V1 : zéro exécution réelle).
- **`core/pipeline.py`** :
  - `ATIPPipeline` : Pipeline canonique unifié orchestrant les 9 étapes :
    1. Validation qualité des données (`DataQualityEngine`)
    2. Calcul causale des indicateurs (`FeatureEngine`)
    3. Détection du régime de marché (`MarketRegimeEngine`)
    4. Évaluation et sélection des stratégies (`StrategyEngine`)
    5. Détection des opportunités (`OpportunityDetector`)
    6. Quantification du score d'opportunité (`OpportunityQuantifier`)
    7. Validation des conditions d'entrée (`OpportunityValidator`)
    8. Évaluation des limites de risque et dimensionnement (`RiskEngine`)
    9. Émission du signal final (`SignalEngine.generate_signal`)
  - `PipelineResult` : Dataclass gelée contenant tous les artefacts intermédiaires et le `risk_proposal` pour l'audit et la parité.
- **`core/strategy/`** :
  - Stratégies actives : `TrendFollowingStrategy`, `MeanReversionStrategy`. EMA 200, Breakout, Fibonacci et MTF sont présentes mais `EXPERIMENTAL` ; Pairs Trading et Market Making sont `UNSUPPORTED_DATA`.
  - Moteur unifié : `core.strategy.services.engine.StrategyEngine` (avec alias de compatibilité `StrategyEngine.py`).
- **`core/risk/`** :
  - `RiskEngine` : validation des limites du compte (drawdown journalier, exposition, nombre de positions, spread) et vérification SL/TP.
  - `PositionSizer` : gestion du mode `PERCENTAGE` et `FIXED_AMOUNT`, calcul basé sur `SymbolInfo` ou pips standard, arrondi aux steps de lot du broker.
  - `AccountState` / `OrderProposal` : modèles Pydantic immuables.
- **`core/backtest/`** :
  - `BacktestRunner` : orchestrateur de replay historique avec horloge de simulation (`SimulationClock`), isolation anti-lookahead, gestion dynamique du capital (`_update_account_after_closed_trades`, `_reset_daily_pnl_if_new_day`, `_reset_account`).
  - `VirtualOutcomeEngine` : gestion des coûts (spread, slippage, commission) et résolution des sorties (règle déterministe STOP_LOSS_FIRST en cas de bougie ambiguë).
  - `MetricsCalculator` : métriques complètes (R-multiple, win rate, profit factor, max drawdown R, décomposition par régime).
- **`core/paper_trading/`** :
  - `ForwardPaperEngine` (`core/paper_trading/forward_paper_engine.py`) : simulateur forward pas-à-pas relié au `SignalEngine` canonique avec checkpoints reproductibles (hash SHA-256).
  - `PaperBroker` : exécution virtuelle, suivi des positions, calcul des coûts et du ledger.
- **`core/monitor/` & `core/notification/`** :
  - `ContinuousMonitor` : surveillance continue des bougies clôturées.
  - `NotificationService` : interface d'envoi d'alertes avec adaptateur SMTP optionnel ; la livraison est explicitement désactivée en l'absence de configuration.
- **`brokers/mt5/`** :
  - `adapter.py` : connecteur MetaTrader 5 natif (Windows).
  - `mock_adapter.py` : connecteur mock déterministe pour tests et développement hors MT5.

---

## 2. Défauts Détectés et Corrigés en Phase 0/1

| Identifiant | Description du problème | Impact initial | Correction appliquée | Statut |
|---|---|---|---|---|
| **DEF-01** | `PipelineResult` manquait l'attribut `risk_proposal` | Échec du test d'intégration `test_backtest_forward_parity.py` | Ajout de `risk_proposal: Optional[OrderProposal] = None` sur la dataclass et propagation dans `ATIPPipeline.process()` | **RÉSOLU** |
| **DEF-02** | Doublon de code entre `engine.py` et `StrategyEngine.py` | Risque de désynchronisation de l'évaluation des stratégies | Unification sur `engine.py` ; `StrategyEngine.py` transformé en alias propre de ré-export | **RÉSOLU** |
| **DEF-03** | `VirtualTrade` manquait `volume_lots` et `risk_amount_account_currency` | `TypeError` dans `VirtualOutcomeEngine.create_trade_from_order` et tests unitaires | Ajout des champs optionnels sur `VirtualTrade` dans `core/backtest/domain.py` | **RÉSOLU** |
| **DEF-04** | `BacktestConfig` manquait `risk_mode` et `fixed_risk_amount` | `TypeError` à l'instanciation des configurations en mode montant fixe | Ajout des champs et interfaçage avec `PositionSizer` dans `BacktestRunner` | **RÉSOLU** |
| **DEF-05** | `BacktestRunner` manquait la gestion du capital dynamique | 8 tests unitaires échouaient (`AttributeError: _update_account_after_closed_trades`) | Implémentation complète de `self.account`, `_reset_account`, `_reset_daily_pnl_if_new_day` et `_update_account_after_closed_trades` | **RÉSOLU** |
| **DEF-06** | Routes publiques `/signals`, `/regime` et `/risk` renvoyaient des features/signaux factices | Une fixture pouvait être prise pour une analyse de marché | Retrait des routeurs de l'application montée ; exposition du chemin réel `/api/v1/decision/{symbol}` uniquement | **RÉSOLU** |

---

## 3. Résultats de la Suite de Tests

Suite exécutée avec `pytest` sous Python 3.14 :

```text
============================= 213 passed in 124.38s ==============================
```

- **Tests unitaires :** 184 passés (features, indicateurs, régimes, risk engine, sizer, strategies, virtual outcome, dataset validator, clock, dynamic capital).
- **Tests d'intégration :** 10 passés (parité backtest / forward, step 11 forward paper trading, cycle de vie des signaux, notifications finales).
- **Zéro test masqué ou désactivé.**

---

## 4. Éléments Manquants & Backlog Produit (Feuille de Route)

1. **Phase 1 (Finalisation) :**
   - Reste à relier des spécifications de symbole et un état de compte provenant d'un fournisseur non simulé au moteur de risque.
2. **Phase 2 — Nouvelles Stratégies & Recherche :**
   - Valider hors échantillon les stratégies EMA 200, Breakout, Fibonacci et MTF avant de les passer de `EXPERIMENTAL` à `ENABLED`.
   - Outils de validation Walk-Forward et versioning de datasets.
3. **Phase 3 — Données & Monitoring Durable :**
   - Worker persistant en tâche de fond (Celery / Redis ou thread daemon robuste) avec déduplication en base de données.
   - Un adaptateur SMTP est disponible lorsque configuré ; sa persistance, les retries et la déduplication après redémarrage restent à réaliser.
4. **Phase 4 — API Produit, Identité & Assistant IA :**
   - Préfixage des routes sous `/api/v1`.
   - Authentification JWT avec refresh tokens sécurisés et gestion de session.
   - Assistant IA de recherche (explication de signaux et de rapports) avec interface Provider, mode mock et zéro pouvoir d'exécution.
5. **Phase 5 — Application Web :**
   - Frontend Next.js + TypeScript sous `apps/web/`.
6. **Phase 6 — Application Mobile :**
   - Application Flutter sous `apps/mobile/`.
7. **Phase 7 — DevSecOps & Déploiement :**
   - CI GitHub Actions, Docker Compose durci, runbooks et sauvegardes.

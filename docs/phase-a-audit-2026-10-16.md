# ATIP — Audit technique Phase A

**Date :** 16 octobre 2026  
**Branche :** `feat/atip-product-build`  
**Dépôt :** `bontetabala4/trading-intelligence-`

## Validation initiale rapportée

Avant l'application du correctif décrit ci-dessous, l'exécution locale a terminé avec **213 tests réussis, 0 échec et 104 avertissements**, en 64,18 secondes, sur Python 3.14.5 et pytest 8.3.3. Ce résultat est la baseline pré-correctif. La suite doit être relancée après ce changement ; ce rapport ne prétend pas que la validation post-correctif a déjà réussi.

## Constats confirmés par inspection

- L'API FastAPI assemble une route décisionnelle versionnée `/api/v1/decision/{symbol}`. Les anciens routeurs `signals`, `regime` et `risk` qui utilisent des features d'exemple ne sont pas montés dans l'application actuelle.
- Le routeur `apps/api/routers/execution.py` n'est pas enregistré dans l'application montée. Néanmoins, avant correction, `core/execution/services/mt5_executor.py` contenait un appel réel à `order_send` atteignable en mode LIVE quand `TRADING_EXECUTION_ENABLED=true`.
- `core/pipeline.py` utilise par défaut un `AccountState` fictif de 10 000 et transmet `current_spread_pips=1.0` au moteur de risque.
- `core/decision/service.py` récupère `SymbolInfo` pour vérifier l'existence du symbole, mais ne le transmet pas au pipeline ; le calcul du risque peut donc tomber sur des hypothèses génériques.
- Plusieurs chemins de backtest/paper coexistent. `core/paper_trading/engine.py` contient un évaluateur explicitement provisoire, un prix d'entrée au close et des distances de risque fixes ; ce chemin ne doit pas être considéré comme équivalent au pipeline canonique sans tests ciblés.
- Les stratégies EMA200, Breakout, Fibonacci et Multi-Timeframe sont expérimentales. Pairs Trading et Market Making n'ont pas les données/mécaniques nécessaires à une validation de bout en bout dans l'état inspecté.
- Aucun projet Flutter/mobile, module dédié IA/ML/LLM ni workflow GitHub Actions n'a été trouvé dans l'arborescence inspectée.
- Le service de notification garde sa déduplication en mémoire ; celle-ci n'est pas durable après redémarrage.

## Rapports historiques examinés

- EURUSD M15 : 5 453 transactions ; taux gagnant 32,1 % ; résultat net `-1 147,3 R` ; profit factor `0,72`.
- EURUSD H1 : 1 484 transactions ; taux gagnant 33,7 % ; résultat net `-173,0 R` ; profit factor `0,84`.
- EURUSD H4 : 307 transactions ; taux gagnant 33,2 % ; résultat net `-30,4 R` ; profit factor `0,86`.

Ces valeurs proviennent des rapports déjà versionnés et n'ont pas été recalculées lors de cet audit.

## Correctif préparé par ce script

- `core/execution/services/mt5_executor.py` : le mode LIVE est refusé inconditionnellement dans la V1 ; ce chemin ne doit plus appeler `order_send`, même si le vieux flag d'environnement est activé.
- `tests/test_execution_engine.py` : un test de régression configure le flag à `true` et vérifie que le client MT5 n'est jamais appelé.

## Validation encore requise

Après application, exécuter :

```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=core --cov=brokers --cov-report=term-missing
```

Le correctif ne doit être considéré comme validé qu'après succès réel de ces commandes. Les prochaines priorités sont le contrat du Risk Engine (compte, spread et spécifications du symbole explicites), l'unification des chemins de paper trading, puis l'authentification, le Web produit, le mobile, l'IA d'assistance et la CI.

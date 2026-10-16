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

## Phase C1 — durcissement du contexte de risque (patch local)

Le patch ajoute des champs explicites `free_margin`, `daily_pnl` et `open_positions_count` au contrat de compte. Le mock les fournit comme données synthétiques ; l'adaptateur MT5 les fournit lorsque les requêtes du compte, de l'historique et des positions réussissent. Le calcul MT5 de `daily_pnl` est une approximation (transactions depuis minuit UTC + PnL flottant courant), à remplacer ensuite par une mesure de drawdown basée sur l'equity au début de journée.

Le pipeline ne crée plus par défaut un compte fictif de 10 000. Le chemin API transmet le compte, les spécifications du symbole et le spread dérivé des points du broker ; si le contexte requis est incomplet, le moteur produit une proposition rejetée `MISSING_RISK_INPUTS`, qui force `NO_TRADE`. Le backtest transmet le spread du modèle de coûts ou celui de la bougie. Les spécifications mock restent des fixtures synthétiques et ne sont pas des conditions réelles de broker.

Validation locale requise après application :

```bash
python -m pytest tests/unit/test_risk_context_safety.py tests/test_risk_engine.py tests/unit/test_decision_service.py -v
python -m pytest tests/ -v
git diff --check
git diff --stat
```

Ce document est mis à jour par le patch ; aucune validation post-patch n'est présumée avant l'exécution de ces commandes.

## Phase C2 — cotation actuelle et spread explicite (patch local)

Le contrat broker expose maintenant un `MarketQuote` facultatif (Bid/Ask horodatés). L'adaptateur MT5 lit le tick courant ; le mock expose uniquement une cotation synthétique de test. Le service de décision ignore les cotations absentes, invalides, sans fuseau horaire, trop anciennes (>60 secondes) ou excessivement futures (>5 secondes). Le pipeline strict rejette un contexte sans cotation récente et ancre les propositions BUY sur l'Ask et SELL sur le Bid. Le spread des bougies historiques n'est plus utilisé comme substitut au spread courant dans la décision API.

Le RiskEngine et les limites refusent désormais un spread absent au lieu de supposer un pip. Les tests historiques qui représentent volontairement un spread simulé le transmettent explicitement. La limite de 60 secondes est une politique prudente codée comme constante ; elle devra être configurée et surveillée lors du déploiement selon le broker et la classe d'actif.

Validation requise après application : tests ciblés, suite complète, `git diff --check`, puis revue de la sortie avant tout commit. Aucune validation n'est présumée avant exécution locale.

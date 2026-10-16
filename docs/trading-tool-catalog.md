# Catalogue des plateformes et stratégies

Ce catalogue distingue les outils connus des intégrations réellement configurées dans ATIP. Aucun élément ci-dessous n'active un ordre réel : `TRADING_EXECUTION_ENABLED` reste désactivé et les plateformes ne sont pas connectées par défaut.

| Outil | Classe d'actif | Usage envisagé | État ATIP |
| --- | --- | --- | --- |
| MetaTrader Expert Advisors | Forex / CFD | Automatisation sur graphiques | Non configuré ; aucun pont EA ajouté |
| Freqtrade | Crypto | Recherche, backtest et optimisation | Recherche uniquement ; instance externe requise |
| Hummingbot | Crypto | Market making et arbitrage | Non configuré ; carnet d'ordres requis |
| QuantConnect LEAN | Multi-actifs | Recherche quantitative et backtest | Recherche uniquement ; moteur et données non configurés |
| Cryptohopper | Crypto | Automatisation configurée | Non configuré ; aucun compte/API relié |

## Stratégies

- **Trend Following** et **Mean Reversion** sont les deux stratégies activées par défaut.
- **EMA 200 Macro Trend**, **Breakout**, **Fibonacci Pullback** et **Multi-Timeframe** sont présentes mais `EXPERIMENTAL` et donc exclues du moteur par défaut tant qu'elles n'ont pas passé les validations hors échantillon et anti-lookahead.
- **Pairs Trading / Statistical Arbitrage** est `UNSUPPORTED_DATA` : il faut deux séries synchronisées, une validation de stabilité/cointegration et un ledger à deux jambes.
- **Market Making** est `UNSUPPORTED_DATA` : des bougies OHLCV ne suffisent pas ; une source bid/ask, idéalement le carnet, la latence et le risque d'inventaire sont nécessaires.

Ce statut ne préjuge jamais de rentabilité. Toute activation doit rester une modification explicite de configuration, accompagnée de tests et d'un backtest reproductible.

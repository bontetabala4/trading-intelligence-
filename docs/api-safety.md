# Sécurité des routes API

Les anciennes routes `/signals`, `/regime` et `/risk` construisaient des indicateurs et des signaux à partir de valeurs factices. Elles ne sont plus montées par l'application FastAPI et ne font donc pas partie de l'API publique.

La route décisionnelle publique est désormais :

`GET /api/v1/decision/{symbol}`

Elle passe par le broker configuré, les bougies clôturées et `ATIPPipeline`, puis retourne la décision avec ses raisons. En configuration par défaut, le broker est `mock` : le résultat doit alors être interprété comme une démonstration, jamais comme une donnée de marché live.

`/api/v1/decisions/{symbol}` expose uniquement l'historique persistant correspondant. Aucune route d'exécution d'ordre n'est montée. Le moteur de paper trading demeure isolé du broker et le verrou `TRADING_EXECUTION_ENABLED=false` reste actif.

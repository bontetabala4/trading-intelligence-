# Feature Engineering & Market Context — Étape 3

## Vue d'ensemble

```
MarketDataRepository (Étape 2)
        ↓
FeatureEngine.bars_from_market_data()   # conversion MarketData -> OHLCVBar
        ↓
OHLCVSeries                              # wrapper trié, immuable
        ↓
FeatureRegistry.all()                    # price, trend, volatility, momentum, volume, vwap
        ↓
FeatureSet                               # dict[str, float | None] + métadonnées de traçabilité
        ↓
MarketContextBuilder                     # + DataQualityEngine
        ↓
MarketContext                            # symbol, price, features, data_quality
```

Chaque calculateur (`core/features/calculators/*.py`) ne connaît que `OHLCVSeries` — aucune dépendance à MT5, PostgreSQL ou FastAPI. Le seul point de couture avec la base de données est `FeatureEngine.bars_from_market_data()`.

## Principe : None, jamais 0

Une feature non calculable (historique insuffisant, division par zéro évitée, volume absent) vaut **explicitement `None`**, jamais `0` ou une valeur inventée. C'est vérifié par test pour chaque calculateur (`test_*_features.py`).

## Anti-look-ahead

`tests/unit/test_no_lookahead.py` vérifie, pour chaque calculateur, qu'falsifier une bougie **future** ne change jamais le résultat calculé au présent. C'est le test le plus important de cette étape (section 15) — il tourne sur tous les calculateurs enregistrés dans le registre par défaut.

`EMA` est calculée point par point de façon causale (`ema_series()`) : `ema[i]` ne dépend que de `values[0..i]`, jamais de valeurs postérieures.

## Détail par groupe de features

### Price (`price.py`)
- `open_to_close_return`, `close_to_close_return` (nécessite une bougie précédente)
- `high_low_range`, `body`, `abs_body`, `upper_wick`, `lower_wick`, `body_ratio`
- `direction` (1.0 haussière, -1.0 baissière, 0.0 doji)
- `close_to_open/high/low_distance`
- **Cas `high == low`** : `body_ratio`, `upper_wick`, `lower_wick` valent `None` (pas de division par zéro).

### Trend (`trend.py`)
- `sma_{période}`, `distance_to_sma_{période}` — périodes par défaut : `[20]`
- `ema_{période}`, `distance_to_ema_{période}`, `ema_{période}_slope` — périodes par défaut : `[20, 50, 200]`
- Périodes entièrement configurables au constructeur de `TrendFeatures`.
- **Aucune interprétation** ("tendance haussière") n'est produite — seulement des valeurs.

### Volatility (`volatility.py`)
- `true_range` : max(high-low, |high-prev_close|, |low-prev_close|)
- `atr_{période}` : moyenne mobile **simple** du True Range (pas la méthode de Wilder — choix documenté pour la simplicité/vérifiabilité, section 23 KISS). Défaut : période 14.
- `rolling_stddev_{période}` : écart-type de population des closes. Défaut : période 20.
- `relative_range` : True Range / close.

### Momentum (`momentum.py`)
- `rsi_{période}` : formule standard de Wilder simplifiée (moyenne simple des gains/pertes, pas de lissage récursif — choix documenté, cohérent avec l'ATR). Défaut : période 14. Cas particulier : série plate (aucune perte) → `100.0` si gains > 0, sinon `50.0` (ni surachat ni survente).
- `roc_{période}` : (close actuel - close il y a N périodes) / close il y a N périodes × 100. Défaut : période 10.
- `momentum_{période}` : différence brute de prix. Défaut : période 10.

### Volume (`volume.py`)
- `tick_volume`, `real_volume` : valeurs brutes de la dernière bougie — `None` si le broker ne les fournit pas (jamais inventées, section 8).
- `real_volume_available` : booléen explicite.
- `rolling_avg_tick_volume_{période}`, `rolling_avg_real_volume_{période}` : `None` si une seule bougie de la fenêtre a un volume manquant (pas de moyenne partielle silencieuse).
- `relative_tick_volume`, `relative_real_volume` : volume actuel / moyenne glissante.

### VWAP (`vwap.py`)
- Priorité : `real_volume` si disponible sur **toutes** les bougies de la fenêtre, sinon repli sur `tick_volume`, sinon `vwap_available: False`.
- Méthode : prix typique `(H+L+C)/3` pondéré par le volume choisi, fenêtre glissante (pas de VWAP de session — reporté à une étape future).
- `vwap_volume_source` indique explicitement quelle source a été utilisée (`"real_volume"` / `"tick_volume"` / `None`).
- **Limitation assumée** : approximation "volume constant sur la bougie" (pas de données tick-by-tick) ; pas de VWAP ancré ou de session.

## API

```
GET /features/{symbol}?asset_class=metals&timeframe=M15
```
Lit les 300 dernières bougies persistées (Étape 2), calcule le `MarketContext`, et retourne :
```json
{
  "status": "success",
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "timestamp": "...",
  "data_quality": "VALID",
  "price": 2650.12,
  "features": { "sma_20": ..., "rsi_14": ..., "vwap": ..., ... }
}
```
`404` si aucune donnée n'a encore été collectée pour ce symbole (redirige vers `POST /data/collect` de l'Étape 2). Ne retourne jamais `BUY`/`SELL`/`NO TRADE`.

## Limites connues

- Pas de VWAP de session/jour/ancré — glissant uniquement.
- Calculateurs testés avec des doubles PostgreSQL réels non disponibles dans le sandbox de développement (même limite qu'Étape 2) — la logique de calcul est testée réellement, l'intégration avec une vraie base PostgreSQL est à confirmer en local.
- `FeatureRegistry` ne gère pas encore les collisions de noms entre calculateurs autrement qu'un avertissement en log ("dernier gagne") — acceptable tant qu'aucun calculateur futur ne réutilise un nom existant.

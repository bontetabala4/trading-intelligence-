# Étape 8 — Signal Engine & Notification Service

## Description
Ce module finalise le pipeline analytique ATIP V1 en agrégeant l'ensemble des couches d'analyse (Market Regime, Strategy Selection, Opportunity Engine, Risk Engine) pour émettre un **Signal Final déterministe et explicable**.

## Pipeline de Génération du Signal
1. **Data Quality Gate** : Si la qualité des données n'est pas `VALID`, émission immédiate d'un `NO_TRADE` (Raison : `INVALID_DATA`).
2. **Strategy Compatibility Gate** : Si la stratégie est incompatible avec le régime de marché, émission d'un `NO_TRADE` (Raison : `STRATEGY_NOT_COMPATIBLE`).
3. **Opportunity Gate** : Validation du statut de l'opportunité (`VALID`, `UNCERTAIN`, `REJECTED`).
4. **Risk Gate** : Validation du risque (`APPROVED`, `REJECTED`, `REQUIRES_REVIEW`).
5. **Direction Gate** : Détermination de la direction (`BUY`, `SELL`, `NO_TRADE`).

## Système de Notification
- Totalement séparé du domaine d'évaluation des signaux.
- Utilise une clé déterministe d'idempotence :
  `symbol:timeframe:timestamp:direction:strategy:signal_version`
- Évite d'envoyer plusieurs fois la même notification pour le même signal.
- Les erreurs d'envoi n'altèrent pas l'état du signal généré.

## Principe Human-In-The-Loop (V1)
ATIP V1 **n'exécute aucun ordre automatique**. Les signaux constituent une aide à la décision destinée à être consultée et validée par l'utilisateur avant toute saisie manuelle sur MetaTrader 5.
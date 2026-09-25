"""
MarketCalendar — détermine si une absence de données à un instant donné
est "attendue" (marché fermé) ou "inattendue" (trou suspect à investiguer).

LIMITE ASSUMÉE (documentée en Phase D de l'Étape 2, docs/data-pipeline.md) :
ceci n'est PAS un calendrier de marché complet. Il ne connaît que la
fermeture week-end générique par classe d'actif. Il ne modélise pas les
jours fériés, les horaires de session précis (ex: NYSE 9h30-16h00 ET), ni
les demi-journées. Une classe d'actif ouverte 24/7 (crypto) n'a aucun gap
"attendu". Cette simplification est volontaire pour l'Étape 2 — un vrai
calendrier de sessions est un chantier à part entière, à traiter dans une
étape ultérieure si le besoin se confirme (ex: intégration d'actions US).
"""
from datetime import datetime, timedelta

from core.market.selection import AssetClass

# Classes d'actifs qui tradent en continu (pas de fermeture week-end connue).
_ALWAYS_OPEN = {AssetClass.CRYPTO}

# Classes d'actifs qui ferment classiquement le week-end (vendredi soir à
# dimanche soir en heure de marché — ici simplifié en jours calendaires UTC,
# ce qui peut décaler la frontière de quelques heures selon le broker).
_CLOSES_WEEKEND = {
    AssetClass.FOREX,
    AssetClass.METALS,
    AssetClass.INDICES,
    AssetClass.STOCKS,
    AssetClass.COMMODITIES,
    AssetClass.CURRENCIES_FX,
    AssetClass.BONDS_RATES,
    AssetClass.FUTURES,
    AssetClass.OTHER,
}


class MarketCalendar:
    """Calendrier simplifié — voir limite documentée en tête de fichier."""

    def closed_duration(
        self, asset_class: AssetClass, start: datetime, end: datetime
    ) -> timedelta:
        """
        Durée cumulée de fermeture "connue" (week-end) à l'intérieur de
        [start, end]. Utilisé pour classifier un trou : si la quasi-totalité
        du trou coïncide avec une fermeture connue, il est "attendu".
        """
        if asset_class in _ALWAYS_OPEN or asset_class not in _CLOSES_WEEKEND:
            return timedelta(0)
        if start >= end:
            return timedelta(0)

        total = timedelta(0)
        cursor = start
        while cursor < end:
            next_midnight = datetime(
                cursor.year, cursor.month, cursor.day, tzinfo=cursor.tzinfo
            ) + timedelta(days=1)
            day_end = min(next_midnight, end)
            if cursor.weekday() >= 5:  # samedi=5, dimanche=6
                total += day_end - cursor
            cursor = day_end
        return total

    def is_expected_closed(self, asset_class: AssetClass, timestamp: datetime) -> bool:
        """True si l'instant précis donné tombe un jour de fermeture connue."""
        if asset_class in _ALWAYS_OPEN:
            return False
        if asset_class in _CLOSES_WEEKEND:
            return timestamp.weekday() >= 5
        return False

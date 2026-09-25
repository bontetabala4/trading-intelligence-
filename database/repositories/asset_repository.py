"""Repository pour l'entité Asset — isole les requêtes SQL du reste du code."""
from sqlalchemy.orm import Session

from database.models import Asset


class AssetRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_symbol(self, symbol: str) -> Asset | None:
        return self._db.query(Asset).filter(Asset.symbol == symbol).first()

    def get_or_create(
        self,
        symbol: str,
        asset_class: str,
        broker: str = "mt5",
        **contract_specs,
    ) -> Asset:
        """
        contract_specs : champs optionnels de l'Étape 2 (base_currency,
        quote_currency, contract_type, tick_size, tick_value, point, digits,
        volume_min, volume_max, volume_step). Ignorés silencieusement si non
        fournis — un Asset créé à l'Étape 1 reste valide sans eux.
        """
        asset = self.get_by_symbol(symbol)
        if asset:
            return asset
        asset = Asset(symbol=symbol, asset_class=asset_class, broker=broker, **contract_specs)
        self._db.add(asset)
        self._db.commit()
        self._db.refresh(asset)
        return asset

    def list_all(self) -> list[Asset]:
        return self._db.query(Asset).all()

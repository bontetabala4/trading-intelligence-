
from brokers.base.interface import OHLCVBar, Timeframe
from core.data.quality_engine import DataQualityEngine, DataQualityReport
from core.features.models import FeatureSet, MarketContext
from core.features.services.feature_engine import FeatureEngine
from core.market.selection import AssetClass


class MarketContextBuilder:
    def __init__(
        self,
        feature_engine: FeatureEngine | None = None,
        quality_engine: DataQualityEngine | None = None,
    ) -> None:
        self._feature_engine = feature_engine or FeatureEngine()
        self._quality_engine = quality_engine or DataQualityEngine()

    def build(
        self,
        symbol: str,
        asset_class: AssetClass,
        timeframe: Timeframe,
        bars: list[OHLCVBar],
    ) -> MarketContext:
        quality = self._quality_engine.evaluate(
            bars,
            timeframe,
            asset_class,
        )

        feature_set = self._feature_engine.compute_feature_set(
            symbol,
            timeframe,
            bars,
        )

        last_bar = max(bars, key=lambda b: b.timestamp)

        return MarketContext(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            timestamp=last_bar.timestamp,
            price=last_bar.close,
            features=feature_set,
            data_quality=quality,
        )
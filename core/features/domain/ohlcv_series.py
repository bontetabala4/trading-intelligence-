"""
OHLCVSeries — wrapper léger autour d'une liste d'OHLCVBar triée
chronologiquement. Centralise les vérifications communes ("assez de
données ?", "pas de trou dans l'indexation ?") pour que chaque calculateur
n'ait pas à les réimplémenter (DRY, section 23).

Ce module ne connaît ni MT5, ni PostgreSQL, ni FastAPI — uniquement
OHLCVBar (déjà générique depuis l'Étape 1/2).
"""
from dataclasses import dataclass

from brokers.base.interface import OHLCVBar


@dataclass(frozen=True)
class OHLCVSeries:
    bars: tuple[OHLCVBar, ...]  # immuable — une feature ne doit jamais muter sa source

    @classmethod
    def from_bars(cls, bars: list[OHLCVBar]) -> "OHLCVSeries":
        # Tri défensif : garantit qu'aucun calculateur ne peut accidentellement
        # lire une bougie future avant une bougie passée (section 15, anti-look-ahead).
        sorted_bars = tuple(sorted(bars, key=lambda b: b.timestamp))
        return cls(bars=sorted_bars)

    def __len__(self) -> int:
        return len(self.bars)

    def has_min_length(self, min_length: int) -> bool:
        return len(self.bars) >= min_length

    def closes(self) -> list[float]:
        return [b.close for b in self.bars]

    def highs(self) -> list[float]:
        return [b.high for b in self.bars]

    def lows(self) -> list[float]:
        return [b.low for b in self.bars]

    def opens(self) -> list[float]:
        return [b.open for b in self.bars]

    def last(self) -> OHLCVBar | None:
        return self.bars[-1] if self.bars else None

    def up_to(self, index: int) -> "OHLCVSeries":
        """
        Sous-série contenant uniquement les bougies [0, index] (incluse).
        Outil explicite pour les tests anti-look-ahead : calculer une feature
        sur up_to(i) ne doit jamais dépendre de bars[i+1:].
        """
        return OHLCVSeries(bars=self.bars[: index + 1])

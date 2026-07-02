import json
import secrets
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "assets" / "cards"


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    name_en: str
    arcana: str
    upright: str
    reversed: str
    suit: str | None = None

    @property
    def image_path(self) -> Path:
        return CARDS_DIR / f"{self.id}.jpg"


@dataclass(frozen=True)
class DrawnCard:
    card: Card
    is_reversed: bool

    @property
    def title(self) -> str:
        return f"{self.card.name}{' (перевёрнутая)' if self.is_reversed else ''}"

    @property
    def meaning(self) -> str:
        return self.card.reversed if self.is_reversed else self.card.upright


def _load() -> list[Card]:
    data = json.loads((ROOT / "data" / "deck.json").read_text(encoding="utf-8"))
    cards = [Card(**c) for c in data["cards"]]
    assert len(cards) == 78
    return cards


DECK: list[Card] = _load()
CARD_BY_ID: dict[str, Card] = {c.id: c for c in DECK}
REVERSED_CHANCE = 0.30  # доля перевёрнутых карт


def draw(n: int) -> list[DrawnCard]:
    """Тянет n уникальных карт криптографическим ГСЧ."""
    rng = secrets.SystemRandom()
    cards = rng.sample(DECK, n)
    return [DrawnCard(c, rng.random() < REVERSED_CHANCE) for c in cards]

from dataclasses import dataclass

from bot.config import config


@dataclass(frozen=True)
class Slot:
    """Позиция карты в раскладе. Координаты в единицах ширины/высоты карты."""

    label: str
    x: float
    y: float
    cross: bool = False  # карта лежит поперёк (кельтский крест, позиция 2)


@dataclass(frozen=True)
class Spread:
    key: str
    title: str
    emoji: str
    description: str
    price: int
    slots: tuple[Slot, ...]

    @property
    def num_cards(self) -> int:
        return len(self.slots)


SPREADS: dict[str, Spread] = {
    s.key: s
    for s in [
        Spread(
            key="one",
            title="Одна карта",
            emoji="🃏",
            description="Быстрый и ёмкий ответ на один вопрос.",
            price=config.price_one,
            slots=(Slot("Ответ", 0, 0),),
        ),
        Spread(
            key="three",
            title="Прошлое — Настоящее — Будущее",
            emoji="🌗",
            description="Как ситуация развивалась, где она сейчас и куда движется.",
            price=config.price_three,
            slots=(
                Slot("Прошлое", 0, 0),
                Slot("Настоящее", 1.15, 0),
                Slot("Будущее", 2.30, 0),
            ),
        ),
        Spread(
            key="relationship",
            title="Отношения",
            emoji="💞",
            description="Вы, партнёр, что происходит между вами и совет карт.",
            price=config.price_relationship,
            slots=(
                Slot("Вы", 0, 0),
                Slot("Между вами", 1.15, 0),
                Slot("Партнёр", 2.30, 0),
                Slot("Совет", 3.45, 0),
            ),
        ),
        Spread(
            key="celtic",
            title="Кельтский крест",
            emoji="✨",
            description="Глубокий разбор ситуации по 10 позициям — классика Таро.",
            price=config.price_celtic,
            # крест слева, посох компактным блоком 2x2 справа — держим
            # пропорции кадра, чтобы Telegram не обрезал гифку
            slots=(
                Slot("Суть ситуации", 1.3, 1.15),
                Slot("Что помогает или мешает", 1.3, 1.15, cross=True),
                Slot("Основание", 1.3, 2.30),
                Slot("Недавнее прошлое", 0, 1.15),
                Slot("Возможный итог", 1.3, 0),
                Slot("Ближайшее будущее", 2.6, 1.15),
                Slot("Вы сами", 4.15, 1.72),
                Slot("Окружение", 5.30, 1.72),
                Slot("Надежды и страхи", 4.15, 0.58),
                Slot("Итог", 5.30, 0.58),
            ),
        ),
    ]
}

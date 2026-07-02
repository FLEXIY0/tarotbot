from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.spreads import SPREADS

BTN_DAILY = "🌞 Карта дня"
BTN_SPREADS = "🔮 Расклады"
BTN_HISTORY = "📜 История"
BTN_HELP = "ℹ️ Помощь"

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_DAILY), KeyboardButton(text=BTN_SPREADS)],
        [KeyboardButton(text=BTN_HISTORY), KeyboardButton(text=BTN_HELP)],
    ],
    resize_keyboard=True,
)


def spreads_catalog() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{s.emoji} {s.title} — {s.price} ⭐",
            callback_data=f"spread:{s.key}",
        )]
        for s in SPREADS.values()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_question() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сделать расклад без вопроса", callback_data="q:skip")],
        [InlineKeyboardButton(text="✖️ Отмена", callback_data="q:cancel")],
    ])


def reveal_kb(reading_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Раскрыть толкование", callback_data=f"reveal:{reading_id}")]
    ])


def clarify_kb(reading_id: int, free_left: int, price: int) -> InlineKeyboardMarkup:
    if free_left > 0:
        text = f"🔍 Уточнить бесплатно (осталось {free_left})"
    else:
        text = f"🔍 Уточнить за {price} ⭐"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"clarify:{reading_id}")],
        [InlineKeyboardButton(text="🔮 Новый расклад", callback_data="menu:spreads")],
    ])


def onboarding_skip(step: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data=f"onb_skip:{step}")]
    ])


def daily_upsell() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Разобрать свой вопрос", callback_data="menu:spreads")]
    ])

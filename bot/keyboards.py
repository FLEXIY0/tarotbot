from urllib.parse import quote

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot import runtime
from bot.spreads import SPREADS

SHARE_TEXT = "🔮 Мне тут карты Таро разложили с настоящим ритуалом — попробуй, карта дня бесплатная"


def _share_button(tg_id: int) -> InlineKeyboardButton:
    link = f"https://t.me/{runtime.bot_username}?start={tg_id}"
    return InlineKeyboardButton(
        text="📤 Поделиться с другом",
        url=f"https://t.me/share/url?url={quote(link)}&text={quote(SHARE_TEXT)}",
    )

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


def clarify_kb(reading_id: int, free_left: int, price: int, tg_id: int) -> InlineKeyboardMarkup:
    if free_left > 0:
        text = f"🔍 Уточнить бесплатно (осталось {free_left})"
    else:
        text = f"🔍 Уточнить за {price} ⭐"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"clarify:{reading_id}")],
        [InlineKeyboardButton(text="🔮 Новый расклад", callback_data="menu:spreads")],
        [_share_button(tg_id)],
    ])


def shared_reading_kb(tg_id: int) -> InlineKeyboardMarkup:
    """Остаётся под гифкой после раскрытия толкования."""
    return InlineKeyboardMarkup(inline_keyboard=[[_share_button(tg_id)]])


def onboarding_skip(step: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data=f"onb_skip:{step}")]
    ])


def daily_upsell(remind_on: bool = False, tg_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🔮 Разобрать свой вопрос", callback_data="menu:spreads")]]
    if remind_on:
        rows.append([InlineKeyboardButton(text="🔕 Отключить утренние напоминания", callback_data="remind:off")])
    else:
        rows.append([InlineKeyboardButton(text="🔔 Напоминать о карте дня по утрам", callback_data="remind:on")])
    if tg_id:
        rows.append([_share_button(tg_id)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reminder_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌞 Вытянуть карту дня", callback_data="daily:go")],
        [InlineKeyboardButton(text="🔕 Больше не напоминать", callback_data="remind:off")],
    ])

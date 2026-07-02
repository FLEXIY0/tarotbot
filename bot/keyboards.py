from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.spreads import SPREADS

BTN_DAILY = "🌙 Карта дня"
BTN_SPREADS = "🔮 Расклады"
BTN_HISTORY = "📜 История"
BTN_HELP = "🕯 Помощь"

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_DAILY), KeyboardButton(text=BTN_SPREADS)],
        [KeyboardButton(text=BTN_HISTORY), KeyboardButton(text=BTN_HELP)],
    ],
    resize_keyboard=True,
)


def _share_button(query: str) -> InlineKeyboardButton:
    """Инлайн-шеринг: по нажатию открывается выбор чата, туда уходит сам расклад."""
    return InlineKeyboardButton(text="💫 Отправить другу", switch_inline_query=query)


def spreads_catalog() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{s.emoji} {s.title} · {s.price} ⭐", callback_data=f"spread:{s.key}")]
        for s in SPREADS.values()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_question() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без вопроса", callback_data="q:skip")],
        [InlineKeyboardButton(text="Отмена", callback_data="q:cancel")],
    ])


def reveal_kb(reading_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Раскрыть толкование", callback_data=f"reveal:{reading_id}")]
    ])


def shared_reading_kb(reading_id: int) -> InlineKeyboardMarkup:
    """Остаётся под гифкой после раскрытия толкования."""
    return InlineKeyboardMarkup(inline_keyboard=[[_share_button(f"r{reading_id}")]])


def clarify_kb(reading_id: int, free_left: int, price: int) -> InlineKeyboardMarkup:
    if free_left > 0:
        text = f"🔍 Уточнить · бесплатно (осталось {free_left})"
    else:
        text = f"🔍 Уточнить · {price} ⭐"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"clarify:{reading_id}")],
        [InlineKeyboardButton(text="🔮 Новый расклад", callback_data="menu:spreads")],
        [_share_button(f"r{reading_id}")],
    ])


def onboarding_skip(step: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data=f"onb_skip:{step}")]
    ])


def daily_upsell(remind_on: bool = False, share_query: str | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🔮 Разобрать свой вопрос", callback_data="menu:spreads")]]
    if remind_on:
        rows.append([InlineKeyboardButton(text="🔕 Отключить утренние напоминания", callback_data="remind:off")])
    else:
        rows.append([InlineKeyboardButton(text="🔔 Напоминать по утрам", callback_data="remind:on")])
    if share_query:
        rows.append([_share_button(share_query)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reminder_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌙 Вытянуть карту дня", callback_data="daily:go")],
        [InlineKeyboardButton(text="🔕 Больше не напоминать", callback_data="remind:off")],
    ])

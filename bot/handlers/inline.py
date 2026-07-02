"""Инлайн-шеринг: пользователь отправляет свой расклад другу в любой чат.

Требует включённого inline-режима у бота (@BotFather -> /setinline).
"""

import html
import json
import logging

from aiogram import Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedMpeg4Gif,
    InlineQueryResultCachedPhoto,
    InputTextMessageContent,
)

from bot import runtime
from bot.db import db
from bot.deck import CARD_BY_ID
from bot.spreads import SPREADS

router = Router(name="inline")
log = logging.getLogger(__name__)


def _invite_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Сделать свой расклад", url=f"https://t.me/{runtime.bot_username}")
    ]])


def _invite_article() -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id="invite",
        title="Пригласить в Аркану",
        description="Расклады Таро с живым ритуалом, карта дня — бесплатно",
        input_message_content=InputTextMessageContent(
            message_text=(
                "Мне тут карты Таро разложили с настоящим ритуалом — попробуй, "
                f"карта дня бесплатная: @{runtime.bot_username}"
            )
        ),
    )


@router.inline_query()
async def share_reading(q: InlineQuery) -> None:
    query = (q.query or "").strip()
    results: list = []

    if query.startswith("r") and query[1:].isdigit():
        reading = await db.get_reading(int(query[1:]))
        user = await db.get_or_create_user(q.from_user.id)
        if reading and reading["user_id"] == user["id"] and reading.get("media_file_id"):
            spread = SPREADS.get(reading["type"])
            cards = json.loads(reading["cards_json"])
            lines = [f"<b>{spread.title if spread else reading['type']}</b>"]
            if reading["question"]:
                lines.append(f"<i>{html.escape(reading['question'][:120])}</i>")
            lines.append("")
            for i, c in enumerate(cards):
                card = CARD_BY_ID[c["id"]]
                label = spread.slots[i].label if spread and i < len(spread.slots) else f"Карта {i + 1}"
                lines.append(f"{label} — {card.name}{' (перевёрнутая)' if c['reversed'] else ''}")
            caption = "\n".join(lines)[:1024]
            common = dict(
                id=f"r{reading['id']}",
                caption=caption,
                parse_mode="HTML",
                reply_markup=_invite_kb(),
            )
            if reading.get("media_type") == "photo":
                results.append(InlineQueryResultCachedPhoto(photo_file_id=reading["media_file_id"], **common))
            else:
                results.append(
                    InlineQueryResultCachedMpeg4Gif(mpeg4_file_id=reading["media_file_id"], **common)
                )

    elif query.startswith("d:"):
        # карта дня: d:<card_id>:<u|r>
        parts = query.split(":")
        if len(parts) == 3 and parts[1] in CARD_BY_ID:
            file_id = await db.cache_get(f"dailyimg:{parts[1]}:{parts[2]}")
            if file_id:
                card = CARD_BY_ID[parts[1]]
                rev = " (перевёрнутая)" if parts[2] == "r" else ""
                results.append(InlineQueryResultCachedPhoto(
                    id=query.replace(":", "_"),
                    photo_file_id=file_id,
                    caption=f"Моя карта дня — <b>{card.name}</b>{rev}",
                    parse_mode="HTML",
                    reply_markup=_invite_kb(),
                ))

    results.append(_invite_article())
    await q.answer(results, cache_time=10, is_personal=True)

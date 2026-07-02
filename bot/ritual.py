"""«Ритуал» выдачи расклада одним сообщением: гифка с подписью и кнопкой.

Видео рендерится в отдельном потоке; при сбое ffmpeg то же сообщение уходит
статичным коллажем — пользователь после оплаты получает результат всегда.
"""

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message

from bot.db import db
from bot.deck import DrawnCard
from bot.spreads import Spread
from bot.video import render_collage_jpeg, render_reading_video

log = logging.getLogger(__name__)


def reading_caption(drawn: list[DrawnCard], spread: Spread, question: str | None) -> str:
    lines = [f"{spread.emoji} <b>{spread.title}</b>"]
    if question:
        import html

        lines.append(f"<i>{html.escape(question[:150])}</i>")
    lines.append("")
    lines.extend(f"▫️ {slot.label} — {dc.title}" for slot, dc in zip(spread.slots, drawn))
    return "\n".join(lines)[:1024]


async def send_reading_media(
    bot: Bot,
    chat_id: int,
    drawn: list[DrawnCard],
    spread: Spread,
    subtitle: str = "",
    caption: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
    cache_key: str | None = None,
) -> Message | None:
    caption = caption or reading_caption(drawn, spread, None)

    cached = await db.cache_get(cache_key) if cache_key else None
    if cached:
        try:
            return await bot.send_animation(chat_id, cached, caption=caption, reply_markup=reply_markup)
        except Exception:
            log.warning("Кэшированный file_id %s не сработал, перерендериваю", cache_key)

    video_path: Path | None = await asyncio.to_thread(render_reading_video, drawn, spread, subtitle)
    if video_path is not None:
        try:
            sent = await bot.send_animation(
                chat_id, FSInputFile(video_path), caption=caption, reply_markup=reply_markup
            )
            if cache_key:
                media = sent.animation or sent.video or sent.document
                if media:
                    await db.cache_set(cache_key, media.file_id)
            return sent
        except Exception:
            log.exception("Не удалось отправить видео, откатываюсь на коллаж")
        finally:
            video_path.unlink(missing_ok=True)

    collage = await asyncio.to_thread(render_collage_jpeg, drawn, spread, subtitle)
    try:
        return await bot.send_photo(chat_id, FSInputFile(collage), caption=caption, reply_markup=reply_markup)
    except Exception:
        log.exception("Не удалось отправить и коллаж")
        return None
    finally:
        collage.unlink(missing_ok=True)

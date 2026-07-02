"""«Ритуал» выдачи расклада: видео-анимация переворота + коллаж на память.

Видео рендерится в отдельном потоке, при сбое ffmpeg пользователь гарантированно
получает статичный коллаж. file_id закэшированных видео переиспользуется бесплатно.
"""

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, Message

from bot.db import db
from bot.deck import DrawnCard
from bot.spreads import Spread
from bot.video import render_collage_jpeg, render_reading_video

log = logging.getLogger(__name__)


async def send_reading_media(
    bot: Bot,
    chat_id: int,
    drawn: list[DrawnCard],
    spread: Spread,
    subtitle: str = "",
    cache_key: str | None = None,
    with_collage: bool = True,
) -> None:
    caption = "\n".join(
        f"• {slot.label}: {dc.title}" for slot, dc in zip(spread.slots, drawn)
    )
    caption = f"{spread.emoji} {spread.title}\n{caption}"[:1024]

    cached = await db.cache_get(cache_key) if cache_key else None
    if cached:
        try:
            await bot.send_animation(chat_id, cached, caption=caption)
            return
        except Exception:
            log.warning("Кэшированный file_id %s не сработал, перерендериваю", cache_key)

    video_path: Path | None = await asyncio.to_thread(render_reading_video, drawn, spread, subtitle)
    sent_video: Message | None = None
    if video_path is not None:
        try:
            sent_video = await bot.send_animation(chat_id, FSInputFile(video_path), caption=caption)
        except Exception:
            log.exception("Не удалось отправить видео, откатываюсь на коллаж")
        finally:
            video_path.unlink(missing_ok=True)

    if sent_video and cache_key:
        media = sent_video.animation or sent_video.video or sent_video.document
        if media:
            await db.cache_set(cache_key, media.file_id)

    if with_collage or sent_video is None:
        collage = await asyncio.to_thread(render_collage_jpeg, drawn, spread, subtitle)
        try:
            await bot.send_photo(
                chat_id,
                FSInputFile(collage),
                caption=None if sent_video else caption,
            )
        finally:
            collage.unlink(missing_ok=True)

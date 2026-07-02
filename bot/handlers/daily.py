import asyncio
import tempfile
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot import keyboards as kb
from bot.config import config
from bot.db import db
from bot.deck import draw
from bot.llm import interpreter
from bot.render import render_daily_card
from bot.video import render_daily_video
from bot.textutil import md_bold_to_html

router = Router(name="daily")


def _today() -> str:
    return datetime.now(ZoneInfo(config.tz)).date().isoformat()


_in_flight: set[int] = set()


async def send_daily(bot: Bot, chat_id: int, tg_id: int) -> None:
    if tg_id in _in_flight:  # дедуп двойного тапа
        return
    _in_flight.add(tg_id)
    try:
        await _send_daily(bot, chat_id, tg_id)
    finally:
        _in_flight.discard(tg_id)


async def _send_daily(bot: Bot, chat_id: int, tg_id: int) -> None:
    user = await db.get_or_create_user(tg_id)
    today = _today()
    remind_on = bool(user.get("remind_daily"))
    if user.get("daily_card_date") == today:
        await bot.send_message(
            chat_id,
            "🌙 Карту дня ты уже получил(а) сегодня — новая появится после полуночи.\n"
            "А пока можно разобрать конкретный вопрос в «Раскладах».",
            reply_markup=kb.daily_upsell(remind_on),
        )
        return

    await db.update_user(tg_id, daily_card_date=today)
    dc = draw(1)[0]
    orientation = "r" if dc.is_reversed else "u"
    status = await bot.send_message(chat_id, "🎴 Тасую колоду и тяну твою карту дня…")
    with suppress(Exception):
        await bot.send_chat_action(chat_id, "upload_video")
    date_str = datetime.now(ZoneInfo(config.tz)).strftime("%d.%m.%Y")
    anim_key = f"dailyanim:{dc.card.id}:{orientation}"

    # «живая» карта и текст готовятся параллельно, уходят одним сообщением
    text, cached = await asyncio.gather(
        interpreter.interpret_daily(dc, user.get("name")),
        db.cache_get(anim_key),
    )
    caption = f"<blockquote>{md_bold_to_html(text)}</blockquote>"
    markup = kb.daily_upsell(remind_on, share_query=f"d:{dc.card.id}:{orientation}")

    sent = None
    if cached:
        with suppress(Exception):
            sent = await bot.send_animation(chat_id, cached, caption=caption, reply_markup=markup)
    if sent is None:
        video = await asyncio.to_thread(render_daily_video, dc, date_str)
        if video is not None:
            try:
                sent = await bot.send_animation(
                    chat_id, FSInputFile(video), caption=caption, reply_markup=markup
                )
                media = sent.animation or sent.video or sent.document
                if media:
                    await db.cache_set(anim_key, media.file_id)
            except Exception:
                sent = None
            finally:
                video.unlink(missing_ok=True)
    if sent is None:  # fallback: статичная открытка
        img = await asyncio.to_thread(render_daily_card, dc, date_str)
        path = Path(tempfile.mkstemp(suffix=".jpg", prefix="daily_")[1])
        try:
            await asyncio.to_thread(img.save, path, "JPEG", quality=90)
            sent = await bot.send_photo(chat_id, FSInputFile(path), caption=caption, reply_markup=markup)
        finally:
            path.unlink(missing_ok=True)
        if sent.photo:
            await db.cache_set(f"dailyimg:{dc.card.id}:{orientation}", sent.photo[-1].file_id)
    with suppress(Exception):
        await status.delete()


@router.message(Command("daily"))
@router.message(F.text == kb.BTN_DAILY)
async def daily_card(message: Message) -> None:
    assert message.from_user and message.bot
    await send_daily(message.bot, message.chat.id, message.from_user.id)


@router.callback_query(F.data == "daily:go")
async def daily_from_reminder(callback: CallbackQuery) -> None:
    assert callback.from_user and callback.bot and isinstance(callback.message, Message)
    await callback.answer()
    with suppress(Exception):
        await callback.message.edit_reply_markup(reply_markup=None)
    await send_daily(callback.bot, callback.message.chat.id, callback.from_user.id)


@router.callback_query(F.data.in_({"remind:on", "remind:off"}))
async def toggle_reminder(callback: CallbackQuery) -> None:
    assert callback.data and callback.from_user and isinstance(callback.message, Message)
    on = callback.data == "remind:on"
    await db.update_user(callback.from_user.id, remind_daily=int(on))
    await callback.answer(
        "Буду присылать карту дня каждое утро." if on else "Напоминания отключены.",
        show_alert=False,
    )
    with suppress(Exception):
        if callback.message.photo:
            await callback.message.edit_reply_markup(reply_markup=kb.daily_upsell(on))
        else:
            await callback.message.edit_reply_markup(reply_markup=None)


async def reminder_loop(bot: Bot) -> None:
    """Утренняя рассылка «карта дня ждёт» для подписавшихся."""
    while True:
        now = datetime.now(ZoneInfo(config.tz))
        if now.hour == config.reminder_hour:
            today = now.date().isoformat()
            for tg_id in await db.users_to_remind(today):
                await db.mark_reminded(tg_id, today)
                with suppress(Exception):
                    await bot.send_message(
                        tg_id,
                        "🌙 Доброе утро! Твоя карта дня уже ждёт в колоде.",
                        reply_markup=kb.reminder_kb(),
                    )
                await asyncio.sleep(0.1)
        await asyncio.sleep(300)
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from bot import keyboards as kb
from bot.config import config
from bot.db import db
from bot.deck import draw
from bot.llm import interpreter
from bot.render import render_daily_card
from bot.textutil import md_bold_to_html

router = Router(name="daily")


def _today() -> str:
    return datetime.now(ZoneInfo(config.tz)).date().isoformat()


@router.message(Command("daily"))
@router.message(F.text == kb.BTN_DAILY)
async def daily_card(message: Message) -> None:
    assert message.from_user and message.bot
    user = await db.get_or_create_user(message.from_user.id)
    today = _today()
    if user.get("daily_card_date") == today:
        await message.answer(
            "🌙 Карту дня ты уже получил(а) сегодня — новая будет после полуночи.\n"
            "А пока можно разобрать конкретный вопрос в разделе «🔮 Расклады».",
            reply_markup=kb.daily_upsell(),
        )
        return

    await db.update_user(message.from_user.id, daily_card_date=today)
    dc = draw(1)[0]
    orientation = "r" if dc.is_reversed else "u"
    await message.answer("🎴 Тасую колоду и тяну твою карту дня…")
    date_str = datetime.now(ZoneInfo(config.tz)).strftime("%d.%m.%Y")
    cache_key = f"dailyimg:{dc.card.id}:{orientation}"
    cached = await db.cache_get(cache_key)
    if cached:
        sent = await message.answer_photo(cached)
    else:
        img = await asyncio.to_thread(render_daily_card, dc, date_str)
        path = Path(tempfile.mkstemp(suffix=".jpg", prefix="daily_")[1])
        try:
            await asyncio.to_thread(img.save, path, "JPEG", quality=90)
            sent = await message.answer_photo(FSInputFile(path))
        finally:
            path.unlink(missing_ok=True)
        if sent.photo:
            await db.cache_set(cache_key, sent.photo[-1].file_id)
    text = await interpreter.interpret_daily(dc, user.get("name"))
    await message.answer(
        md_bold_to_html(text) + "\n\n💫 Хочешь разобрать конкретный вопрос? Загляни в «🔮 Расклады».",
        reply_markup=kb.daily_upsell(),
    )

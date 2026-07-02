from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot import keyboards as kb
from bot.config import config
from bot.db import db
from bot.deck import draw
from bot.llm import interpreter
from bot.ritual import send_reading_media
from bot.spreads import Slot, Spread
from bot.textutil import md_bold_to_html

router = Router(name="daily")

DAILY_SPREAD = Spread(
    key="daily",
    title="Карта дня",
    emoji="🌞",
    description="Послание дня",
    price=0,
    slots=(Slot("Послание дня", 0, 0),),
)


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
    await send_reading_media(
        message.bot,
        message.chat.id,
        [dc],
        DAILY_SPREAD,
        cache_key=f"daily:{dc.card.id}:{orientation}",
        with_collage=False,
    )
    text = await interpreter.interpret_daily(dc, user.get("name"))
    await message.answer(
        md_bold_to_html(text) + "\n\n💫 Хочешь разобрать конкретный вопрос? Загляни в «🔮 Расклады».",
        reply_markup=kb.daily_upsell(),
    )

import html
import json
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import keyboards as kb
from bot.db import db
from bot.deck import CARD_BY_ID
from bot.spreads import SPREADS
from bot.textutil import md_bold_to_html

router = Router(name="history")


@router.message(Command("history"))
@router.message(F.text == kb.BTN_HISTORY)
async def show_history(message: Message) -> None:
    assert message.from_user
    user = await db.get_or_create_user(message.from_user.id)
    readings = await db.recent_readings(user["id"], limit=10)
    if not readings:
        await message.answer("📜 Пока пусто. Начни с карты дня или сделай первый расклад! 🔮")
        return
    rows = []
    for r in readings:
        spread = SPREADS.get(r["type"])
        title = spread.title if spread else r["type"]
        date = datetime.fromisoformat(r["created_at"]).strftime("%d.%m")
        q = f" · {r['question'][:25]}…" if r["question"] and len(r["question"]) > 25 else (
            f" · {r['question']}" if r["question"] else ""
        )
        rows.append([InlineKeyboardButton(text=f"{date} · {title}{q}", callback_data=f"hist:{r['id']}")])
    await message.answer(
        "📜 <b>Твои расклады</b> — нажми, чтобы перечитать:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("hist:"))
async def show_reading(callback: CallbackQuery) -> None:
    assert callback.data and callback.from_user and isinstance(callback.message, Message)
    reading = await db.get_reading(int(callback.data.split(":", 1)[1]))
    user = await db.get_or_create_user(callback.from_user.id)
    if not reading or reading["user_id"] != user["id"]:
        await callback.answer("Расклад не найден", show_alert=True)
        return
    await callback.answer()
    spread = SPREADS.get(reading["type"])
    cards = json.loads(reading["cards_json"])
    lines = [f"🔮 <b>{spread.title if spread else reading['type']}</b>"]
    if reading["question"]:
        lines.append(f"<i>Вопрос: {html.escape(reading['question'])}</i>")
    for i, c in enumerate(cards):
        card = CARD_BY_ID[c["id"]]
        label = spread.slots[i].label if spread and i < len(spread.slots) else f"Карта {i + 1}"
        lines.append(f"• {label}: {card.name}{' (перевёрнутая)' if c['reversed'] else ''}")
    if reading["interpretation"]:
        lines.append("\n" + md_bold_to_html(reading["interpretation"]))
    await callback.message.answer("\n".join(lines)[:4000])

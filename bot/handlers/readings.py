"""Платные расклады: каталог -> вопрос -> счёт в Stars -> ритуал -> интерпретация -> уточнения."""

import json
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from bot import keyboards as kb
from bot.config import config
from bot.db import db
from bot.deck import CARD_BY_ID, DrawnCard, draw
from bot.llm import interpreter
from bot.ritual import send_reading_media
from bot.spreads import SPREADS
from bot.textutil import md_bold_to_html

router = Router(name="readings")
log = logging.getLogger(__name__)


class ReadingFlow(StatesGroup):
    question = State()          # ждём вопрос к раскладу


class ClarifyFlow(StatesGroup):
    question = State()          # ждём уточняющий вопрос


# --- каталог ---


@router.message(Command("spreads"))
@router.message(F.text == kb.BTN_SPREADS)
async def catalog(message: Message) -> None:
    lines = ["🔮 <b>Расклады</b>\n"]
    for s in SPREADS.values():
        lines.append(f"{s.emoji} <b>{s.title}</b> ({s.num_cards} карт{'ы' if s.num_cards < 5 else ''}) — {s.price} ⭐\n<i>{s.description}</i>\n")
    lines.append("Выбери расклад:")
    await message.answer("\n".join(lines), reply_markup=kb.spreads_catalog())


@router.callback_query(F.data == "menu:spreads")
async def catalog_cb(callback: CallbackQuery) -> None:
    assert isinstance(callback.message, Message)
    await callback.answer()
    await catalog(callback.message)


@router.callback_query(F.data.startswith("spread:"))
async def pick_spread(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.data and isinstance(callback.message, Message)
    spread = SPREADS.get(callback.data.split(":", 1)[1])
    if not spread:
        await callback.answer("Расклад не найден", show_alert=True)
        return
    await callback.answer()
    await state.set_state(ReadingFlow.question)
    await state.update_data(spread_key=spread.key)
    await callback.message.answer(
        f"{spread.emoji} <b>{spread.title}</b> — {spread.price} ⭐\n\n"
        "✍️ Сформулируй свой вопрос одним сообщением. Чем конкретнее вопрос, "
        "тем точнее ответ карт.",
        reply_markup=kb.skip_question(),
    )


@router.callback_query(ReadingFlow.question, F.data == "q:cancel")
async def cancel_question(callback: CallbackQuery, state: FSMContext) -> None:
    assert isinstance(callback.message, Message)
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.answer("Хорошо, вернёмся, когда будешь готов(а). 🌙", reply_markup=kb.main_menu)


@router.callback_query(ReadingFlow.question, F.data == "q:skip")
async def skip_question(callback: CallbackQuery, state: FSMContext) -> None:
    assert isinstance(callback.message, Message) and callback.from_user
    await callback.answer()
    await send_invoice_for_reading(callback.message, state, question=None, tg_id=callback.from_user.id)


@router.message(ReadingFlow.question, F.text)
async def got_question(message: Message, state: FSMContext) -> None:
    assert message.text and message.from_user
    await send_invoice_for_reading(
        message, state, question=message.text.strip()[:500], tg_id=message.from_user.id
    )


async def send_invoice_for_reading(
    message: Message, state: FSMContext, question: str | None, tg_id: int
) -> None:
    data = await state.get_data()
    spread = SPREADS[data["spread_key"]]
    await state.update_data(question=question)
    if tg_id in config.admin_ids:  # админам бесплатно (тест-режим)
        user = await db.get_or_create_user(tg_id)
        await deliver_reading(message, state, user, spread.key, charge_id=None)
        return
    await message.answer_invoice(
        title=f"Расклад «{spread.title}»",
        description=(question or spread.description)[:255],
        payload=f"reading:{spread.key}",
        currency="XTR",
        prices=[LabeledPrice(label=spread.title, amount=spread.price)],
    )


# --- оплата ---


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    payload = query.invoice_payload or ""
    if payload.startswith("reading:") and payload.split(":", 1)[1] in SPREADS:
        await query.answer(ok=True)
    elif payload.startswith("clarify:"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Этот счёт устарел, начните заново.")


@router.message(F.successful_payment)
async def on_payment(message: Message, state: FSMContext) -> None:
    assert message.from_user and message.successful_payment and message.bot
    sp = message.successful_payment
    payload = sp.invoice_payload or ""
    user = await db.get_or_create_user(message.from_user.id)

    # идемпотентность: повторный апдейт с тем же charge_id не создаёт второй расклад
    fresh = await db.record_payment(
        user["id"], sp.total_amount, sp.telegram_payment_charge_id, payload
    )
    if not fresh:
        log.warning("Повторный successful_payment %s — пропускаю", sp.telegram_payment_charge_id)
        return

    if payload.startswith("reading:"):
        await deliver_reading(message, state, user, payload.split(":", 1)[1], sp.telegram_payment_charge_id)
    elif payload.startswith("clarify:"):
        reading_id = int(payload.split(":", 1)[1])
        await state.set_state(ClarifyFlow.question)
        await state.update_data(reading_id=reading_id, free=False)
        await message.answer("💫 Оплата получена! Напиши свой уточняющий вопрос одним сообщением.")


async def deliver_reading(
    message: Message, state: FSMContext, user: dict, spread_key: str, charge_id: str | None
) -> None:
    assert message.bot
    spread = SPREADS[spread_key]
    data = await state.get_data()
    question = data.get("question") if data.get("spread_key") == spread_key else None
    await state.clear()

    drawn = draw(spread.num_cards)
    cards_json = [{"id": dc.card.id, "reversed": dc.is_reversed} for dc in drawn]
    # расклад фиксируется в БД до генерации — после оплаты результат не потеряется
    reading_id = await db.create_reading(
        user_id=user["id"],
        rtype=spread.key,
        question=question,
        cards=cards_json,
        price_stars=spread.price if charge_id else 0,
        charge_id=charge_id,
        clarifications_left=config.free_clarifications,
    )

    prefix = "🎴 Оплата получена. " if charge_id else "🎴 Админ-режим, без оплаты. "
    await message.answer(prefix + "Тасую колоду и раскладываю карты…")
    subtitle = f"Вопрос: {question[:60]}…" if question and len(question) > 60 else (f"Вопрос: {question}" if question else "")
    try:
        await send_reading_media(message.bot, message.chat.id, drawn, spread, subtitle)
    except Exception:
        log.exception("Медиа расклада %d не отправилось", reading_id)

    history = [r["question"] for r in await db.recent_readings(user["id"], 4, paid_only=True)
               if r["question"] and r["id"] != reading_id]
    text = await interpreter.interpret(
        drawn, spread, question, user.get("name"), user.get("birth_date"), history
    )
    await db.set_interpretation(reading_id, text)
    await message.answer(
        md_bold_to_html(text),
        reply_markup=kb.clarify_kb(reading_id, config.free_clarifications, config.price_clarify),
    )


# --- уточняющие вопросы ---


@router.callback_query(F.data.startswith("clarify:"))
async def clarify_start(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.data and callback.from_user and isinstance(callback.message, Message)
    reading_id = int(callback.data.split(":", 1)[1])
    reading = await db.get_reading(reading_id)
    user = await db.get_or_create_user(callback.from_user.id)
    if not reading or reading["user_id"] != user["id"]:
        await callback.answer("Расклад не найден", show_alert=True)
        return
    await callback.answer()
    if callback.from_user.id in config.admin_ids:  # админам бесплатно, лимит не тратится
        await state.set_state(ClarifyFlow.question)
        await state.update_data(reading_id=reading_id, free=False)
        await callback.message.answer("🔍 Напиши уточняющий вопрос (админ-режим, бесплатно).")
    elif reading["clarifications_left"] > 0:
        await state.set_state(ClarifyFlow.question)
        await state.update_data(reading_id=reading_id, free=True)
        await callback.message.answer("🔍 Напиши уточняющий вопрос к этому раскладу одним сообщением.")
    else:
        await callback.message.answer_invoice(
            title="Уточняющий вопрос",
            description="Дополнительный вопрос к уже сделанному раскладу",
            payload=f"clarify:{reading_id}",
            currency="XTR",
            prices=[LabeledPrice(label="Уточнение", amount=config.price_clarify)],
        )


@router.message(ClarifyFlow.question, F.text)
async def clarify_answer(message: Message, state: FSMContext) -> None:
    assert message.from_user and message.text
    data = await state.get_data()
    await state.clear()
    reading = await db.get_reading(data["reading_id"])
    user = await db.get_or_create_user(message.from_user.id)
    if not reading or reading["user_id"] != user["id"]:
        await message.answer("Не нашёл этот расклад. Попробуй сделать новый. 🌙")
        return

    spread = SPREADS[reading["type"]]
    drawn = [
        DrawnCard(CARD_BY_ID[c["id"]], c["reversed"]) for c in json.loads(reading["cards_json"])
    ]
    prior = await db.get_clarifications(reading["id"])
    question = message.text.strip()[:500]
    await message.answer("🔮 Вглядываюсь в карты…")
    answer = await interpreter.clarify(
        drawn, spread, reading["question"], reading["interpretation"] or "",
        prior, question, user.get("name"),
    )
    if data.get("free"):
        await db.use_clarification(reading["id"])
        reading["clarifications_left"] -= 1
    await db.add_clarification(reading["id"], question, answer)
    await message.answer(
        md_bold_to_html(answer),
        reply_markup=kb.clarify_kb(reading["id"], reading["clarifications_left"], config.price_clarify),
    )

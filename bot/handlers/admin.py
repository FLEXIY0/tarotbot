import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import config
from bot.db import db

router = Router(name="admin")
log = logging.getLogger(__name__)

router.message.filter(F.from_user.id.in_(config.admin_ids))
router.callback_query.filter(F.from_user.id.in_(config.admin_ids))


class Broadcast(StatesGroup):
    text = State()


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    s = await db.stats()
    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"Пользователи: {s['users_total']} (+{s['users_today']} сегодня)\n"
        f"Расклады: {s['readings_total']} (+{s['readings_today']} сегодня)\n"
        f"Выручка: {s['stars_total']} ⭐ (+{s['stars_today']} сегодня)"
    )


@router.message(Command("refund"))
async def cmd_refund(message: Message, command: CommandObject) -> None:
    assert message.bot
    charge_id = (command.args or "").strip()
    if not charge_id:
        await message.answer("Использование: <code>/refund telegram_payment_charge_id</code>")
        return
    payment = await db.get_payment(charge_id)
    if not payment:
        await message.answer("Платёж с таким charge_id не найден.")
        return
    if payment["status"] == "refunded":
        await message.answer("Этот платёж уже возвращён.")
        return
    cur = await db.conn.execute("SELECT tg_id FROM users WHERE id = ?", (payment["user_id"],))
    row = await cur.fetchone()
    try:
        await message.bot.refund_star_payment(user_id=row[0], telegram_payment_charge_id=charge_id)
    except Exception as e:
        await message.answer(f"Telegram отклонил возврат: {e}")
        return
    await db.mark_refunded(charge_id)
    await message.answer(f"✅ Возвращено {payment['stars']} ⭐ пользователю {row[0]}.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    await state.set_state(Broadcast.text)
    await message.answer("Пришли текст рассылки одним сообщением (HTML разрешён). /cancel — отмена.")


@router.message(Broadcast.text, Command("cancel"))
async def broadcast_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Рассылка отменена.")


@router.message(Broadcast.text, F.text)
async def broadcast_confirm(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.html_text)
    count = len(await db.all_user_tg_ids())
    await message.answer(
        f"Отправить это сообщение {count} пользователям?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Отправить", callback_data="bc:go"),
            InlineKeyboardButton(text="✖️ Отмена", callback_data="bc:no"),
        ]]),
    )


@router.callback_query(F.data == "bc:no")
async def broadcast_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")


@router.callback_query(F.data == "bc:go")
async def broadcast_go(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.bot and isinstance(callback.message, Message)
    data = await state.get_data()
    await state.clear()
    text = data.get("text")
    if not text:
        await callback.answer("Текст потерялся, начни заново", show_alert=True)
        return
    await callback.answer()
    sent = failed = 0
    for tg_id in await db.all_user_tg_ids():
        try:
            await callback.bot.send_message(tg_id, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # ~20 msg/s, под лимитами Telegram
    await callback.message.answer(f"Рассылка завершена: доставлено {sent}, ошибок {failed}.")

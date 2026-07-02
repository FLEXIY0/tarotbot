from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot.config import config
from bot.db import db

router = Router(name="start")

DISCLAIMER = (
    "Бот — развлекательный сервис и не заменяет профессиональную консультацию "
    "врача, юриста или финансового советника."
)

HELP_TEXT = (
    "<b>Что я умею</b>\n\n"
    f"<b>{kb.BTN_DAILY}</b> — бесплатная карта дня, раз в сутки.\n"
    f"<b>{kb.BTN_SPREADS}</b> — персональные расклады с ритуалом и подробным "
    "толкованием. После каждого расклада можно задать уточняющие вопросы.\n"
    f"<b>{kb.BTN_HISTORY}</b> — все твои прошлые расклады.\n\n"
    "Оплата — в Telegram Stars. Вопросы по оплате: /paysupport\n\n" + DISCLAIMER
)


class Onboarding(StatesGroup):
    name = State()
    birth = State()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    assert message.from_user
    referrer = None
    if command.args and command.args.isdigit():
        referrer = int(command.args)
        if referrer == message.from_user.id:
            referrer = None
    user = await db.get_or_create_user(message.from_user.id, referrer)
    if user.get("name"):
        await message.answer(
            f"С возвращением, {user['name']}. Карты уже ждут.", reply_markup=kb.main_menu
        )
        return
    await message.answer(
        "Приветствую. Я — Люмина, твой проводник в мир Таро.\n\n"
        "Я делаю персональные расклады: ты задаёшь вопрос, я тяну карты из "
        "колоды Райдера–Уэйта и читаю их для тебя.\n\n"
        "Чтобы расклады были точнее, давай познакомимся. <b>Как тебя зовут?</b>\n\n<i>" + DISCLAIMER + "</i>",
        reply_markup=kb.onboarding_skip("name"),
    )
    await state.set_state(Onboarding.name)


@router.message(Onboarding.name, F.text)
async def onb_name(message: Message, state: FSMContext) -> None:
    assert message.from_user and message.text
    name = message.text.strip()[:50]
    await db.update_user(message.from_user.id, name=name)
    await ask_birth(message, state, name)


@router.callback_query(Onboarding.name, F.data == "onb_skip:name")
async def onb_skip_name(callback: CallbackQuery, state: FSMContext) -> None:
    assert isinstance(callback.message, Message)
    await callback.answer()
    await ask_birth(callback.message, state, None)


async def ask_birth(message: Message, state: FSMContext, name: str | None) -> None:
    hello = f"Очень приятно, {name}. " if name else ""
    await message.answer(
        f"{hello}Теперь — <b>дата рождения</b> (например, 21.03.1995). "
        "Она поможет мне тоньше настроиться на твою энергию.",
        reply_markup=kb.onboarding_skip("birth"),
    )
    await state.set_state(Onboarding.birth)


@router.message(Onboarding.birth, F.text)
async def onb_birth(message: Message, state: FSMContext) -> None:
    assert message.from_user and message.text
    await db.update_user(message.from_user.id, birth_date=message.text.strip()[:20])
    await finish_onboarding(message, state)


@router.callback_query(Onboarding.birth, F.data == "onb_skip:birth")
async def onb_skip_birth(callback: CallbackQuery, state: FSMContext) -> None:
    assert isinstance(callback.message, Message)
    await callback.answer()
    await finish_onboarding(callback.message, state)


async def finish_onboarding(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Готово. Начни с бесплатной <b>карты дня</b> — она уже ждёт тебя.",
        reply_markup=kb.main_menu,
    )


@router.message(Command("help"))
@router.message(F.text == kb.BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=kb.main_menu)


@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message) -> None:
    await message.answer(
        "<b>Поддержка по оплате</b>\n\n"
        "Оплата принимается в Telegram Stars.\n\n"
        "<b>Возвраты.</b> Если расклад не был доставлен из-за технического сбоя — напишите нам, "
        "и мы вернём звёзды. Возврат за корректно доставленный расклад не предусмотрен, "
        "так как услуга оказывается в момент генерации.\n\n"
        f"Связь: {config.support_contact}"
    )

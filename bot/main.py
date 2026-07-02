import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot import runtime
from bot.config import config
from bot.db import db
from bot.handlers import router
from bot.handlers.daily import reminder_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def main() -> None:
    await db.connect()
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    me = await bot.get_me()
    runtime.bot_username = me.username or ""

    await bot.set_my_commands([
        BotCommand(command="daily", description="🌞 Карта дня (бесплатно)"),
        BotCommand(command="spreads", description="🔮 Расклады"),
        BotCommand(command="history", description="📜 История раскладов"),
        BotCommand(command="help", description="ℹ️ Помощь"),
        BotCommand(command="paysupport", description="💫 Поддержка по оплате"),
    ])

    reminders = asyncio.create_task(reminder_loop(bot))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        reminders.cancel()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())

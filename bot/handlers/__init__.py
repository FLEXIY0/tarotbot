from aiogram import Router

from bot.handlers import admin, daily, history, inline, readings, start

router = Router(name="root")
router.include_routers(
    admin.router, start.router, daily.router, readings.router, history.router, inline.router
)

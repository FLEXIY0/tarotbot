"""Смоук-тесты без Telegram: колода, рендер, БД, платежи.

Запуск: BOT_TOKEN=1:test python -m pytest tests/ -q
"""

import asyncio
import os
import tempfile
from pathlib import Path

os.environ.setdefault("BOT_TOKEN", "1:test")
os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "test.db"))

from bot.deck import DECK, draw  # noqa: E402
from bot.render import render_collage  # noqa: E402
from bot.spreads import SPREADS  # noqa: E402
from bot.video import render_reading_video  # noqa: E402


def test_deck_complete():
    assert len(DECK) == 78
    assert len({c.id for c in DECK}) == 78
    for c in DECK:
        assert c.image_path.exists(), f"нет изображения для {c.id}"
        assert c.upright and c.reversed and c.name


def test_draw_unique():
    drawn = draw(10)
    assert len({d.card.id for d in drawn}) == 10


def test_collage_all_spreads():
    for spread in SPREADS.values():
        img = render_collage(draw(spread.num_cards), spread, "тест")
        assert img.width % 2 == 0 and img.height % 2 == 0  # требование yuv420p


def test_video_one_card():
    spread = SPREADS["one"]
    out = render_reading_video(draw(1), spread)
    assert out is not None and out.stat().st_size > 10_000
    out.unlink()


def test_db_payment_idempotency():
    async def run():
        from bot.db import Database

        db = Database()
        from bot import config as cfg

        await db.connect()
        u = await db.get_or_create_user(42)
        assert await db.record_payment(u["id"], 30, "c1", "reading:three")
        assert not await db.record_payment(u["id"], 30, "c1", "reading:three")
        await db.close()
        cfg.config.db_path.unlink(missing_ok=True)

    asyncio.run(run())

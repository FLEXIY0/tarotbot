import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from bot.config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    tg_id INTEGER UNIQUE NOT NULL,
    name TEXT,
    birth_date TEXT,
    created_at TEXT NOT NULL,
    daily_card_date TEXT,
    referrer_id INTEGER
);
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    type TEXT NOT NULL,
    question TEXT,
    cards_json TEXT NOT NULL,
    interpretation TEXT,
    created_at TEXT NOT NULL,
    price_stars INTEGER NOT NULL DEFAULT 0,
    payment_charge_id TEXT,
    clarifications_left INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS clarifications (
    id INTEGER PRIMARY KEY,
    reading_id INTEGER NOT NULL REFERENCES readings(id),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    reading_id INTEGER,
    stars INTEGER NOT NULL,
    charge_id TEXT UNIQUE NOT NULL,
    payload TEXT,
    status TEXT NOT NULL DEFAULT 'paid',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media_cache (
    key TEXT PRIMARY KEY,
    file_id TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self) -> None:
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(config.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        # лёгкие миграции для существующих баз
        for ddl in (
            "ALTER TABLE users ADD COLUMN remind_daily INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN reminded_date TEXT",
        ):
            try:
                await self._conn.execute(ddl)
            except aiosqlite.OperationalError:
                pass  # колонка уже есть
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database.connect() не вызван"
        return self._conn

    # --- users ---

    async def get_or_create_user(self, tg_id: int, referrer_id: int | None = None) -> dict[str, Any]:
        cur = await self.conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        if row:
            return dict(row)
        await self.conn.execute(
            "INSERT INTO users (tg_id, created_at, referrer_id) VALUES (?, ?, ?)",
            (tg_id, _now(), referrer_id),
        )
        await self.conn.commit()
        return await self.get_or_create_user(tg_id)

    async def update_user(self, tg_id: int, **fields: Any) -> None:
        keys = ", ".join(f"{k} = ?" for k in fields)
        await self.conn.execute(f"UPDATE users SET {keys} WHERE tg_id = ?", (*fields.values(), tg_id))
        await self.conn.commit()

    # --- readings ---

    async def create_reading(
        self,
        user_id: int,
        rtype: str,
        question: str | None,
        cards: list[dict],
        price_stars: int,
        charge_id: str | None,
        clarifications_left: int,
    ) -> int:
        cur = await self.conn.execute(
            "INSERT INTO readings (user_id, type, question, cards_json, created_at,"
            " price_stars, payment_charge_id, clarifications_left)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, rtype, question, json.dumps(cards, ensure_ascii=False), _now(),
             price_stars, charge_id, clarifications_left),
        )
        await self.conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid

    async def set_interpretation(self, reading_id: int, text: str) -> None:
        await self.conn.execute("UPDATE readings SET interpretation = ? WHERE id = ?", (text, reading_id))
        await self.conn.commit()

    async def get_reading(self, reading_id: int) -> dict[str, Any] | None:
        cur = await self.conn.execute("SELECT * FROM readings WHERE id = ?", (reading_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def use_clarification(self, reading_id: int) -> None:
        await self.conn.execute(
            "UPDATE readings SET clarifications_left = clarifications_left - 1"
            " WHERE id = ? AND clarifications_left > 0",
            (reading_id,),
        )
        await self.conn.commit()

    async def add_clarification(self, reading_id: int, question: str, answer: str) -> None:
        await self.conn.execute(
            "INSERT INTO clarifications (reading_id, question, answer, created_at) VALUES (?, ?, ?, ?)",
            (reading_id, question, answer, _now()),
        )
        await self.conn.commit()

    async def get_clarifications(self, reading_id: int) -> list[dict[str, Any]]:
        cur = await self.conn.execute(
            "SELECT * FROM clarifications WHERE reading_id = ? ORDER BY id", (reading_id,)
        )
        return [dict(r) for r in await cur.fetchall()]

    async def recent_readings(self, user_id: int, limit: int = 10, paid_only: bool = False) -> list[dict[str, Any]]:
        q = "SELECT * FROM readings WHERE user_id = ?"
        if paid_only:
            q += " AND price_stars > 0"
        q += " ORDER BY id DESC LIMIT ?"
        cur = await self.conn.execute(q, (user_id, limit))
        return [dict(r) for r in await cur.fetchall()]

    # --- payments ---

    async def record_payment(
        self, user_id: int, stars: int, charge_id: str, payload: str, reading_id: int | None = None
    ) -> bool:
        """False, если этот charge_id уже обработан (идемпотентность)."""
        try:
            await self.conn.execute(
                "INSERT INTO payments (user_id, reading_id, stars, charge_id, payload, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, reading_id, stars, charge_id, payload, _now()),
            )
            await self.conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def mark_refunded(self, charge_id: str) -> bool:
        cur = await self.conn.execute(
            "UPDATE payments SET status = 'refunded' WHERE charge_id = ? AND status = 'paid'", (charge_id,)
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def get_payment(self, charge_id: str) -> dict[str, Any] | None:
        cur = await self.conn.execute("SELECT * FROM payments WHERE charge_id = ?", (charge_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

    # --- stats / admin ---

    async def stats(self) -> dict[str, Any]:
        async def one(q: str, *args: Any) -> Any:
            cur = await self.conn.execute(q, args)
            row = await cur.fetchone()
            return row[0] if row else 0

        today = datetime.now(timezone.utc).date().isoformat()
        return {
            "users_total": await one("SELECT COUNT(*) FROM users"),
            "users_today": await one("SELECT COUNT(*) FROM users WHERE created_at >= ?", today),
            "readings_total": await one("SELECT COUNT(*) FROM readings"),
            "readings_today": await one("SELECT COUNT(*) FROM readings WHERE created_at >= ?", today),
            "stars_total": await one("SELECT COALESCE(SUM(stars),0) FROM payments WHERE status='paid'"),
            "stars_today": await one(
                "SELECT COALESCE(SUM(stars),0) FROM payments WHERE status='paid' AND created_at >= ?", today
            ),
        }

    async def all_user_tg_ids(self) -> list[int]:
        cur = await self.conn.execute("SELECT tg_id FROM users")
        return [r[0] for r in await cur.fetchall()]

    # --- утренние напоминания ---

    async def users_to_remind(self, today: str) -> list[int]:
        cur = await self.conn.execute(
            "SELECT tg_id FROM users WHERE remind_daily = 1"
            " AND (daily_card_date IS NULL OR daily_card_date != ?)"
            " AND (reminded_date IS NULL OR reminded_date != ?)",
            (today, today),
        )
        return [r[0] for r in await cur.fetchall()]

    async def mark_reminded(self, tg_id: int, today: str) -> None:
        await self.conn.execute("UPDATE users SET reminded_date = ? WHERE tg_id = ?", (today, tg_id))
        await self.conn.commit()

    # --- media cache (file_id переиспользуется Telegram бесплатно) ---

    async def cache_get(self, key: str) -> str | None:
        cur = await self.conn.execute("SELECT file_id FROM media_cache WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

    async def cache_set(self, key: str, file_id: str) -> None:
        await self.conn.execute(
            "INSERT INTO media_cache (key, file_id) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET file_id = excluded.file_id",
            (key, file_id),
        )
        await self.conn.commit()


db = Database()

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _admin_ids() -> frozenset[int]:
    raw = os.getenv("ADMIN_IDS", "")
    return frozenset(int(x) for x in raw.replace(" ", "").split(",") if x)


@dataclass(frozen=True)
class Config:
    bot_token: str = field(default_factory=lambda: os.environ["BOT_TOKEN"])
    admin_ids: frozenset[int] = field(default_factory=_admin_ids)

    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "claude-opus-4-8"))

    db_path: Path = field(default_factory=lambda: ROOT / os.getenv("DB_PATH", "data/tarotbot.db"))
    tz: str = field(default_factory=lambda: os.getenv("TZ", "Europe/Moscow"))
    reminder_hour: int = field(default_factory=lambda: int(os.getenv("REMINDER_HOUR", "9")))

    # цены в Telegram Stars (XTR); меняются через env без правки кода
    price_one: int = field(default_factory=lambda: int(os.getenv("PRICE_ONE", "15")))
    price_three: int = field(default_factory=lambda: int(os.getenv("PRICE_THREE", "30")))
    price_relationship: int = field(default_factory=lambda: int(os.getenv("PRICE_RELATIONSHIP", "45")))
    price_celtic: int = field(default_factory=lambda: int(os.getenv("PRICE_CELTIC", "75")))
    price_clarify: int = field(default_factory=lambda: int(os.getenv("PRICE_CLARIFY", "8")))
    free_clarifications: int = field(default_factory=lambda: int(os.getenv("FREE_CLARIFICATIONS", "2")))

    support_contact: str = field(default_factory=lambda: os.getenv("SUPPORT_CONTACT", "@your_support"))


config = Config()

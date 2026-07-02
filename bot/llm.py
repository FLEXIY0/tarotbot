"""LLM-прослойка: интерпретации раскладов через Claude API с fallback на значения карт.

Провайдер спрятан за классом Interpreter — при масштабировании сюда можно
подставить локальную модель, не трогая хендлеры.
"""

import logging

import anthropic

from bot.config import config
from bot.deck import DrawnCard
from bot.spreads import Spread

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — опытная таролог по имени Люмина: тёплая, образная, внимательная к деталям.
Ты делаешь персональные интерпретации раскладов Таро на русском языке.

Правила:
- Обращайся к человеку по имени, если оно известно, на «ты».
- Обязательно вплетай в трактовку КАЖДУЮ вытянутую карту: её название, положение
  (прямое/перевёрнутое) и позицию в раскладе. Названия карт выделяй жирным (**Карта**).
- Свяжи карты в единую историю, отвечающую на вопрос человека, а не пересказывай значения по отдельности.
- Заверши тёплым практичным советом (2-3 предложения).
- Объём: 150-400 слов. Для расклада из одной карты — 100-200 слов.
- Тон: мистический, но ясный; поддерживающий, без запугивания. Перевёрнутые и «тяжёлые»
  карты трактуй как зоны роста и предупреждения, а не приговор.
- Не давай медицинских, юридических или финансовых директивных указаний; при таких вопросах
  мягко напомни, что карты показывают энергии ситуации, а решения принимает человек.
- Не упоминай, что ты ИИ. Не используй заголовки и списки — только живой связный текст."""


def _spread_block(drawn: list[DrawnCard], spread: Spread) -> str:
    lines = [f"Расклад: «{spread.title}» ({spread.description})"]
    for slot, dc in zip(spread.slots, drawn):
        pos = "перевёрнутая" if dc.is_reversed else "прямая"
        lines.append(f"- Позиция «{slot.label}»: {dc.card.name} ({dc.card.name_en}), {pos}. "
                     f"Ключевые значения: {dc.meaning}.")
    return "\n".join(lines)


def _profile_block(name: str | None, birth_date: str | None) -> str:
    parts = []
    if name:
        parts.append(f"Имя: {name}")
    if birth_date:
        parts.append(f"Дата рождения: {birth_date}")
    return "; ".join(parts) if parts else "не указан"


class Interpreter:
    def __init__(self) -> None:
        self._client = (
            anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
            if config.anthropic_api_key
            else None
        )

    async def _complete(self, prompt: str, max_tokens: int = 1200) -> str | None:
        if self._client is None:
            log.warning("ANTHROPIC_API_KEY не задан — используется fallback-интерпретация")
            return None
        for attempt in range(2):
            try:
                resp = await self._client.messages.create(
                    model=config.llm_model,
                    max_tokens=max_tokens,
                    system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                    messages=[{"role": "user", "content": prompt}],
                    timeout=90.0,
                )
                text = "".join(b.text for b in resp.content if b.type == "text").strip()
                if text:
                    log.info("LLM ok: in=%s out=%s tokens", resp.usage.input_tokens, resp.usage.output_tokens)
                    return text
            except Exception:
                log.exception("LLM запрос не удался (попытка %d)", attempt + 1)
        return None

    async def interpret(
        self,
        drawn: list[DrawnCard],
        spread: Spread,
        question: str | None,
        name: str | None,
        birth_date: str | None,
        history: list[str] | None = None,
    ) -> str:
        prompt_parts = [
            f"Профиль клиента: {_profile_block(name, birth_date)}",
            f"Вопрос клиента: {question or 'общий расклад без конкретного вопроса'}",
            _spread_block(drawn, spread),
        ]
        if history:
            prompt_parts.append("Темы прошлых обращений (для тонкой персонализации, не пересказывай их): "
                                + "; ".join(history[:3]))
        prompt_parts.append("Дай интерпретацию расклада.")
        text = await self._complete("\n\n".join(prompt_parts))
        return text or self.fallback(drawn, spread, name)

    async def interpret_daily(self, dc: DrawnCard, name: str | None) -> str:
        prompt = (
            f"Профиль клиента: {_profile_block(name, None)}\n\n"
            f"Карта дня: {dc.card.name} ({dc.card.name_en}), "
            f"{'перевёрнутая' if dc.is_reversed else 'прямая'}. Значения: {dc.meaning}.\n\n"
            "Дай короткое (50-90 слов) послание дня по этой карте: на что обратить внимание сегодня. "
            "Ответ должен уместиться в подпись к фото — без вступлений, сразу суть."
        )
        text = await self._complete(prompt, max_tokens=500)
        if text:
            return text
        return (
            f"🌙 Сегодня тебе выпала карта **{dc.title}**.\n\n"
            f"Её энергии дня: {dc.meaning}. Понаблюдай, где эти темы проявятся сегодня, — "
            "карта подсвечивает то, что просит твоего внимания."
        )

    async def clarify(
        self,
        drawn: list[DrawnCard],
        spread: Spread,
        original_question: str | None,
        interpretation: str,
        prior: list[dict],
        question: str,
        name: str | None,
    ) -> str:
        parts = [
            f"Профиль клиента: {_profile_block(name, None)}",
            f"Исходный вопрос: {original_question or 'общий расклад'}",
            _spread_block(drawn, spread),
            f"Твоя интерпретация была такой:\n{interpretation}",
        ]
        for c in prior:
            parts.append(f"Уточнение клиента: {c['question']}\nТвой ответ: {c['answer']}")
        parts.append(
            f"Новый уточняющий вопрос клиента: {question}\n\n"
            "Ответь на уточняющий вопрос в контексте этого же расклада (120-250 слов). "
            "Новые карты не тяни — работай с уже выпавшими."
        )
        text = await self._complete("\n\n".join(parts), max_tokens=800)
        return text or (
            "Карты уже сказали главное в раскладе выше — перечитай позиции, которые "
            "откликаются на твой вопрос. Если хочется нового ответа, лучше сделать отдельный расклад. ✨"
        )

    @staticmethod
    def fallback(drawn: list[DrawnCard], spread: Spread, name: str | None) -> str:
        """Интерпретация из статических значений — пользователь не остаётся без результата."""
        who = f"{name}, " if name else ""
        lines = [f"✨ {who}вот что показали карты в раскладе «{spread.title}»:\n"]
        for slot, dc in zip(spread.slots, drawn):
            lines.append(f"🔮 **{slot.label}** — **{dc.title}**: {dc.meaning}.")
        lines.append(
            "\nСоедини эти образы с тем, что происходит в твоей ситуации, — карты описывают "
            "энергии, а выбор всегда остаётся за тобой. Задай уточняющий вопрос, если что-то "
            "хочется раскрыть глубже. 🌙"
        )
        return "\n".join(lines)


interpreter = Interpreter()

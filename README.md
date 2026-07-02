# 🔮 TarotBot — Telegram-бот платных таро-раскладов

Персональные расклады Таро с видео-анимацией переворота карт, интерпретациями от LLM
и оплатой в Telegram Stars. Полное ТЗ — в [TZ.md](TZ.md).

## Возможности

- 🌞 **Карта дня** — бесплатно раз в сутки, воронка и удержание
- 🔮 **4 платных расклада**: одна карта, «Прошлое–Настоящее–Будущее», «Отношения», «Кельтский крест»
- 🎴 **Видео-ритуал**: карты ложатся рубашками и переворачиваются в коротком MP4 (Pillow + ffmpeg)
- 🧠 **Персональные интерпретации** через Claude API: бот помнит имя, дату рождения и темы прошлых раскладов; при недоступности LLM — fallback на классические значения карт
- 🔍 **Уточняющие вопросы** к сделанному раскладу (2 бесплатно, дальше за ⭐)
- ⭐ **Оплата в Telegram Stars** с идемпотентностью платежей и возвратами (`/refund`)
- 📜 История раскладов, админ-статистика, рассылки

## Быстрый старт

```bash
git clone <repo> && cd tarotbot
cp .env.example .env      # заполнить BOT_TOKEN, ADMIN_IDS, ANTHROPIC_API_KEY
docker compose up -d --build
```

Всё. ffmpeg и шрифты уже внутри образа, база SQLite живёт в volume `bot_data`.

Локальный запуск без Docker:

```bash
pip install -r requirements.txt
cp .env.example .env && set -a && source .env && set +a
python -m bot.main
```

## Структура

```
bot/
  main.py        # точка входа, polling
  config.py      # все настройки из env
  deck.py        # 78 карт, криптографическая тяга, перевёрнутые
  spreads.py     # определения раскладов и раскладка для рендера
  render.py      # Pillow: коллаж и кадры анимации переворота
  video.py       # сборка кадров в MP4 (ffmpeg)
  ritual.py      # отправка видео/коллажа, кэш file_id
  llm.py         # интерпретации (Claude API) + fallback
  db.py          # SQLite: пользователи, расклады, платежи, кэш медиа
  handlers/      # start/онбординг, карта дня, расклады+оплата, история, админка
data/deck.json   # названия и значения всех 78 карт (рус)
assets/cards/    # public domain сканы Райдера–Уэйта (Internet Archive)
tools/prepare_deck.py  # скачивание и нормализация сканов
```

## Админ-команды

- `/stats` — пользователи, расклады, выручка
- `/refund <telegram_payment_charge_id>` — возврат звёзд
- `/broadcast` — рассылка с подтверждением

## Лицензии материалов

- Сканы карт: колода Райдера–Уэйта 1909 г., public domain
  ([Internet Archive](https://archive.org/details/rider-waite-tarot))
- Шрифты DejaVu: [лицензия Bitstream Vera / Arev](https://dejavu-fonts.github.io/License.html), разрешает распространение

## Дисклеймер

Бот — развлекательный сервис и не является профессиональной консультацией.

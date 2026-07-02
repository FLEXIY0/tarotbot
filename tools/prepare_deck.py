"""Скачивает public domain сканы Райдера-Уэйта с Internet Archive и нормализует их.

Источник: https://archive.org/details/rider-waite-tarot (Public Domain Mark 1.0).
Результат: assets/cards/<id>.jpg (высота 900px, JPEG q87) + assets/back.png (рубашка).

Запуск:  python tools/prepare_deck.py
Повторный запуск докачивает только недостающие карты.
"""

import io
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "assets" / "cards"
DECK_JSON = ROOT / "data" / "deck.json"
IA_BASE = "https://archive.org/download/rider-waite-tarot"
CARD_HEIGHT = 900


def fetch(name: str, attempts: int = 4) -> bytes:
    url = f"{IA_BASE}/{name}"
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return resp.read()
        except Exception:
            if attempt == attempts - 1:
                raise
            import time

            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def normalize(raw: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size
    new_w = round(w * CARD_HEIGHT / h)
    return img.resize((new_w, CARD_HEIGHT), Image.LANCZOS)


def process(card_id: str) -> str:
    out = CARDS_DIR / f"{card_id}.jpg"
    if out.exists():
        return f"skip  {card_id}"
    raw = fetch(f"{card_id}.png")
    img = normalize(raw)
    img.save(out, "JPEG", quality=87, optimize=True)
    return f"ok    {card_id} ({img.size[0]}x{img.size[1]}, {out.stat().st_size // 1024} KB)"


def make_back() -> None:
    """Рубашка: глубокие чернила, двойная волосяная рамка, полумесяц со звездой."""
    out = ROOT / "assets" / "back.png"
    if out.exists():
        return
    import random

    w, h = 600, 900
    ink = (14, 13, 26)
    gold = (201, 170, 108)
    gold_dim = (110, 94, 66)
    img = Image.new("RGB", (w, h), ink)
    d = ImageDraw.Draw(img)
    for y in range(h):  # едва заметный градиент
        t = y / h
        d.line([(0, y), (w, y)], fill=(14 + round(10 * t), 13 + round(7 * t), 26 + round(14 * t)))

    rnd = random.Random(3)
    for _ in range(46):  # редкие тусклые звёзды
        x, y = rnd.randrange(48, w - 48), rnd.randrange(48, h - 48)
        c = 70 + rnd.randrange(60)
        d.point((x, y), fill=(c, c, c + 10))
    for _ in range(8):  # тонкие искры
        x, y = rnd.randrange(70, w - 70), rnd.randrange(70, h - 70)
        r = rnd.choice((4, 6))
        d.line([(x - r, y), (x + r, y)], fill=gold_dim, width=1)
        d.line([(x, y - r), (x, y + r)], fill=gold_dim, width=1)

    d.rounded_rectangle([18, 18, w - 19, h - 19], 14, outline=gold_dim, width=2)
    d.rounded_rectangle([30, 30, w - 31, h - 31], 10, outline=gold_dim, width=1)
    for cx, cy in ((18, 18), (w - 19, 18), (18, h - 19), (w - 19, h - 19)):
        d.polygon([(cx, cy - 7), (cx + 7, cy), (cx, cy + 7), (cx - 7, cy)], fill=gold)

    # полумесяц: золотой круг минус смещённый круг фона
    mx, my, r = w // 2, h // 2 - 20, 92
    d.ellipse([mx - r, my - r, mx + r, my + r], fill=gold)
    d.ellipse([mx - r + 46, my - r - 18, mx + r + 46, my + r - 18], fill=(20, 18, 36))
    # маленькая четырёхлучевая звезда рядом
    sx, sy = mx + 68, my + 46
    d.polygon([(sx, sy - 16), (sx + 5, sy - 5), (sx + 16, sy), (sx + 5, sy + 5),
               (sx, sy + 16), (sx - 5, sy + 5), (sx - 16, sy), (sx - 5, sy - 5)], fill=gold)
    img.save(out, "PNG", optimize=True)
    print("ok    back.png")


def main() -> None:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    deck = json.loads(DECK_JSON.read_text(encoding="utf-8"))
    ids = [c["id"] for c in deck["cards"]]
    assert len(ids) == 78, f"deck.json должен содержать 78 карт, найдено {len(ids)}"
    make_back()
    errors = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for res in pool.map(lambda i: _safe(i, errors), ids):
            print(res)
    if errors:
        print(f"\nОШИБКИ ({len(errors)}): {errors}", file=sys.stderr)
        sys.exit(1)
    print(f"\nГотово: {len(list(CARDS_DIR.glob('*.jpg')))}/78 карт в {CARDS_DIR}")


def _safe(card_id: str, errors: list) -> str:
    try:
        return process(card_id)
    except Exception as e:  # noqa: BLE001 - собираем все сбои, чтобы показать разом
        errors.append(card_id)
        return f"FAIL  {card_id}: {e}"


if __name__ == "__main__":
    main()

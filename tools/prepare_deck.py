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
    """Рубашка карты: тёмно-синее поле, двойная золотая рамка, узор из звёзд."""
    out = ROOT / "assets" / "back.png"
    if out.exists():
        return
    w, h = 600, 900
    img = Image.new("RGB", (w, h), (24, 22, 56))
    d = ImageDraw.Draw(img)
    gold = (196, 164, 90)
    d.rectangle([14, 14, w - 15, h - 15], outline=gold, width=4)
    d.rectangle([30, 30, w - 31, h - 31], outline=gold, width=2)
    # регулярная сетка ромбов со звёздами
    import math

    def star(cx, cy, r, color):
        pts = []
        for i in range(8):
            ang = math.pi / 4 * i - math.pi / 2
            rr = r if i % 2 == 0 else r * 0.4
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        d.polygon(pts, fill=color)

    step = 78
    for row in range(3, (h - 60) // step):
        for col in range(1, (w - 60) // step):
            x = 30 + col * step + (step // 2 if row % 2 else 0)
            y = 30 + row * step
            if 60 < x < w - 60 and 60 < y < h - 60:
                star(x, y, 11, (72, 66, 130))
    # центральная большая звезда
    star(w // 2, h // 2, 60, gold)
    star(w // 2, h // 2, 34, (24, 22, 56))
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

"""Рендер расклада: статичный коллаж и кадры анимации переворота (Pillow)."""

import math
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bot.deck import DrawnCard
from bot.spreads import Spread

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
BACK_PATH = ROOT / "assets" / "back.png"

CW = 200                      # ширина карты на канве
CH = round(CW * 900 / 520)    # высота (пропорции сканов)
MARGIN = 56
TITLE_H = 88
LABEL_H = 40
FPS = 24

BG_TOP = (16, 14, 38)
BG_BOTTOM = (36, 24, 62)
GOLD = (212, 181, 112)
LABEL_COLOR = (196, 190, 222)


@lru_cache(maxsize=4)
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _rounded(img: Image.Image, radius: int = 12) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius, fill=255)
    img.putalpha(mask)
    return img


@lru_cache(maxsize=200)
def _card_face(card_id: str, is_reversed: bool, width: int = CW) -> Image.Image:
    height = round(width * 900 / 520)
    img = Image.open(ROOT / "assets" / "cards" / f"{card_id}.jpg").convert("RGB")
    img = img.resize((width, height), Image.LANCZOS)
    if is_reversed:
        img = img.rotate(180)
    return _rounded(img)


@lru_cache(maxsize=4)
def _card_back(width: int = CW) -> Image.Image:
    height = round(width * 900 / 520)
    img = Image.open(BACK_PATH).convert("RGB").resize((width, height), Image.LANCZOS)
    return _rounded(img)


def _slot_px(spread: Spread) -> tuple[list[tuple[int, int]], int, int]:
    """Пиксельные top-left координаты слотов и размер канвы (чётные стороны для h264)."""
    xs = [s.x for s in spread.slots]
    ys = [s.y for s in spread.slots]
    w = MARGIN * 2 + round(max(xs) * CW) + CW
    # поперечная карта кельтского креста шире обычной — добавим поля
    if any(s.cross for s in spread.slots):
        w += (CH - CW) // 2
    h = TITLE_H + MARGIN + round(max(ys) * CH) + CH + LABEL_H + MARGIN
    pos = [(MARGIN + round(s.x * CW), TITLE_H + MARGIN + round(s.y * CH)) for s in spread.slots]
    return pos, w + w % 2, h + h % 2


def _base(spread: Spread, subtitle: str = "") -> tuple[Image.Image, list[tuple[int, int]]]:
    pos, w, h = _slot_px(spread)
    img = Image.new("RGB", (w, h), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(h):  # вертикальный градиент
        t = y / h
        d.line(
            [(0, y), (w, y)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
        )
    # мерцающие точки-звёзды
    import random

    rnd = random.Random(7)
    for _ in range(w * h // 9000):
        x, y = rnd.randrange(w), rnd.randrange(h)
        d.point((x, y), fill=(90 + rnd.randrange(60),) * 3)

    title_font = _font("DejaVuSerif-Bold.ttf", 34)
    tw = d.textlength(spread.title, font=title_font)
    d.text(((w - tw) / 2, 26), spread.title, font=title_font, fill=GOLD)
    if subtitle:
        sub_font = _font("DejaVuSans.ttf", 18)
        sw = d.textlength(subtitle, font=sub_font)
        d.text(((w - sw) / 2, 66), subtitle, font=sub_font, fill=LABEL_COLOR)

    label_font = _font("DejaVuSans.ttf", 17)
    for slot, (x, y) in zip(spread.slots, pos):
        if slot.cross:
            continue  # подпись поперечной карты наложилась бы на первую
        lw = d.textlength(slot.label, font=label_font)
        d.text((x + (CW - lw) / 2, y + CH + 10), slot.label, font=label_font, fill=LABEL_COLOR)
    return img, pos


def _paste_slot(canvas: Image.Image, sprite: Image.Image, slot_xy: tuple[int, int], cross: bool) -> None:
    x, y = slot_xy
    if cross:
        sprite = sprite.rotate(90, expand=True)
        x += (CW - sprite.width) // 2
        y += (CH - sprite.height) // 2
    else:
        x += (CW - sprite.width) // 2
        y += (CH - sprite.height) // 2
    canvas.paste(sprite, (x, y), sprite)


def render_collage(drawn: list[DrawnCard], spread: Spread, subtitle: str = "") -> Image.Image:
    base, pos = _base(spread, subtitle)
    canvas = base.copy()
    for dc, slot, xy in zip(drawn, spread.slots, pos):
        shadow = Image.new("RGBA", (CW + 16, CH + 16), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([8, 10, CW + 8, CH + 12], 14, fill=(0, 0, 0, 120))
        canvas.paste(
            shadow.filter(ImageFilter.GaussianBlur(5)),
            (xy[0] - 8, xy[1] - 8),
            shadow.filter(ImageFilter.GaussianBlur(5)),
        )
        _paste_slot(canvas, _card_face(dc.card.id, dc.is_reversed), xy, slot.cross)
    return canvas


def _squeeze(sprite: Image.Image, factor: float) -> Image.Image:
    w = max(2, round(sprite.width * factor))
    return sprite.resize((w, sprite.height), Image.BILINEAR)


def iter_frames(drawn: list[DrawnCard], spread: Spread, subtitle: str = "") -> Iterator[Image.Image]:
    """Кадры: рубашки ложатся по одной, затем каждая карта переворачивается."""
    base, pos = _base(spread, subtitle)
    back = _card_back()
    faces = [_card_face(dc.card.id, dc.is_reversed) for dc in drawn]
    n = len(drawn)
    # state[i]: None=пусто, "back", "face"
    state: list[str | None] = [None] * n

    def frame(anim_idx: int | None = None, anim_sprite: Image.Image | None = None) -> Image.Image:
        canvas = base.copy()
        for i, (slot, xy) in enumerate(zip(spread.slots, pos)):
            if anim_idx == i and anim_sprite is not None:
                _paste_slot(canvas, anim_sprite, xy, slot.cross)
            elif state[i] == "back":
                _paste_slot(canvas, back, xy, slot.cross)
            elif state[i] == "face":
                _paste_slot(canvas, faces[i], xy, slot.cross)
        return canvas

    yield frame()
    # раздача рубашек
    deal_hold = 3 if n > 4 else 5
    for i in range(n):
        state[i] = "back"
        f = frame()
        for _ in range(deal_hold):
            yield f
    # перевороты
    flip_steps = 8
    hold_after = 5 if n > 4 else 9
    for i in range(n):
        for step in range(flip_steps + 1):
            t = step / flip_steps
            factor = abs(math.cos(math.pi * t))
            sprite = _squeeze(back if t < 0.5 else faces[i], max(factor, 0.04))
            yield frame(anim_idx=i, anim_sprite=sprite)
        state[i] = "face"
        f = frame()
        for _ in range(hold_after):
            yield f
    # финальный кадр
    final = render_collage(drawn, spread, subtitle)
    for _ in range(FPS * 2):
        yield final

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


def _paste_slot(
    canvas: Image.Image,
    sprite: Image.Image,
    slot_xy: tuple[int, int],
    cross: bool,
    lift: int = 0,
) -> None:
    x, y = slot_xy
    if cross:
        sprite = sprite.rotate(90, expand=True)
    x += (CW - sprite.width) // 2
    y += (CH - sprite.height) // 2 - lift
    canvas.paste(sprite, (x, y), sprite)


@lru_cache(maxsize=8)
def _glow_sprite(width: int, height: int, color: tuple[int, int, int], strength: int) -> Image.Image:
    """Мягкое свечение-ореол под карту."""
    pad = 70
    img = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad, pad, pad + width, pad + height], 18, fill=(*color, strength))
    return img.filter(ImageFilter.GaussianBlur(28))


def _paste_glow(canvas: Image.Image, slot_xy: tuple[int, int], cross: bool, strength: int = 90) -> None:
    w, h = (CH, CW) if cross else (CW, CH)
    glow = _glow_sprite(w, h, GOLD, strength)
    x = slot_xy[0] + (CW - glow.width) // 2
    y = slot_xy[1] + (CH - glow.height) // 2
    canvas.paste(glow, (x, y), glow)


def _smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


def render_collage(drawn: list[DrawnCard], spread: Spread, subtitle: str = "") -> Image.Image:
    base, pos = _base(spread, subtitle)
    canvas = base.copy()
    for dc, slot, xy in zip(drawn, spread.slots, pos):
        _paste_glow(canvas, xy, slot.cross, strength=70)
        _paste_slot(canvas, _card_face(dc.card.id, dc.is_reversed), xy, slot.cross)
    return canvas


def _squeeze(sprite: Image.Image, factor: float) -> Image.Image:
    w = max(2, round(sprite.width * factor))
    return sprite.resize((w, sprite.height), Image.BILINEAR)


def iter_frames(drawn: list[DrawnCard], spread: Spread, subtitle: str = "") -> Iterator[Image.Image]:
    """Кадры ритуала: рубашки ложатся по одной, затем карты открываются
    с плавным переворотом, подъёмом и золотой вспышкой."""
    base, pos = _base(spread, subtitle)
    back = _card_back()
    faces = [_card_face(dc.card.id, dc.is_reversed) for dc in drawn]
    n = len(drawn)
    state: list[str | None] = [None] * n  # None | "back" | "face"
    reveal_age = [999] * n                # кадров с момента открытия (для затухающей вспышки)

    def frame(anim_idx: int | None = None, anim_sprite: Image.Image | None = None, lift: int = 0) -> Image.Image:
        canvas = base.copy()
        for i, (slot, xy) in enumerate(zip(spread.slots, pos)):
            if state[i] == "face":
                flash = max(0, 160 - reveal_age[i] * 22)  # вспышка гаснет ~7 кадров
                _paste_glow(canvas, xy, slot.cross, strength=70 + flash)
                _paste_slot(canvas, faces[i], xy, slot.cross)
            elif state[i] == "back" and anim_idx != i:
                _paste_slot(canvas, back, xy, slot.cross)
            if anim_idx == i and anim_sprite is not None:
                _paste_glow(canvas, xy, slot.cross, strength=110)
                _paste_slot(canvas, anim_sprite, xy, slot.cross, lift=lift)
        for i in range(n):
            reveal_age[i] += 1
        return canvas

    def repeat(img: Image.Image, times: int) -> Iterator[Image.Image]:
        for _ in range(times):
            yield img

    def fade_scale(sprite: Image.Image, t: float) -> Image.Image:
        """Появление: карта опускается на стол, вырастая из 55% и проявляясь."""
        f = 0.55 + 0.45 * t
        s = sprite.resize((max(2, round(sprite.width * f)), max(2, round(sprite.height * f))), Image.BILINEAR)
        alpha = s.getchannel("A").point(lambda a: round(a * min(1.0, t * 1.4)))
        s.putalpha(alpha)
        return s

    yield frame()
    # раздача: каждая рубашка прилетает с масштабированием и растворением
    deal_steps = 6
    deal_hold = 2 if n > 4 else 4
    for i in range(n):
        for step in range(1, deal_steps + 1):
            t = _smoothstep(step / deal_steps)
            sprite = fade_scale(back, t)
            lift = round((1 - t) * 34)
            yield frame(anim_idx=i, anim_sprite=sprite, lift=lift)
        state[i] = "back"
        yield from repeat(frame(), deal_hold)
    # перевороты: smoothstep-изинг, карта приподнимается на пике
    flip_steps = 10
    hold_after = 6 if n > 4 else 10
    for i in range(n):
        state[i] = "back"
        for step in range(1, flip_steps + 1):
            t = _smoothstep(step / flip_steps)
            factor = abs(math.cos(math.pi * t))
            lift = round(math.sin(math.pi * t) * 16)
            sprite = _squeeze(back if t < 0.5 else faces[i], max(factor, 0.04))
            yield frame(anim_idx=i, anim_sprite=sprite, lift=lift)
        state[i] = "face"
        reveal_age[i] = 0
        for _ in range(hold_after):
            yield frame()
    # долгая финальная пауза, чтобы зацикленный повтор не мельтешил
    final = render_collage(drawn, spread, subtitle)
    yield from repeat(final, FPS * 4)


def render_daily_card(dc: DrawnCard, date_str: str = "") -> Image.Image:
    """Статичная открытка «Карта дня»: крупная карта в золотом сиянии."""
    w, h = 720, 1120
    img = Image.new("RGB", (w, h), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))
    import random

    rnd = random.Random(dc.card.id)  # свой рисунок звёзд у каждой карты
    for _ in range(140):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r = rnd.choice((1, 1, 1, 2))
        c = 90 + rnd.randrange(110)
        d.ellipse([x, y, x + r, y + r], fill=(c, c, min(255, c + 25)))

    title_font = _font("DejaVuSerif-Bold.ttf", 46)
    tw = d.textlength("Карта дня", font=title_font)
    d.text(((w - tw) / 2, 46), "Карта дня", font=title_font, fill=GOLD)
    if date_str:
        sub_font = _font("DejaVuSans.ttf", 22)
        sw = d.textlength(date_str, font=sub_font)
        d.text(((w - sw) / 2, 104), date_str, font=sub_font, fill=LABEL_COLOR)

    card_w = 380
    card = _card_face(dc.card.id, dc.is_reversed, width=card_w)
    cx, cy = (w - card.width) // 2, 170
    # многослойное сияние
    for pad, alpha in ((110, 40), (70, 70), (36, 110)):
        halo = Image.new("RGBA", (card.width + pad * 2, card.height + pad * 2), (0, 0, 0, 0))
        ImageDraw.Draw(halo).rounded_rectangle(
            [pad, pad, pad + card.width, pad + card.height], 22, fill=(*GOLD, alpha)
        )
        halo = halo.filter(ImageFilter.GaussianBlur(pad // 2))
        img.paste(halo, (cx - pad, cy - pad), halo)
    img.paste(card, (cx, cy), card)

    name_font = _font("DejaVuSerif-Bold.ttf", 36)
    nw = d.textlength(dc.card.name, font=name_font)
    ny = cy + card.height + 44
    d.text(((w - nw) / 2, ny), dc.card.name, font=name_font, fill=GOLD)
    tag = "перевёрнутое положение" if dc.is_reversed else "прямое положение"
    tag_font = _font("DejaVuSans.ttf", 22)
    tw2 = d.textlength(tag, font=tag_font)
    d.text(((w - tw2) / 2, ny + 52), tag, font=tag_font, fill=LABEL_COLOR)
    return img

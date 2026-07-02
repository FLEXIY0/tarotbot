"""Рендер расклада: статичный коллаж и кадры анимации переворота (Pillow)."""

import math
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from bot.deck import DrawnCard
from bot.spreads import Spread

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
BACK_PATH = ROOT / "assets" / "back.png"

CW = 200                      # ширина карты на канве
CH = round(CW * 900 / 520)    # высота (пропорции сканов)
MARGIN = 56
TITLE_H = 0  # заголовок в кадре убран: он дублировал подпись сообщения и резался
LABEL_H = 40
FPS = 24
MAX_MEDIA_RATIO = 1.13
RITUAL_SECONDS = 20  # общая длина гифки ритуала

BG_TOP = (13, 12, 24)
BG_BOTTOM = (31, 25, 48)
GOLD = (201, 170, 108)
GOLD_DIM = (128, 110, 78)
LABEL_COLOR = (152, 148, 176)


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


@lru_cache(maxsize=8)
def _vignette_mask(w: int, h: int) -> Image.Image:
    small = Image.new("L", (64, 64), 0)
    px = small.load()
    for y in range(64):
        for x in range(64):
            dx, dy = (x - 31.5) / 32, (y - 31.5) / 32
            d = (dx * dx + dy * dy) ** 0.5
            px[x, y] = min(110, max(0, round((d - 0.62) / 0.55 * 110)))
    return small.resize((w, h), Image.BILINEAR)


def premium_bg(w: int, h: int, seed: str = "arcana", stars: int | None = None) -> Image.Image:
    """Фирменный фон: чернильный градиент, редкие звёзды с тонкими искрами,
    виньетка и волосяная золотая рамка с уголками."""
    import random

    img = Image.new("RGB", (w, h), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    rnd = random.Random(seed)
    n_dots = stars if stars is not None else w * h // 26000
    for _ in range(n_dots):
        x, y = rnd.randrange(w), rnd.randrange(h)
        c = 110 + rnd.randrange(70)
        od.point((x, y), fill=(c, c, min(255, c + 14), 255))
    for _ in range(max(3, n_dots // 7)):  # тонкие четырёхлучевые искры
        x, y = rnd.randrange(w), rnd.randrange(h)
        r = rnd.choice((5, 7, 9))
        a = 70 + rnd.randrange(60)
        od.line([(x - r, y), (x + r, y)], fill=(*GOLD, a), width=1)
        od.line([(x, y - r), (x, y + r)], fill=(*GOLD, a), width=1)
    img.paste(overlay, (0, 0), overlay)

    img.paste((0, 0, 0), (0, 0), _vignette_mask(w, h))

    d = ImageDraw.Draw(img)
    inset = 16
    d.rounded_rectangle([inset, inset, w - inset - 1, h - inset - 1], 10, outline=GOLD_DIM, width=1)
    for cx, cy in ((inset, inset), (w - inset - 1, inset), (inset, h - inset - 1), (w - inset - 1, h - inset - 1)):
        d.polygon([(cx, cy - 5), (cx + 5, cy), (cx, cy + 5), (cx - 5, cy)], fill=GOLD)
    return img


def _tracked(d: ImageDraw.ImageDraw, center_x: float, y: int, text: str,
             font: ImageFont.FreeTypeFont, fill, tracking: int = 2) -> None:
    """Текст с разрядкой букв (letter-spacing) по центру."""
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = center_x - total / 2
    for ch, cw in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill)
        x += cw + tracking


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
    # Telegram обрезает вытянутые гифки в пузыре — держим кадр почти квадратным
    max_ratio = MAX_MEDIA_RATIO
    if h > w * max_ratio:
        new_w = math.ceil(h / max_ratio)
        shift = (new_w - w) // 2
        pos = [(x + shift, y) for x, y in pos]
        w = new_w
    return pos, w + w % 2, h + h % 2


def _base(spread: Spread, subtitle: str = "") -> tuple[Image.Image, list[tuple[int, int]]]:
    pos, w, h = _slot_px(spread)
    img = premium_bg(w, h, seed=spread.key)
    d = ImageDraw.Draw(img)
    label_font = _font("DejaVuSans.ttf", 14)
    for slot, (x, y) in zip(spread.slots, pos):
        if slot.cross:
            continue  # подпись поперечной карты наложилась бы на первую
        _tracked(d, x + CW / 2, y + CH + 12, slot.label.upper(), label_font, LABEL_COLOR, tracking=2)
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
def _shadow_sprite(width: int, height: int) -> Image.Image:
    """Мягкая тень под карту — глубина без блеска."""
    pad = 34
    img = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad, pad + 8, pad + width, pad + height + 10], 16, fill=(0, 0, 0, 105))
    return img.filter(ImageFilter.GaussianBlur(12))


def _paste_shadow(canvas: Image.Image, slot_xy: tuple[int, int], cross: bool, alpha: float = 1.0) -> None:
    w, h = (CH, CW) if cross else (CW, CH)
    shadow = _shadow_sprite(w, h)
    if alpha < 1.0:
        shadow = shadow.copy()
        shadow.putalpha(shadow.getchannel("A").point(lambda a: round(a * alpha)))
    x = slot_xy[0] + (CW - shadow.width) // 2
    y = slot_xy[1] + (CH - shadow.height) // 2
    canvas.paste(shadow, (x, y), shadow)


# --- изинги (теория: ease-out для влетающих объектов, in-out для переворотов) ---


def _smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _ease_out_back(t: float, s: float = 1.4) -> float:
    """Лёгкий overshoot при приземлении — карта чуть «переезжает» и садится."""
    t -= 1
    return 1 + (s + 1) * t**3 + s * t**2


def render_collage(drawn: list[DrawnCard], spread: Spread, subtitle: str = "") -> Image.Image:
    base, pos = _base(spread, subtitle)
    canvas = base.copy()
    for dc, slot, xy in zip(drawn, spread.slots, pos):
        _paste_shadow(canvas, xy, slot.cross)
        _paste_slot(canvas, _card_face(dc.card.id, dc.is_reversed), xy, slot.cross)
    return canvas


def _squeeze(sprite: Image.Image, factor: float) -> Image.Image:
    w = max(2, round(sprite.width * factor))
    return sprite.resize((w, sprite.height), Image.BILINEAR)


def iter_frames(drawn: list[DrawnCard], spread: Spread, subtitle: str = "") -> Iterator[Image.Image]:
    """Кадры ритуала.

    Раздача: карты выбрасываются из центра стола веером — быстрый вылет,
    вращение, гасящееся к приземлению, лёгкий overshoot (ease-out-back),
    перекрывающийся стаггер между картами. Затем перевороты с in-out изингом.
    Без блеска — глубину даёт мягкая тень.
    """
    base, pos = _base(spread, subtitle)
    back = _card_back()
    faces = [_card_face(dc.card.id, dc.is_reversed) for dc in drawn]
    n = len(drawn)

    # центр стола — точка вылета
    cxs = [xy[0] + CW / 2 for xy in pos]
    cys = [xy[1] + CH / 2 for xy in pos]
    origin = (sum(cxs) / n, sum(cys) / n)

    # детерминированное вращение: чередуем направление, ~⅔ оборота
    spins = [(-1 if i % 2 else 1) * (200 + (i * 53) % 70) for i in range(n)]

    landed = [False] * n
    opened = [False] * n

    def draw_landed(canvas: Image.Image) -> None:
        for i, (slot, xy) in enumerate(zip(spread.slots, pos)):
            if landed[i]:
                _paste_shadow(canvas, xy, slot.cross)
                _paste_slot(canvas, faces[i] if opened[i] else back, xy, slot.cross)

    def repeat(img: Image.Image, times: int) -> Iterator[Image.Image]:
        for _ in range(times):
            yield img

    yield base.copy()

    # --- раздача из центра, стаггер: следующая карта стартует до приземления предыдущей
    deal_dur = 11          # ~0.46 c полёта
    stagger = 5 if n > 4 else 7
    total = (n - 1) * stagger + deal_dur
    for g in range(1, total + 1):
        canvas = base.copy()
        draw_landed(canvas)
        for i, (slot, xy) in enumerate(zip(spread.slots, pos)):
            lt = (g - i * stagger) / deal_dur
            if lt <= 0 or landed[i]:
                continue
            if lt >= 1:
                landed[i] = True
                _paste_shadow(canvas, xy, slot.cross)
                _paste_slot(canvas, back, xy, slot.cross)
                continue
            t_pos = _ease_out_back(_ease_out_cubic(lt))     # траектория с мягким overshoot
            t_rot = _ease_out_cubic(lt)                     # вращение гаснет к посадке
            target = (xy[0] + CW / 2, xy[1] + CH / 2)
            x = origin[0] + (target[0] - origin[0]) * t_pos
            y = origin[1] + (target[1] - origin[1]) * t_pos
            scale = 0.62 + 0.38 * _ease_out_cubic(lt)
            angle = spins[i] * (1 - t_rot) + (90 if slot.cross else 0)
            sprite = back.resize(
                (max(2, round(CW * scale)), max(2, round(CH * scale))), Image.BILINEAR
            ).rotate(angle, expand=True, resample=Image.BILINEAR)
            _paste_shadow(canvas, xy, slot.cross, alpha=0.35 * lt)
            canvas.paste(sprite, (round(x - sprite.width / 2), round(y - sprite.height / 2)), sprite)
        yield canvas

    settle = base.copy()
    draw_landed(settle)
    yield from repeat(settle, 7)

    # --- перевороты: in-out изинг, лёгкий подъём на пике
    flip_steps = 10
    hold_after = 5 if n > 4 else 9
    for i, (slot, xy) in enumerate(zip(spread.slots, pos)):
        for step in range(1, flip_steps + 1):
            t = _smoothstep(step / flip_steps)
            factor = abs(math.cos(math.pi * t))
            lift = round(math.sin(math.pi * t) * 12)
            sprite = _squeeze(back if t < 0.5 else faces[i], max(factor, 0.04))
            canvas = base.copy()
            landed[i] = False
            draw_landed(canvas)
            landed[i] = True
            _paste_shadow(canvas, xy, slot.cross)
            _paste_slot(canvas, sprite, xy, slot.cross, lift=lift)
            yield canvas
        opened[i] = True
        canvas = base.copy()
        draw_landed(canvas)
        yield from repeat(canvas, hold_after)

    # финальная пауза добивает гифку до RITUAL_SECONDS + затухание на стыке цикла
    emitted = [1 + total + 7 + n * (flip_steps + hold_after)]  # кадры динамики выше
    final = render_collage(drawn, spread, subtitle)
    fade_frames = 10
    hold = max(FPS * 3, FPS * RITUAL_SECONDS - emitted[0] - fade_frames)
    yield from repeat(final, hold)
    dark = Image.new("RGB", final.size, BG_TOP)
    for step in range(1, fade_frames + 1):
        yield Image.blend(final, dark, _smoothstep(step / fade_frames))


def with_fade_in(frames: Iterator[Image.Image], fade_frames: int = 8) -> Iterator[Image.Image]:
    """Плавное проявление первых кадров — цикл гифки замыкается мягко."""
    first = next(frames)
    dark = Image.new("RGB", first.size, BG_TOP)
    for step in range(fade_frames):
        yield Image.blend(dark, first, _smoothstep((step + 1) / fade_frames))
    yield first
    yield from frames


DAILY_W, DAILY_H = 720, 812          # пропорция ~1.13 — не режется в пузыре Telegram
DAILY_FRAMES = 132                   # 5.5 c бесшовного цикла


def _daily_scene(dc: DrawnCard, date_str: str):
    """База «живой» карты дня: фон, тексты, спрайты для анимации."""
    import random

    w, h = DAILY_W, DAILY_H
    base = premium_bg(w, h, seed=dc.card.id, stars=24)
    d = ImageDraw.Draw(base)

    card_w = 350
    card = _card_face(dc.card.id, dc.is_reversed, width=card_w)
    cx, cy = (w - card.width) // 2, 48

    name_font = _font("DejaVuSerif-Bold.ttf", 33)
    nw = d.textlength(dc.card.name, font=name_font)
    ny = cy + card.height + 34
    d.text(((w - nw) / 2, ny), dc.card.name, font=name_font, fill=GOLD)
    # тонкий орнамент-разделитель: линия — ромб — линия
    oy = ny + 52
    d.line([(w / 2 - 70, oy), (w / 2 - 14, oy)], fill=GOLD_DIM, width=1)
    d.line([(w / 2 + 14, oy), (w / 2 + 70, oy)], fill=GOLD_DIM, width=1)
    d.polygon([(w / 2, oy - 4), (w / 2 + 4, oy), (w / 2, oy + 4), (w / 2 - 4, oy)], fill=GOLD)
    tag = "ПЕРЕВЁРНУТОЕ ПОЛОЖЕНИЕ" if dc.is_reversed else "ПРЯМОЕ ПОЛОЖЕНИЕ"
    _tracked(d, w / 2, oy + 14, tag, _font("DejaVuSans.ttf", 14), LABEL_COLOR, tracking=3)

    # два состояния ореола — между ними дышим блендом
    halos = []
    for alpha in (34, 88):
        pad = 84
        halo = Image.new("RGBA", (card.width + pad * 2, card.height + pad * 2), (0, 0, 0, 0))
        ImageDraw.Draw(halo).rounded_rectangle(
            [pad, pad, pad + card.width, pad + card.height], 20, fill=(*GOLD, alpha)
        )
        halos.append(halo.filter(ImageFilter.GaussianBlur(38)))

    # мерцающие звёзды: позиция, радиус, фаза
    rnd = random.Random(dc.card.id)
    stars = [
        (rnd.randrange(34, w - 34), rnd.randrange(34, h - 34), rnd.choice((1, 1, 2)), rnd.random() * math.tau)
        for _ in range(80)
    ]

    # блик: диагональная светлая полоса, пробегает по карте раз за цикл
    bw = 150
    band = Image.new("RGBA", (bw, card.height * 2), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    for x in range(bw):
        a = round(70 * (1 - abs(x - bw / 2) / (bw / 2)))
        bd.line([(x, 0), (x, band.height)], fill=(255, 250, 235, a))
    band = band.rotate(24, expand=True, resample=Image.BILINEAR)

    return base, card, (cx, cy), halos, stars, band


def iter_daily_frames(dc: DrawnCard, date_str: str = ""):
    """Бесшовный цикл: карта парит и чуть покачивается, ореол дышит,
    звёзды мерцают, по карте пробегает блик. Без переворотов."""
    base, card, (cx, cy), (halo_lo, halo_hi), stars, band = _daily_scene(dc, date_str)
    pad = (halo_lo.width - card.width) // 2
    n = DAILY_FRAMES
    for f in range(n):
        t = f / n  # все движения — целые гармоники, стык цикла бесшовный
        frame = base.copy()
        d = ImageDraw.Draw(frame)
        for sx, sy, r, phase in stars:
            k = 0.5 + 0.5 * math.sin(math.tau * t + phase)
            c = round(60 + 120 * k)
            d.ellipse([sx, sy, sx + r, sy + r], fill=(c, c, min(255, c + 16)))

        float_y = round(10 * math.sin(math.tau * t))
        tilt = 2.0 * math.sin(math.tau * t + math.pi / 2)

        halo = Image.blend(halo_lo, halo_hi, 0.5 + 0.5 * math.sin(math.tau * t + math.pi / 3))
        frame.paste(halo, (cx - pad, cy - pad + float_y), halo)

        sprite = card.copy()
        sweep_x = round(-band.width + (card.width + 2 * band.width) * t)
        gloss = Image.new("RGBA", sprite.size, (0, 0, 0, 0))
        gloss.paste(band, (sweep_x, -(band.height - sprite.height) // 2), band)
        gloss.putalpha(ImageChops.multiply(gloss.getchannel("A"), sprite.getchannel("A")))
        sprite.alpha_composite(gloss)
        if abs(tilt) > 0.05:
            sprite = sprite.rotate(tilt, expand=True, resample=Image.BILINEAR)
        frame.paste(
            sprite,
            (cx - (sprite.width - card.width) // 2, cy + float_y - (sprite.height - card.height) // 2),
            sprite,
        )
        yield frame


def render_daily_card(dc: DrawnCard, date_str: str = "") -> Image.Image:
    """Статичная открытка «Карта дня»: крупная карта в золотом сиянии."""
    w, h = DAILY_W, DAILY_H
    img = premium_bg(w, h, seed=dc.card.id, stars=24)
    d = ImageDraw.Draw(img)

    card_w = 350
    card = _card_face(dc.card.id, dc.is_reversed, width=card_w)
    cx, cy = (w - card.width) // 2, 48
    # многослойное сияние
    for pad, alpha in ((110, 40), (70, 70), (36, 110)):
        halo = Image.new("RGBA", (card.width + pad * 2, card.height + pad * 2), (0, 0, 0, 0))
        ImageDraw.Draw(halo).rounded_rectangle(
            [pad, pad, pad + card.width, pad + card.height], 22, fill=(*GOLD, alpha)
        )
        halo = halo.filter(ImageFilter.GaussianBlur(pad // 2))
        img.paste(halo, (cx - pad, cy - pad), halo)
    img.paste(card, (cx, cy), card)

    name_font = _font("DejaVuSerif-Bold.ttf", 33)
    nw = d.textlength(dc.card.name, font=name_font)
    ny = cy + card.height + 34
    d.text(((w - nw) / 2, ny), dc.card.name, font=name_font, fill=GOLD)
    tag = "ПЕРЕВЁРНУТОЕ ПОЛОЖЕНИЕ" if dc.is_reversed else "ПРЯМОЕ ПОЛОЖЕНИЕ"
    _tracked(d, w / 2, ny + 58, tag, _font("DejaVuSans.ttf", 14), LABEL_COLOR, tracking=3)
    return img

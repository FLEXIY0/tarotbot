"""Витрина каталога: одно изображение с примерами всех раскладов."""

from PIL import Image, ImageDraw

from bot.deck import CARD_BY_ID, DrawnCard
from bot.render import BG_TOP, render_collage
from bot.spreads import SPREADS

# фиксированные «красивые» карты для витрины (все прямые)
_SAMPLES = {
    "one": ["major_arcana_sun"],
    "three": ["major_arcana_fool", "major_arcana_lovers", "major_arcana_star"],
    "relationship": [
        "minor_arcana_cups_queen", "minor_arcana_cups_2",
        "minor_arcana_wands_king", "minor_arcana_cups_10",
    ],
    "celtic": [
        "major_arcana_magician", "major_arcana_priestess", "major_arcana_empress",
        "major_arcana_emperor", "major_arcana_fortune", "major_arcana_star",
        "major_arcana_sun", "major_arcana_temperance", "major_arcana_strength",
        "major_arcana_world",
    ],
}


CELL_W, CELL_H = 780, 640
HEADER_H = 78  # подпись над плиткой: название и цена


def _fit(img: Image.Image) -> Image.Image:
    """Вписывает коллаж в ячейку витрины, сохраняя пропорции."""
    scale = min(CELL_W / img.width, CELL_H / img.height)
    return img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)


def render_catalog_promo() -> Image.Image:
    from bot.render import GOLD, LABEL_COLOR, _font

    tiles = []
    for key, card_ids in _SAMPLES.items():
        spread = SPREADS[key]
        drawn = [DrawnCard(CARD_BY_ID[cid], False) for cid in card_ids]
        tiles.append((spread, _fit(render_collage(drawn, spread))))

    pad = 26
    cell_full = HEADER_H + CELL_H
    total_w = CELL_W * 2 + pad * 3
    total_h = cell_full * 2 + pad * 3
    sheet = Image.new("RGB", (total_w + total_w % 2, total_h + total_h % 2), BG_TOP)
    d = ImageDraw.Draw(sheet)
    title_font = _font("DejaVuSerif-Bold.ttf", 30)
    price_font = _font("DejaVuSans.ttf", 21)
    for i, (spread, tile) in enumerate(tiles):
        x0 = pad + (i % 2) * (CELL_W + pad)
        y0 = pad + (i // 2) * (cell_full + pad)
        tw = d.textlength(spread.title, font=title_font)
        d.text((x0 + (CELL_W - tw) / 2, y0), spread.title, font=title_font, fill=GOLD)
        price = f"{spread.price} ✦"
        pw = d.textlength(price, font=price_font)
        d.text((x0 + (CELL_W - pw) / 2, y0 + 40), price, font=price_font, fill=LABEL_COLOR)
        sheet.paste(tile, (x0 + (CELL_W - tile.width) // 2, y0 + HEADER_H + (CELL_H - tile.height) // 2))
    return sheet

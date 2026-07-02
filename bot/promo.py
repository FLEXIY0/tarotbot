"""Витрина каталога: одно изображение с примерами всех раскладов."""

from PIL import Image

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


CELL_W, CELL_H = 780, 700


def _fit(img: Image.Image) -> Image.Image:
    """Вписывает коллаж в ячейку витрины, сохраняя пропорции."""
    scale = min(CELL_W / img.width, CELL_H / img.height)
    return img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)


def render_catalog_promo() -> Image.Image:
    tiles = []
    for key, card_ids in _SAMPLES.items():
        spread = SPREADS[key]
        drawn = [DrawnCard(CARD_BY_ID[cid], False) for cid in card_ids]
        tiles.append(_fit(render_collage(drawn, spread, f"{spread.price} ★")))

    pad = 26
    total_w = CELL_W * 2 + pad * 3
    total_h = CELL_H * 2 + pad * 3
    sheet = Image.new("RGB", (total_w + total_w % 2, total_h + total_h % 2), BG_TOP)
    for i, tile in enumerate(tiles):
        cx = pad + (i % 2) * (CELL_W + pad) + (CELL_W - tile.width) // 2
        cy = pad + (i // 2) * (CELL_H + pad) + (CELL_H - tile.height) // 2
        sheet.paste(tile, (cx, cy))
    return sheet

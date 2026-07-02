"""Детальный разбор расклада без ИИ — классические техники Таро.

Всё вычислимо из выпавших карт: позиционные трактовки (ранг x масть либо
тема старшего аркана), баланс стихий, доля перевёрнутых, повторы рангов,
квинтэссенция. Когда подключён LLM, этот же разбор уходит в промпт.
"""

from collections import Counter

from bot.deck import DrawnCard
from bot.spreads import Spread

# --- знания ---

SUITS = {
    "wands": ("Жезлы", "огонь", "энергию, дело, амбиции и творческий напор"),
    "cups": ("Кубки", "вода", "чувства, отношения и интуицию"),
    "swords": ("Мечи", "воздух", "мысли, решения, слова и правду"),
    "pentacles": ("Пентакли", "земля", "материю, деньги, тело и ресурсы"),
}

RANKS = {
    "ace": "чистый импульс, семя нового",
    "2": "выбор и поиск равновесия",
    "3": "первый ощутимый результат, рост",
    "4": "устойчивость, фундамент, пауза",
    "5": "перелом, вызов, точка напряжения",
    "6": "выравнивание, помощь, движение к лучшему",
    "7": "переоценка, стратегия, испытание на верность пути",
    "8": "набранная сила процесса, мастерство в движении",
    "9": "кульминация, почти собранный урожай",
    "10": "завершение цикла во всей полноте",
    "page": "весть и свежий взгляд ученика",
    "knight": "направленное действие, поход за целью",
    "queen": "зрелая внутренняя сила, глубокое владение стихией",
    "king": "внешняя власть над стихией, ответственность мастера",
}

MAJOR_THEMES = {
    "major_arcana_fool": (0, "энергия чистого начала: жизнь предлагает шагнуть в неизвестное налегке, доверившись дороге"),
    "major_arcana_magician": (1, "точка сборки воли: все инструменты уже на столе, дело за намерением"),
    "major_arcana_priestess": (2, "знание приходит не из логики: ответ уже созрел внутри и просит тишины"),
    "major_arcana_empress": (3, "энергия плодородия: то, что поливаешь вниманием, будет расти пышно"),
    "major_arcana_emperor": (4, "запрос на структуру: границы, правила и порядок сейчас не клетка, а опора"),
    "major_arcana_hierophant": (5, "проверенный путь: традиция, наставник или правило, которое не стоит ломать сгоряча"),
    "major_arcana_lovers": (6, "выбор сердцем: соединение возможно только при честном «да» с обеих сторон"),
    "major_arcana_chariot": (7, "воля к победе: противоположные силы можно запрячь в одну колесницу"),
    "major_arcana_strength": (8, "мягкая сила: не сломать, а приручить — терпением и принятием"),
    "major_arcana_hermit": (9, "время внутреннего света: ответы ищутся в уединении, а не в шуме"),
    "major_arcana_fortune": (10, "поворот колеса: цикл сменяется, и удача любит тех, кто замечает момент"),
    "major_arcana_justice": (11, "закон причины и следствия: всё взвешивается, и равновесие будет восстановлено"),
    "major_arcana_hanged": (12, "пауза-перевёртыш: ситуация не двигается, пока не сменится угол зрения"),
    "major_arcana_death": (13, "великое обновление: что-то должно завершиться, чтобы освободить место живому"),
    "major_arcana_temperance": (14, "алхимия меры: несоединимое соединяется терпением и точной дозировкой"),
    "major_arcana_devil": (15, "узел зависимости: цепи держат ровно настолько, насколько в них верится"),
    "major_arcana_tower": (16, "молния истины: рушится только то, что стояло на ложном основании"),
    "major_arcana_star": (17, "тихая надежда: рана уже промыта, и путь подсвечен далёким, но верным светом"),
    "major_arcana_moon": (18, "туман и отражения: не всё, что пугает, реально — но и не всё видимое правдиво"),
    "major_arcana_sun": (19, "ясный полдень: энергия успеха, витальности и честной радости"),
    "major_arcana_judgement": (20, "зов пробуждения: прошлое подводит итог и выдаёт второй шанс"),
    "major_arcana_world": (21, "круг замкнулся: достигнутая целостность и выход на новый виток"),
}

RANK_VALUES = {"ace": 1, "page": 11, "knight": 12, "queen": 13, "king": 14}

REPEAT_TEXTS = {
    "ace": "несколько Тузов — сразу несколько новых дверей открываются одновременно",
    "2": "повтор Двоек — тема выбора звучит настойчиво, откладывать его не выйдет",
    "3": "повтор Троек — период роста: первые плоды видны в нескольких сферах сразу",
    "4": "повтор Четвёрок — жизнь просит остановиться и укрепить фундамент",
    "5": "несколько Пятёрок — испытание идёт по нескольким фронтам, это проверка на прочность",
    "6": "повтор Шестёрок — волна выравнивания: помощь и облегчение приходят отовсюду",
    "7": "повтор Семёрок — время стратегии, а не спонтанности",
    "8": "повтор Восьмёрок — события ускоряются, процесс набрал собственную силу",
    "9": "повтор Девяток — многое подходит к кульминации одновременно",
    "10": "повтор Десяток — сразу несколько циклов завершаются: большой рубеж",
    "page": "несколько Пажей — вести и новые знакомства посыплются одно за другим",
    "knight": "несколько Рыцарей — вокруг много движения и чужой активности",
    "queen": "несколько Королев — сильное женское влияние на ситуацию",
    "king": "несколько Королей — в деле сталкиваются интересы влиятельных людей",
}

_CONNECTIVES = (
    "В этой позиции карта говорит:",
    "Здесь звучит",
    "Эта позиция раскрывается через",
    "Смысл позиции:",
)


def _rank_of(card_id: str) -> str | None:
    if "minor_arcana" not in card_id:
        return None
    return card_id.rsplit("_", 1)[1]


def _card_sentence(dc: DrawnCard) -> str:
    """Развёрнутое предложение о карте: тема аркана либо ранг x масть."""
    if dc.card.arcana == "major":
        theme = MAJOR_THEMES[dc.card.id][1]
        base = f"Это старший аркан — {theme}."
    else:
        rank = _rank_of(dc.card.id)
        suit_name, element, domain = SUITS[dc.card.suit]
        base = (f"{suit_name} ({element}) отвечают за {domain}; "
                f"номинал карты — {RANKS[rank]}.")
    if dc.is_reversed:
        base += (" Перевёрнутое положение разворачивает энергию внутрь: она либо "
                 "блокирована, либо проживается скрыто и просит осознания.")
    return base


def positions_block(drawn: list[DrawnCard], spread: Spread) -> str:
    parts = []
    for i, (slot, dc) in enumerate(zip(spread.slots, drawn)):
        conn = _CONNECTIVES[i % len(_CONNECTIVES)]
        parts.append(
            f"**{slot.label} — {dc.title}**\n"
            f"{conn} {dc.meaning}. {_card_sentence(dc)}"
        )
    return "\n\n".join(parts)


def energies_block(drawn: list[DrawnCard]) -> str:
    lines = []
    n = len(drawn)

    majors = [dc for dc in drawn if dc.card.arcana == "major"]
    if len(majors) >= max(2, n // 2):
        lines.append(f"Старших арканов {len(majors)} из {n} — ситуация судьбоносная: "
                     "события ведёт не бытовая логика, а более крупные силы, и их урок важнее тактики.")
    elif not majors and n >= 3:
        lines.append("Старших арканов нет — всё в твоих руках: ситуация бытовая, "
                     "управляемая обычными решениями и действиями.")

    suits = Counter(dc.card.suit for dc in drawn if dc.card.suit)
    if suits:
        top_suit, top_count = suits.most_common(1)[0]
        if top_count >= max(2, n // 2):
            name, element, domain = SUITS[top_suit]
            lines.append(f"Доминирует стихия {element} ({name}) — расклад сейчас в первую очередь про {domain}.")
        if n >= 4:
            absent = [SUITS[s][1] for s in SUITS if s not in suits]
            if len(absent) in (1, 2) and len(majors) < n:
                lines.append(f"Полностью отсутствует стихия {' и '.join(absent)} — "
                             "именно этого ресурса ситуации не хватает, добавь его сознательно.")

    reversed_count = sum(dc.is_reversed for dc in drawn)
    if reversed_count == 0 and n >= 3:
        lines.append("Все карты прямые — энергия течёт свободно, внешних и внутренних блоков почти нет.")
    elif reversed_count >= max(2, round(n * 0.5)):
        lines.append(f"Перевёрнутых карт {reversed_count} из {n} — процесс развернулся внутрь: "
                     "многое решается не действиями, а внутренней работой, и торопить события бесполезно.")

    ranks = Counter(r for dc in drawn if (r := _rank_of(dc.card.id)))
    for rank, count in ranks.items():
        if count >= 2:
            lines.append(REPEAT_TEXTS[rank].capitalize() + ".")

    return "\n".join(f"— {line}" for line in lines)


def quintessence(drawn: list[DrawnCard]) -> tuple[str, str]:
    """Квинтэссенция: сумма номиналов, сведённая к старшему аркану."""
    total = 0
    for dc in drawn:
        if dc.card.arcana == "major":
            total += MAJOR_THEMES[dc.card.id][0]
        else:
            rank = _rank_of(dc.card.id)
            total += RANK_VALUES.get(rank) or int(rank)
    while total > 21:
        total -= 22
    for card_id, (num, theme) in MAJOR_THEMES.items():
        if num == total:
            from bot.deck import CARD_BY_ID

            return CARD_BY_ID[card_id].name, theme
    raise RuntimeError("unreachable")


def detailed_reading(
    drawn: list[DrawnCard], spread: Spread, question: str | None, name: str | None
) -> str:
    """Полный текстовый разбор без LLM: позиции, энергии, квинтэссенция, совет."""
    who = f"{name}, " if name else ""
    intro = (f"{who}вот подробный разбор расклада «{spread.title}»"
             + (f" на твой вопрос: «{question}»." if question else "."))

    parts = [intro, positions_block(drawn, spread)]

    energies = energies_block(drawn)
    if energies:
        parts.append("**Энергии расклада**\n" + energies)

    q_name, q_theme = quintessence(drawn)
    parts.append(f"**Квинтэссенция — {q_name}**\n"
                 f"Если свести все карты расклада к одному итоговому аркану, получится {q_name}. "
                 f"Его послание — {q_theme}. Это сквозной урок всей ситуации.")

    advice_card = drawn[-1]
    parts.append("**Совет карт**\n"
                 f"Финальная карта — {advice_card.title}. Её темы ({advice_card.meaning}) — "
                 "это то, что важно увидеть и учесть в первую очередь. Карты описывают течения, "
                 "но руль всегда у тебя: опирайся на сильные стихии расклада и сознательно "
                 "добавляй недостающие.")

    return "\n\n".join(parts)


def analysis_for_prompt(drawn: list[DrawnCard], spread: Spread) -> str:
    """Краткая выжимка техник для промпта LLM — делает ИИ-трактовку глубже."""
    q_name, q_theme = quintessence(drawn)
    lines = [f"Квинтэссенция расклада: {q_name} ({q_theme})."]
    if energies := energies_block(drawn):
        lines.append("Энергии: " + energies.replace("— ", "").replace("\n", " "))
    return "\n".join(lines)

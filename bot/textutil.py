import html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)


def md_bold_to_html(text: str) -> str:
    """LLM пишет **жирным** в markdown; бот работает в HTML parse mode."""
    return _BOLD.sub(r"<b>\1</b>", html.escape(text))

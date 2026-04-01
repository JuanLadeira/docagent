import re

# Cobre os principais blocos Unicode de emojis, símbolos e variantes de apresentação.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # símbolos, pictogramas, emoticons, transporte, etc.
    "\U0001FA00-\U0001FA9F"  # símbolos estendidos
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed chars, regional indicators
    "\u2600-\u26FF"           # símbolos miscelâneos
    "\u2700-\u27BF"           # dingbats
    "\uFE0F"                  # variante de apresentação emoji
    "\u200D"                  # zero-width joiner
    "\u20E3"                  # combining enclosing keycap
    "]+",
    flags=re.UNICODE,
)


def strip_emojis(text: str) -> str:
    """Remove emojis e símbolos Unicode decorativos de um texto."""
    return _EMOJI_RE.sub("", text).strip()

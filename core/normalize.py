from __future__ import annotations

import re
import unicodedata

_APOSTROPHES = "'ʼ`´'"  # ' ʼ ` ´ '
_PUNCT = re.compile(r"[^\w'\s]", flags=re.UNICODE)  # keep word chars, ' and whitespace
_WS = re.compile(r"\s+", flags=re.UNICODE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    for ch in _APOSTROPHES:
        text = text.replace(ch, "'")
    text = _PUNCT.sub(" ", text)   # dashes, commas, quotes, etc. → space
    text = text.replace("_", " ")  # underscore is a word char but unwanted
    text = _WS.sub(" ", text)
    return text.strip()

from __future__ import annotations
import re
import unicodedata

_LIST_NUM = re.compile(r"^\(?\d+[.)]?\s+")          # "1 ", "1. ", "(1) ", "(1 "
_LEAD_JUNK = re.compile(r"^[\s|.:,!/'()]+")          # stray leading punct/space (NOT « „ " or letters)
_LOWER_UA = re.compile(r"[а-яіїєґ]")
_QUOTES = {"«": '"', "»": '"', "„": '"', "“": '"', "”": '"', "‹": '"', "›": '"'}
_APOS = "'ʼ`´’"  # ' ʼ ` ´ ’  -> '
_WS = re.compile(r"\s+")

def clean_text(text: str) -> str:
    t = _LIST_NUM.sub("", text, count=1)
    t = _LEAD_JUNK.sub("", t).strip()
    if t and _LOWER_UA.match(t[0]):
        t = t[0].upper() + t[1:]
    return t

def to_plain(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    for q, a in _QUOTES.items():
        t = t.replace(q, a)
    for ch in _APOS:
        t = t.replace(ch, "'")
    t = t.replace("…", "...")
    t = t.replace("—", "-").replace("–", "-")        # em/en dash -> hyphen; spacing kept distinguishes тире/дефіс
    t = _WS.sub(" ", t).strip()
    return t

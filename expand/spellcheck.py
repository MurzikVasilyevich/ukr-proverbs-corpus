from __future__ import annotations

import csv
import os
import re

_WORD = re.compile(r"[а-яіїєґ'']+")
_CYR_WORD = re.compile(r"^[а-яіїєґ''-]+$")


def tokens(text: str) -> list[str]:
    return [w.strip("''") for w in _WORD.findall(text.lower()) if w.strip("''")]


def load_vocab(corpus_path: str, hunspell_path: str | None = None) -> set[str]:
    vocab: set[str] = set()
    with open(corpus_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vocab.update(tokens(row.get("text", "")))
    if hunspell_path and os.path.exists(hunspell_path):
        with open(hunspell_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                word = line.split("/", 1)[0].strip().lower()
                if word and _CYR_WORD.match(word):
                    vocab.add(word.strip("''"))
    return vocab


def flag_unknown(text: str, vocab: set[str]) -> list[str]:
    return [t for t in tokens(text) if t not in vocab]


def is_clean(text: str, vocab: set[str]) -> bool:
    return not flag_unknown(text, vocab)

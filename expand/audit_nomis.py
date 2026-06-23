"""Measure extraction fidelity: how closely each extracted `text` matches the OCR.

A faithful transcription's `text` (original orthography) should closely match some OCR
line (modulo stripped entry-numbers/sigla). Low best-match = the LLM likely rewrote/
normalized the wording (e.g. кумові->тобі) rather than transcribing.
"""
from __future__ import annotations

import csv
import glob
import random
import re

from rapidfuzz import fuzz, process

OCR_DIR = "expand/work/nomis_txt"
NOMIS = "data/sources/nomis.csv"
SAMPLE = 400


def ocr_pool() -> list[str]:
    pool = []
    for f in glob.glob(f"{OCR_DIR}/page-*.txt"):
        for line in open(f, encoding="utf-8"):
            s = line.strip()
            if len(s) >= 8 and re.search(r"[а-яіїєґА-ЯІЇЄҐ]", s):
                pool.append(s)
    return pool


def main() -> None:
    pool = ocr_pool()
    rows = list(csv.DictReader(open(NOMIS, encoding="utf-8")))
    random.seed(13)
    sample = random.sample(rows, min(SAMPLE, len(rows)))
    buckets = {"faithful>=90": 0, "minor 80-90": 0, "weak 70-80": 0, "diverged<70": 0}
    diverged = []
    for r in sample:
        text = r["text"]
        m = process.extractOne(text, pool, scorer=fuzz.token_set_ratio)
        score = m[1] if m else 0
        if score >= 90:
            buckets["faithful>=90"] += 1
        elif score >= 80:
            buckets["minor 80-90"] += 1
        elif score >= 70:
            buckets["weak 70-80"] += 1
        else:
            buckets["diverged<70"] += 1
            diverged.append((round(score), text[:55], (m[0][:55] if m else "")))
    n = len(sample)
    print(f"=== fidelity audit (n={n}, text vs OCR token_set_ratio) ===")
    for k, v in buckets.items():
        print(f"  {k:14s}: {v:4d}  ({100*v/n:.1f}%)")
    print(f"\n  diverged<70 examples (score | extracted text | best OCR match):")
    for sc, t, o in diverged[:12]:
        print(f"   {sc:3d} | {t}  ||  {o}")
    # calibration: the коровая line
    cor = next((r for r in rows if "коровая" in r["text"] and ("тобі" in r["text"] or "кумов" in r["text"])), None)
    if cor:
        m = process.extractOne(cor["text"], pool, scorer=fuzz.token_set_ratio)
        print(f"\n  коровая calibration: text={cor['text']!r} -> best OCR {round(m[1])}: {m[0]!r}")


if __name__ == "__main__":
    main()

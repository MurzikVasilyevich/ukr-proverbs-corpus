from __future__ import annotations

import csv

_TAXONOMY_PATH = "enrich/taxonomy.csv"


def load_taxonomy(path: str = _TAXONOMY_PATH) -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        return {row["key"]: row["ukrainian_label"] for row in csv.DictReader(f)}


TAXONOMY_KEYS: frozenset[str] = frozenset(load_taxonomy().keys())


def validate_categories(cats: list[str], keys: frozenset[str]) -> list[str]:
    if not isinstance(cats, list) or not (1 <= len(cats) <= 3):
        raise ValueError(f"categories must be a list of 1-3 keys, got {cats!r}")
    bad = [c for c in cats if c not in keys]
    if bad:
        raise ValueError(f"categories not in taxonomy: {bad!r}")
    return cats


def validate_pass_a_record(rec: dict, keys: frozenset[str]) -> None:
    if not isinstance(rec.get("id"), str) or not rec["id"]:
        raise ValueError(f"pass-A record missing id: {rec!r}")
    validate_categories(rec.get("categories"), keys)
    if not isinstance(rec.get("explanation_clean"), str):
        raise ValueError(f"pass-A record missing explanation_clean: {rec!r}")


def validate_pass_b_record(rec: dict) -> None:
    if not isinstance(rec.get("id"), str) or not rec["id"]:
        raise ValueError(f"pass-B record missing id: {rec!r}")
    if not isinstance(rec.get("modern_text"), str) or not rec["modern_text"].strip():
        raise ValueError(f"pass-B record missing modern_text: {rec!r}")

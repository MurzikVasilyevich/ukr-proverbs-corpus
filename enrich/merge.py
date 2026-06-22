from __future__ import annotations

import glob
import json
import os

from enrich.schema import TAXONOMY_KEYS, validate_pass_a_record, validate_pass_b_record

_COLUMNS = ["id", "text", "normalized_text", "modern_text", "keyword",
            "explanation", "category", "sources", "source_refs", "variant_group"]


def load_outputs(dir_path: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(glob.glob(os.path.join(dir_path, "*.json"))):
        with open(p, encoding="utf-8") as f:
            for rec in json.load(f):
                rid = rec.get("id")
                if rid in out:
                    raise ValueError(f"duplicate id {rid!r} across output files")
                out[rid] = rec
    return out


def merge(corpus_rows, pass_a, pass_b, keys=TAXONOMY_KEYS):
    corpus_ids = {r["id"] for r in corpus_rows}
    extra_a = set(pass_a) - corpus_ids
    extra_b = set(pass_b) - corpus_ids
    if extra_a or extra_b:
        raise ValueError(f"pass output has ids not in corpus: {sorted(extra_a | extra_b)[:5]}")
    result = []
    for row in corpus_rows:
        rid = row["id"]
        if rid not in pass_a:
            raise ValueError(f"id {rid} missing from pass A")
        if rid not in pass_b:
            raise ValueError(f"id {rid} missing from pass B")
        a, b = pass_a[rid], pass_b[rid]
        validate_pass_a_record(a, keys)
        validate_pass_b_record(b)
        enriched = {
            "id": rid,
            "text": row["text"],
            "normalized_text": row["normalized_text"],
            "modern_text": b["modern_text"],
            "keyword": row["keyword"],
            "explanation": a["explanation_clean"],
            "category": ";".join(a["categories"]),
            "sources": row["sources"],
            "source_refs": row["source_refs"],
            "variant_group": row["variant_group"],
        }
        result.append({c: enriched[c] for c in _COLUMNS})
    return result

from __future__ import annotations

import csv
import json

from core.schema import CanonicalRecord


def finalize(records: list[CanonicalRecord]) -> list[CanonicalRecord]:
    records.sort(key=lambda r: (r.normalized_text, r.text))
    for n, rec in enumerate(records, start=1):
        rec.id = f"p{n:06d}"
    return records


def write_csv(records: list[CanonicalRecord], path: str) -> None:
    fields = [
        "id", "text", "normalized_text", "keyword",
        "explanation", "category", "sources", "source_refs", "variant_group",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "id": r.id,
                "text": r.text,
                "normalized_text": r.normalized_text,
                "keyword": r.keyword,
                "explanation": r.csv_explanation(),
                "category": r.category,
                "sources": ";".join(r.sources()),
                "source_refs": ";".join(r.source_refs()),
                "variant_group": r.variant_group,
            })


def _or_none(value: str) -> str | None:
    return value if value else None


def write_json(records: list[CanonicalRecord], path: str) -> None:
    payload = [
        {
            "id": r.id,
            "text": r.text,
            "normalized_text": r.normalized_text,
            "keyword": _or_none(r.keyword),
            "category": _or_none(r.category),
            "variant_group": _or_none(r.variant_group),
            "annotations": [
                {
                    "source": a.source,
                    "ref": _or_none(a.ref),
                    "explanation": _or_none(a.explanation),
                }
                for a in r.annotations
            ],
        }
        for r in records
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

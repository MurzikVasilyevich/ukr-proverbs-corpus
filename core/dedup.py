from __future__ import annotations

from core.schema import CanonicalRecord


def merge_exact(records: list[CanonicalRecord]) -> list[CanonicalRecord]:
    groups: dict[str, list[CanonicalRecord]] = {}
    order: list[str] = []
    for rec in records:
        key = rec.normalized_text
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(rec)

    merged: list[CanonicalRecord] = []
    for key in order:
        group = groups[key]
        annotations = [a for rec in group for a in rec.annotations]
        keyword = next((rec.keyword for rec in group if rec.keyword), "")
        text = min(rec.text for rec in group)
        merged.append(
            CanonicalRecord(
                text=text,
                normalized_text=key,
                keyword=keyword,
                annotations=annotations,
            )
        )
    return merged

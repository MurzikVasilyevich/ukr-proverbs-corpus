from __future__ import annotations

from collections import Counter, defaultdict

from rapidfuzz import fuzz

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


def _tokens(norm: str) -> list[str]:
    return [t for t in norm.split() if len(t) >= 3]


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def link_variants(
    records: list[CanonicalRecord],
    threshold: int = 85,
    rare_df_cap: int = 40,
) -> list[CanonicalRecord]:
    n = len(records)
    token_df: Counter[str] = Counter()
    rec_tokens: list[list[str]] = []
    for rec in records:
        toks = _tokens(rec.normalized_text)
        rec_tokens.append(toks)
        for t in set(toks):
            token_df[t] += 1

    index: dict[str, list[int]] = defaultdict(list)
    for i, toks in enumerate(rec_tokens):
        for t in set(toks):
            if token_df[t] <= rare_df_cap:
                index[t].append(i)

    uf = _UnionFind(n)
    seen_pairs: set[tuple[int, int]] = set()
    for members in index.values():
        for a_idx in range(len(members)):
            for b_idx in range(a_idx + 1, len(members)):
                i, j = members[a_idx], members[b_idx]
                pair = (i, j)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                if fuzz.token_set_ratio(
                    records[i].normalized_text, records[j].normalized_text
                ) >= threshold:
                    uf.union(i, j)

    members_by_root: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        members_by_root[uf.find(i)].append(i)

    multi = [m for m in members_by_root.values() if len(m) >= 2]
    multi.sort(key=lambda m: min(records[i].normalized_text for i in m))
    for gid, m in enumerate(multi, start=1):
        label = f"v{gid:04d}"
        for i in m:
            records[i].variant_group = label
    return records

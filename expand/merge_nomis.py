"""SP6 Stage A (deterministic): merge Nomis into the corpus, preserving enrichment.

Builds a bare corpus WITH nomis.csv (to a temp dir), re-attaches prior enrichment by
normalized_text, overrides modern_text for Nomis net-new from nomis.csv, and reports stats.
Writes a provisional corpus + the list of net-new ids needing categorization. Does NOT
touch the live corpus.csv.
"""
from __future__ import annotations

import csv
import collections
import json

import build as build_mod
from core.normalize import normalize
from expand.reattach import reattach

TMP = "/tmp/nomis_bare"
PRIOR = "corpus.csv"
NOMIS = "data/sources/nomis.csv"
PROV_CSV = "/tmp/nomis_merge_corpus.csv"
NEWIDS = "/tmp/nomis_new_ids.json"
_COLS = ["id", "text", "normalized_text", "modern_text", "keyword",
         "explanation", "category", "sources", "source_refs", "variant_group"]


def _read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    # 1. bare build WITH nomis.csv -> temp (does not overwrite live corpus.csv)
    stats = build_mod.build(sources_dir="data/sources", out_dir=TMP)
    print("bare build:", stats["total"], "per_source:", stats["per_source"])

    base_rows = _read(f"{TMP}/corpus.csv")
    enriched_rows = _read(PRIOR)
    attached, new_ids = reattach(base_rows, enriched_rows)

    # override modern_text for Nomis net-new from nomis.csv
    nomis_modern = {}
    for r in _read(NOMIS):
        nomis_modern[normalize(r["text"])] = r.get("modern_text") or r["text"]
    new_id_set = set(new_ids)
    overridden = 0
    for row in attached:
        if row["id"] in new_id_set:
            nm = nomis_modern.get(row["normalized_text"])
            if nm:
                row["modern_text"] = nm
                overridden += 1

    # stats
    per_source = collections.Counter()
    for row in attached:
        for s in row["sources"].split(";"):
            if s:
                per_source[s] += 1
    print(f"\nmerged total: {len(attached)}  (was 40444)")
    print(f"net-new ids: {len(new_ids)}  | modern_text overridden from nomis: {overridden}")
    print("per_source:", dict(per_source.most_common()))
    # how many net-new still lack a category (need categorize pass)
    need_cat = [r["id"] for r in attached if r["id"] in new_id_set and not r["category"]]
    print(f"net-new needing categorization: {len(need_cat)}")

    with open(PROV_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_COLS)
        w.writeheader()
        for r in attached:
            w.writerow({c: r[c] for c in _COLS})
    json.dump(new_ids, open(NEWIDS, "w"))
    print(f"\nwrote provisional {PROV_CSV} + {NEWIDS}")


if __name__ == "__main__":
    main()

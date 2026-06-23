"""SP6 Stage C: apply categories to the provisional merged corpus, write final corpus.csv/json."""
from __future__ import annotations

import csv, glob, json, collections

from enrich.export import write_enriched_csv, enrich_json, write_json
from enrich.schema import TAXONOMY_KEYS

PROV = "/tmp/nomis_merge_corpus.csv"
CATOUT = "/tmp/nomis_cat/out"
BARE_JSON = "/tmp/nomis_bare/corpus.json"
_COLS = ["id", "text", "normalized_text", "modern_text", "keyword",
         "explanation", "category", "sources", "source_refs", "variant_group"]


def main():
    rows = list(csv.DictReader(open(PROV, encoding="utf-8")))
    # category map from haiku output, dropping invalid keys (SP2 lesson)
    cat = {}
    dropped = 0
    for f in glob.glob(f"{CATOUT}/batch-*.json"):
        for rec in json.load(open(f, encoding="utf-8")):
            keys = [k for k in rec.get("categories", []) if k in TAXONOMY_KEYS]
            dropped += len(rec.get("categories", [])) - len(keys)
            if keys:
                cat[rec["id"]] = ";".join(keys[:3])
    applied = 0
    for r in rows:
        if not r["category"] and r["id"] in cat:
            r["category"] = cat[r["id"]]
            applied += 1
    missing = [r["id"] for r in rows if not r["category"]]
    print(f"categories applied: {applied} | invalid keys dropped: {dropped} | still uncategorized: {len(missing)}")

    write_enriched_csv(rows, "corpus.csv")
    base_json = json.load(open(BARE_JSON, encoding="utf-8"))
    rows_by_id = {r["id"]: r for r in rows}
    write_json(enrich_json(base_json, rows_by_id), "corpus.json")

    per_source = collections.Counter()
    for r in rows:
        for s in r["sources"].split(";"):
            if s:
                per_source[s] += 1
    print(f"total: {len(rows)} | per_source: {dict(per_source.most_common())}")
    print(f"with category: {sum(1 for r in rows if r['category'])} | with modern_text!=text: {sum(1 for r in rows if r['modern_text'] and r['modern_text']!=r['text'])}")


if __name__ == "__main__":
    main()

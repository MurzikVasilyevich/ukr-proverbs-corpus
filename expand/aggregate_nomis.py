"""Aggregate Nomis extraction batch JSONs -> data/sources/nomis.csv (ref,text,modern_text)."""
from __future__ import annotations

import csv
import glob
import json
import os

BATCH_DIR = "expand/work/nomis_extract"
OUT = "data/sources/nomis.csv"


def main() -> None:
    rows = []
    seen = set()
    dupes = 0
    files = sorted(glob.glob(os.path.join(BATCH_DIR, "batch-*.json")))
    for f in files:
        data = json.load(open(f, encoding="utf-8"))
        for item in data:
            text = (item.get("text") or "").strip()
            modern = (item.get("modern_text") or "").strip()
            ref = (item.get("ref") or "").strip()
            if not text:
                continue
            key = text  # exact-text dedup within Nomis
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            rows.append({"ref": ref, "text": text, "modern_text": modern or text})
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["ref", "text", "modern_text"])
        w.writeheader()
        w.writerows(rows)
    print(f"batches: {len(files)} | wrote: {len(rows)} | within-Nomis exact dupes dropped: {dupes}")
    print(f"with modern!=text: {sum(1 for r in rows if r['modern_text'] != r['text'])}")
    print(f"with ref: {sum(1 for r in rows if r['ref'])}")


if __name__ == "__main__":
    main()

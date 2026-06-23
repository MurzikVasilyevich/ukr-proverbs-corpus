"""Write net-new Nomis entries into input batch files for the categorize Workflow."""
import csv, json, os

ROWS = "/tmp/nomis_merge_corpus.csv"
NEWIDS = "/tmp/nomis_new_ids.json"
INDIR = "/tmp/nomis_cat/in"
BATCH = 200

os.makedirs(INDIR, exist_ok=True)
new_ids = set(json.load(open(NEWIDS)))
rows = [r for r in csv.DictReader(open(ROWS, encoding="utf-8")) if r["id"] in new_ids and not r["category"]]
items = [{"id": r["id"], "text": r["modern_text"] or r["text"]} for r in rows]
n = 0
for i in range(0, len(items), BATCH):
    n += 1
    json.dump(items[i:i+BATCH], open(f"{INDIR}/batch-{n:04d}.json", "w"), ensure_ascii=False)
print(f"net-new to categorize: {len(items)} -> {n} input batches of {BATCH} in {INDIR}")

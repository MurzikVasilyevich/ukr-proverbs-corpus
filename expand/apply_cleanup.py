from __future__ import annotations
import csv, collections
from core.clean import clean_text, to_plain
from core.normalize import normalize

def apply_row(row: dict, corrections: dict[str, dict]) -> dict:
    r = dict(row)
    corr = corrections.get(r.get("id", ""))
    old_text = r.get("text", "")
    text = to_plain(corr["text"] if corr and corr.get("text") else clean_text(old_text))
    r["text"] = text
    if corr and corr.get("modern_text"):
        r["modern_text"] = to_plain(clean_text(corr["modern_text"]))
    else:
        old_modern = r.get("modern_text", "")
        if (not old_modern) or clean_text(old_modern).strip() == clean_text(old_text).strip():
            r["modern_text"] = text          # modern mirrored the original -> mirror the correction
        else:
            r["modern_text"] = to_plain(clean_text(old_modern))
    r["normalized_text"] = normalize(text)
    return r

def load_corrections(path: str) -> dict[str, dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return {x["id"]: x for x in csv.DictReader(f)}
    except FileNotFoundError:
        return {}

def apply_csv(in_path: str, out_path: str, corrections_path: str = "corrections.csv") -> dict:
    corrections = load_corrections(corrections_path)
    with open(in_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fields = rows[0].keys() if rows else []
    out = [apply_row(r, corrections) for r in rows]
    # dup-check: new exact-duplicate normalized_text
    seen = collections.Counter(r["normalized_text"] for r in out)
    dups = [n for n, c in seen.items() if c > 1]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields)); w.writeheader(); w.writerows(out)
    return {"rows": len(out), "dup_norm_keys": len(dups)}

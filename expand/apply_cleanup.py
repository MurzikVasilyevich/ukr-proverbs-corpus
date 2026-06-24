from __future__ import annotations
import csv, json, collections
from core.clean import clean_text, to_plain
from core.normalize import normalize

def apply_row(row: dict, corrections: dict[str, dict]) -> dict:
    r = dict(row)
    corr = corrections.get(r.get("id", ""))
    # 1. curated correction (homoglyph/judgment) overrides text; else deterministic clean_text
    text = corr["text"] if corr and corr.get("text") else clean_text(r.get("text", ""))
    text = to_plain(text)                                 # 2. ASCII canonicalize
    r["text"] = text
    # modern_text: curated override if given, else clean+plain the existing modern (fallback to text)
    modern_src = corr["modern_text"] if corr and corr.get("modern_text") else r.get("modern_text", "")
    r["modern_text"] = to_plain(clean_text(modern_src)) if modern_src else text
    r["normalized_text"] = normalize(text)                # 3. recompute key
    return r

def load_corrections(path: str) -> dict[str, dict]:
    try:
        return {x["id"]: x for x in csv.DictReader(open(path, encoding="utf-8"))}
    except FileNotFoundError:
        return {}

def apply_csv(in_path: str, out_path: str, corrections_path: str = "corrections.csv") -> dict:
    corrections = load_corrections(corrections_path)
    rows = list(csv.DictReader(open(in_path, encoding="utf-8")))
    fields = rows[0].keys() if rows else []
    out = [apply_row(r, corrections) for r in rows]
    # dup-check: new exact-duplicate normalized_text
    seen = collections.Counter(r["normalized_text"] for r in out)
    dups = [n for n, c in seen.items() if c > 1]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields)); w.writeheader(); w.writerows(out)
    return {"rows": len(out), "dup_norm_keys": len(dups)}

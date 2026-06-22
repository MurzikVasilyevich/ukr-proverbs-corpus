# Ukrainian Proverbs Corpus — Expansion 3a (Bobkova) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the ~800 already-OCR'd Bobkova proverbs into the corpus (fetch → consolidate → LLM OCR-cleanup → `bobkova` adapter → SP1 pipeline), preserving all existing SP2 enrichment by re-attaching on `normalized_text` and enriching only net-new entries.

**Architecture:** TDD Python adds `expand/consolidate.py`, `adapters/bobkova.py`, `expand/reattach.py`, and a one-line `build.py` hook. Two non-deterministic LLM steps (OCR cleanup, net-new categorization) are **controller-run** via the Workflow tool (cannot nest in a subagent). Enriched fields are committed data artifacts.

**Tech Stack:** Python 3 (pandas, rapidfuzz, pytest); Workflow tool. Reuses `core/`, `enrich/`.

**Spec:** `docs/superpowers/specs/2026-06-22-ukr-proverbs-expansion-bobkova-design.md`

## Global Constraints

- Python 3.10+; deps limited to pandas, rapidfuzz, pytest. Use `.venv/bin/python`.
- Verbatim `text` is never mutated by normalization; for Bobkova the cleaned OCR text *is* the source `text`.
- Bobkova source key is exactly `Bobkova`; entries carry `Annotation(source="Bobkova", ref=<page-stem>)`.
- Enriched `corpus.csv` keeps the SP2 10-column order: `id, text, normalized_text, modern_text, keyword, explanation, category, sources, source_refs, variant_group`.
- Enrichment is preserved by matching `normalized_text` against the existing enriched `corpus.csv`; only net-new proverbs get categorized. For Bobkova, `modern_text` = cleaned `text` (already modern).
- Variant grouping uses the SP2-tuned settings: `link_variants` threshold 85, then dissolve groups > 8 (`recompute_variant_groups(rows, 85, 8)`).
- Losslessness: 100% id coverage; every entry has a matched enrichment or a fresh one; no record dropped.
- Commits use local identity `MurzikVasilyevich <vasilyevichmurzik@gmail.com>`; append the session footer (Co-Authored-By + Claude-Session) to every commit. Branch `feat/expand-bobkova`.
- Pushing: `origin` (public Murzik) needs `gh auth switch --user MurzikVasilyevich` then HTTPS; `dmytro` (private) is SSH and account-independent.
- **Task types:** `[IMPL]` = TDD implementer subagent. `[CONTROLLER-RUN]` = executed by the controller (Workflow tool); not dispatched to an implementer.

---

### Task 1 [IMPL]: expand/ scaffold + consolidate.py

**Files:**
- Create: `expand/__init__.py` (empty)
- Create: `expand/consolidate.py`
- Create: `tests/fixtures/bobkova_pages/000.csv`
- Create: `tests/fixtures/bobkova_pages/001.csv`
- Create: `tests/test_expand_consolidate.py`

**Interfaces:**
- Produces: `consolidate(pages_dir: str) -> list[dict]` — reads every `*.csv` in `pages_dir` (sorted by filename), each having a `text` column; returns `[{"ref": <filename-stem>, "text": <stripped text>} ...]` for every non-empty `text`, in (filename, file-row) order.

- [ ] **Step 1: Create fixtures** — `tests/fixtures/bobkova_pages/000.csv`:
```csv
,text
1,Горе тільки рака красить.
0,Лихо нікого не красить.
2,
```
`tests/fixtures/bobkova_pages/001.csv`:
```csv
,text
0,І в Відні люди бідні.
1,"Канада добрий край, як не маєш грошей, то здихай."
```

- [ ] **Step 2: Write the failing test** — `tests/test_expand_consolidate.py`:
```python
from expand.consolidate import consolidate


def test_consolidate_flattens_pages_in_order():
    rows = consolidate("tests/fixtures/bobkova_pages")
    # empty-text row in 000.csv is skipped -> 2 + 2 = 4
    assert len(rows) == 4
    assert rows[0] == {"ref": "000", "text": "Горе тільки рака красить."}
    assert rows[1] == {"ref": "000", "text": "Лихо нікого не красить."}
    assert rows[2]["ref"] == "001"
    assert rows[3]["text"] == "Канада добрий край, як не маєш грошей, то здихай."
```

- [ ] **Step 3: Run test, verify fail** — `.venv/bin/python -m pytest tests/test_expand_consolidate.py -v` → FAIL (ModuleNotFoundError).

- [ ] **Step 4: Implement** — `expand/consolidate.py`:
```python
from __future__ import annotations

import csv
import glob
import os


def consolidate(pages_dir: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(pages_dir, "*.csv"))):
        ref = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            for rec in csv.DictReader(f):
                text = (rec.get("text") or "").strip()
                if text:
                    rows.append({"ref": ref, "text": text})
    return rows
```

- [ ] **Step 5: Run test, verify pass** — PASS (1 passed).

- [ ] **Step 6: Commit**
```bash
git add expand/__init__.py expand/consolidate.py tests/fixtures/bobkova_pages tests/test_expand_consolidate.py
git commit -m "feat(expand): consolidate Bobkova page CSVs"
```

---

### Task 2 [IMPL]: adapters/bobkova.py

**Files:**
- Create: `adapters/bobkova.py`
- Create: `tests/fixtures/bobkova_sample.csv`
- Create: `tests/test_bobkova_adapter.py`

**Interfaces:**
- Consumes: `CanonicalRecord`, `Annotation` from `core.schema`.
- Produces: `load(path: str) -> list[CanonicalRecord]` — reads `bobkova.csv` (`ref,text`); one record per row: `text=row["text"]`, `keyword=""`, `annotations=[Annotation(source="Bobkova", ref=row["ref"])]`; skips empty `text`; `normalized_text` left blank.

- [ ] **Step 1: Create fixture** — `tests/fixtures/bobkova_sample.csv`:
```csv
ref,text
005,Горе тільки рака красить.
005,Лихо нікого не красить.
012,""
```

- [ ] **Step 2: Write the failing test** — `tests/test_bobkova_adapter.py`:
```python
from adapters.bobkova import load


def test_maps_rows_to_records():
    recs = load("tests/fixtures/bobkova_sample.csv")
    assert len(recs) == 2                      # empty-text row skipped
    r = recs[0]
    assert r.text == "Горе тільки рака красить."
    assert r.keyword == ""
    assert r.annotations[0].source == "Bobkova"
    assert r.annotations[0].ref == "005"
    assert r.normalized_text == ""
```

- [ ] **Step 3: Run test, verify fail** — FAIL (ModuleNotFoundError).

- [ ] **Step 4: Implement** — `adapters/bobkova.py`:
```python
from __future__ import annotations

import pandas as pd

from core.schema import Annotation, CanonicalRecord

SOURCE = "Bobkova"


def load(path: str) -> list[CanonicalRecord]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    records: list[CanonicalRecord] = []
    for _, row in df.iterrows():
        text = row["text"].strip()
        if not text:
            continue
        records.append(
            CanonicalRecord(
                text=text,
                keyword="",
                annotations=[Annotation(source=SOURCE, ref=row["ref"].strip())],
            )
        )
    return records
```

- [ ] **Step 5: Run test, verify pass** — PASS (1 passed).

- [ ] **Step 6: Commit**
```bash
git add adapters/bobkova.py tests/fixtures/bobkova_sample.csv tests/test_bobkova_adapter.py
git commit -m "feat(expand): bobkova source adapter"
```

---

### Task 3 [IMPL]: build.py — conditionally include Bobkova

**Files:**
- Modify: `build.py` (in `build_records`)
- Create: `tests/test_build_bobkova.py`

**Interfaces:**
- Consumes: `adapters.bobkova.load`.
- Produces: `build_records(sources_dir)` additionally loads `{sources_dir}/bobkova.csv` **iff it exists** (so SP1 fixtures without bobkova are unaffected).

- [ ] **Step 1: Write the failing test** — `tests/test_build_bobkova.py`:
```python
import csv, os, shutil
from build import build_records


def _seed(dst):
    os.makedirs(dst, exist_ok=True)
    for f in ("franko.csv", "proverbs.csv", "proverbs_sources.csv"):
        shutil.copy(f"tests/fixtures/golden/{f}", os.path.join(dst, f))


def test_bobkova_included_when_present(tmp_path):
    d = tmp_path / "src"; _seed(str(d))
    with open(d / "bobkova.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ref", "text"]); w.writeheader()
        w.writerow({"ref": "005", "text": "Унікальна бобковська приказка тут."})
    recs = build_records(str(d))
    texts = [r.text for r in recs]
    assert "Унікальна бобковська приказка тут." in texts
    assert any("Bobkova" in r.sources() for r in recs)


def test_bobkova_skipped_when_absent(tmp_path):
    d = tmp_path / "src"; _seed(str(d))
    recs = build_records(str(d))            # no bobkova.csv -> no error
    assert all("Bobkova" not in r.sources() for r in recs)
```

- [ ] **Step 2: Run test, verify fail** — `.venv/bin/python -m pytest tests/test_build_bobkova.py -v` → FAIL (Bobkova text absent).

- [ ] **Step 3: Implement** — in `build.py`, edit `build_records` to add the bobkova load after the mlodzynskyi load. The function becomes:
```python
def build_records(sources_dir: str) -> list[CanonicalRecord]:
    records = franko.load(os.path.join(sources_dir, "franko.csv"))
    records += mlodzynskyi.load(
        os.path.join(sources_dir, "proverbs.csv"),
        os.path.join(sources_dir, "proverbs_sources.csv"),
    )
    bobkova_path = os.path.join(sources_dir, "bobkova.csv")
    if os.path.exists(bobkova_path):
        from adapters import bobkova
        records += bobkova.load(bobkova_path)
    for rec in records:
        rec.normalized_text = normalize(rec.text)
    records = merge_exact(records)
    records = link_variants(records)
    records = finalize(records)
    return records
```
(Only the `bobkova_path` block is new; keep the rest identical. The top-of-file imports already cover `os`, `franko`, `mlodzynskyi`, `normalize`, `merge_exact`, `link_variants`, `finalize`.)

- [ ] **Step 4: Run test, verify pass** — `.venv/bin/python -m pytest tests/test_build_bobkova.py -v` → PASS (2 passed).

- [ ] **Step 5: Run full suite** — `.venv/bin/python -m pytest -q` → all pass (SP1 golden unaffected — its fixture dir has no bobkova.csv).

- [ ] **Step 6: Commit**
```bash
git add build.py tests/test_build_bobkova.py
git commit -m "feat(expand): include Bobkova in build when present"
```

---

### Task 4 [IMPL]: expand/reattach.py — preserve enrichment by normalized_text

**Files:**
- Create: `expand/reattach.py`
- Create: `tests/test_expand_reattach.py`

**Interfaces:**
- Produces: `reattach(base_rows: list[dict], enriched_rows: list[dict]) -> tuple[list[dict], list[str]]`.
  - `base_rows`: SP1 9-column dicts (`id, text, normalized_text, keyword, explanation, category, sources, source_refs, variant_group`).
  - `enriched_rows`: the existing enriched corpus (10-column, has `modern_text`, populated `category`, cleaned `explanation`).
  - Returns `(attached, new_ids)`. `attached` is 10-column dicts in `base_rows` order. For a base row whose `normalized_text` matches an enriched row: copy `modern_text`, `category`, `explanation` from the enriched row (enrichment preserved). For a base row with no match (net-new): `modern_text = text`, `category = ""` (to be filled), keep base `explanation`; its `id` is added to `new_ids`.

- [ ] **Step 1: Write the failing test** — `tests/test_expand_reattach.py`:
```python
from expand.reattach import reattach

ENR_COLS = ["id", "text", "normalized_text", "modern_text", "keyword",
            "explanation", "category", "sources", "source_refs", "variant_group"]


def _base(id, text, nt, expl="", src="Bobkova"):
    return {"id": id, "text": text, "normalized_text": nt, "keyword": "",
            "explanation": expl, "category": "", "sources": src,
            "source_refs": "005", "variant_group": ""}


def test_match_reuses_enrichment_and_new_is_flagged():
    enriched = [{"id": "p000050", "text": "Стара", "normalized_text": "стара",
                 "modern_text": "Стара (мод.)", "keyword": "", "explanation": "поясн",
                 "category": "wisdom_folly", "sources": "Franko1901",
                 "source_refs": "С", "variant_group": ""}]
    base = [
        _base("p000050", "Стара", "стара", src="Franko1901;Bobkova"),  # matches
        _base("p000051", "Нова приказка", "нова приказка"),            # net-new
    ]
    attached, new_ids = reattach(base, enriched)
    assert list(attached[0].keys()) == ENR_COLS
    assert attached[0]["modern_text"] == "Стара (мод.)"
    assert attached[0]["category"] == "wisdom_folly"
    assert attached[0]["explanation"] == "поясн"
    assert new_ids == ["p000051"]
    assert attached[1]["modern_text"] == "Нова приказка"   # modern_text = text
    assert attached[1]["category"] == ""
```

- [ ] **Step 2: Run test, verify fail** — FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement** — `expand/reattach.py`:
```python
from __future__ import annotations

_COLUMNS = ["id", "text", "normalized_text", "modern_text", "keyword",
            "explanation", "category", "sources", "source_refs", "variant_group"]


def reattach(base_rows: list[dict], enriched_rows: list[dict]) -> tuple[list[dict], list[str]]:
    by_norm = {r["normalized_text"]: r for r in enriched_rows}
    attached: list[dict] = []
    new_ids: list[str] = []
    for b in base_rows:
        e = by_norm.get(b["normalized_text"])
        if e is not None:
            modern_text = e["modern_text"]
            category = e["category"]
            explanation = e["explanation"]
        else:
            modern_text = b["text"]
            category = ""
            explanation = b["explanation"]
            new_ids.append(b["id"])
        row = {
            "id": b["id"], "text": b["text"], "normalized_text": b["normalized_text"],
            "modern_text": modern_text, "keyword": b["keyword"], "explanation": explanation,
            "category": category, "sources": b["sources"], "source_refs": b["source_refs"],
            "variant_group": b["variant_group"],
        }
        attached.append({c: row[c] for c in _COLUMNS})
    return attached, new_ids
```

- [ ] **Step 4: Run test, verify pass** — PASS (1 passed).

- [ ] **Step 5: Commit**
```bash
git add expand/reattach.py tests/test_expand_reattach.py
git commit -m "feat(expand): re-attach enrichment by normalized_text"
```

---

### Task 5 [CONTROLLER-RUN]: Fetch + consolidate + OCR-clean Bobkova → data/sources/bobkova.csv

Controller-run (Workflow). Produces the committed cleaned source artifact.

- [ ] **Step 1: Fetch** the 64 `data/bobkova_1/pages_OCR/*.csv` from
  `MurzikVasilyevich/Ukraininan-proverbs-and-adages-WIP` (raw GitHub) into `expand/work/pages/`.
- [ ] **Step 2: Consolidate** with `expand.consolidate.consolidate("expand/work/pages")` → raw `(ref,text)` rows (~800). Write `expand/work/bobkova_raw.csv`.
- [ ] **Step 3: OCR-clean** — batch the raw rows (size ~100) and run a small Workflow (haiku, ~8 agents) where each agent reads its batch and returns per-row `{ref, text_clean}` fixing OCR errors (stray capital `Й` mid-word, mis-recognized chars, broken splits) WITHOUT changing meaning. Use the SP2 file-based mechanism with the learned safeguards: one pass, id/row-level repair for gaps, line-salvage if an agent writes invalid JSON. Validate: every raw row has a cleaned counterpart.
- [ ] **Step 4: Write** `data/sources/bobkova.csv` (`ref,text` with cleaned text), UTF-8.
- [ ] **Step 5: Sanity** — row count ≈ raw count; spot-check 10 cleaned vs raw. (Committed in Task 6.)

---

### Task 6 [CONTROLLER-RUN]: Expanded build + reattach + enrich net-new + export

Controller-run.

- [ ] **Step 1: Build expanded base** to a temp dir (does not touch the live enriched corpus):
  `from build import build; build(sources_dir="data/sources", out_dir="/tmp/expand_base")`
  → `/tmp/expand_base/corpus.csv` (9-col base, new ids, includes Bobkova) + `corpus.json`.
- [ ] **Step 2: Reattach** — read the **current** enriched `corpus.csv` (old, 10-col) and the new base
  `/tmp/expand_base/corpus.csv`; `attached, new_ids = reattach(base_rows, enriched_old_rows)`. Record
  `len(new_ids)` (net-new) and merged/matched counts.
- [ ] **Step 3: Enrich net-new** — categorize the `new_ids` entries with a small Workflow (haiku),
  reusing `enrich.prompts.pass_a_prompt` + taxonomy (output `{id, categories, explanation_clean}`);
  drop-invalid-key normalization as in SP2. Fill `category` (`;`-joined) on those rows;
  `modern_text` already = text; `explanation` stays "". (If the spot-check finds archaic Bobkova
  forms, run a modern-spelling pass for those — see spec §9.)
- [ ] **Step 4: Tune variants** — `attached = recompute_variant_groups(attached, threshold=85, max_group_size=8)`.
- [ ] **Step 5: Export** — `write_enriched_csv(attached, "corpus.csv")`; `enrich_json(/tmp/expand_base/corpus.json, {id: row})` → `write_json(..., "corpus.json")`.
- [ ] **Step 6: Source registry** — add to `sources.csv`:
  `Bobkova,Українські народні прислів'я та приказки,,Бобкова В.І. (упоряд.)` (Year left blank, as for Mlodzynskyi; confirm the edition year and fill if known).
- [ ] **Step 7: Hard checks** — `corpus.csv` 10 cols; row count = old 35,165 + net-new; every `category` non-empty with keys ∈ taxonomy; every row has `modern_text`; `corpus.json` parses with same count.
- [ ] **Step 8: REPORT** — write `expand/REPORT.md`: pages fetched, raw rows, cleaned rows, total added, merged-into-existing, net-new, net-new categorized, new total, plus a small cleanup/category audit.
- [ ] **Step 9: Commit** (add `expand/work/*` to `.gitignore` first):
```bash
git add corpus.csv corpus.json sources.csv data/sources/bobkova.csv expand/REPORT.md .gitignore
git commit -m "feat(expand): ingest Bobkova (~800 proverbs), enrichment preserved"
```

---

### Task 7 [IMPL]: README + full suite + finish

**Files:**
- Modify: `README.md`
- Modify: `.gitignore` (add `expand/work/`)

- [ ] **Step 1:** Update `README.md`: add **Bobkova** to the Sources list (modern collection); refresh the stats block (new total, added/merged/net-new counts from `expand/REPORT.md`); note Bobkova entries are modern (so `modern_text` = `text`).
- [ ] **Step 2:** Ensure `.gitignore` has `expand/work/`.
- [ ] **Step 3:** Full suite — `.venv/bin/python -m pytest -q` → all pass.
- [ ] **Step 4: Commit & finish** (controller merges `feat/expand-bobkova` → main and pushes origin + dmytro via finishing-a-development-branch):
```bash
git add README.md .gitignore
git commit -m "docs(expand): document Bobkova source + refreshed stats"
```

---

## Self-Review

**1. Spec coverage:**
- §1 scope (ingest 64 OCR'd pages) → Tasks 5 (fetch/clean), 1–3 (consolidate/adapter/build). ✓
- §2 source (Bobkova key, sources.csv row) → Task 2 (`SOURCE="Bobkova"`), Task 6 Step 6. ✓
- §3 acquisition + cleanup → Task 5. ✓
- §4 enrichment preservation (re-attach by normalized_text; enrich net-new; modern_text=text) → Task 4 + Task 6 Steps 2–3. ✓
- §5 components → all tasks (expand/consolidate, reattach; adapters/bobkova; build hook). ✓
- §6 testing → Tasks 1,2,3,4 each TDD; integration via reattach test + Task 6 hard checks. ✓
- §7 variant tuning (85, cap 8) → Task 6 Step 4. ✓
- §8 expanded export → Task 6 Step 5. ✓

**2. Placeholder scan:** Bobkova year is intentionally blank in `sources.csv` (mirrors Mlodzynskyi's blank author; flagged to confirm), not an unfilled placeholder. REPORT/README counts come from real output. No "TBD/handle errors" steps; code steps contain complete code.

**3. Type consistency:** `consolidate -> [{"ref","text"}]` feeds the cleanup, whose output (`data/sources/bobkova.csv` `ref,text`) is read by `adapters/bobkova.load` (Task 2). `reattach(base_rows, enriched_rows) -> (attached, new_ids)` (Task 4) consumed in Task 6 Step 2. The 10-column order in `reattach._COLUMNS` matches SP2/`enrich.export`. `recompute_variant_groups(rows, threshold, max_group_size)` and `enrich.export.write_enriched_csv/enrich_json/write_json` reused with their SP2 signatures. `build_records` change is additive and guarded by `os.path.exists`.

No issues found.

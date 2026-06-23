# Ukrainian Proverbs — SP6: Nomis 1864 Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Матвій Номис, «Українські приказки, прислів'я і таке інше» (1864) as the corpus's 5th source (`Nomis1864`) via OCR + LLM extraction.

**Architecture:** Deterministic OCR (pdftoppm → per-column crop → tesseract) turns the public-domain two-column scan into noisy text; sonnet LLM extraction pulls modernized proverbs out of the 1864 critical apparatus into `data/sources/nomis.csv`; the existing build/dedup/reattach flow merges them (a Nomis match of an existing proverb just adds `Nomis1864` to its sources; net-new are appended); net-new get categorized; then a full re-embed refreshes the Vectorize index and the app is redeployed.

**Tech Stack:** Python (pandas, Pillow, pytest), tesseract 5.5.2 + tessdata_best, poppler (pdftoppm), the existing `core`/`adapters`/`expand`/`enrich`/`embed` modules, Workers AI + Vectorize, wrangler.

**Spec:** `docs/superpowers/specs/2026-06-23-sp6-nomis-ingestion-design.md`

## Global Constraints

- New source key **`Nomis1864`**; registry row: `Nomis1864,Українські приказки, прислів'я і таке інше,1864,Матвій Номис`.
- **`text = modern_text`** for Nomis (modernized reading; no clean verbatim 1864 original). `data/sources/nomis.csv` columns: **`ref,text`** (mirrors `bobkova.csv`; `text` = modernized proverb, `ref` = Nomis entry № or ""). The adapter mirrors `adapters/bobkova.py`.
- OCR: tesseract `--psm 6 -l ukr` (tessdata_best at `expand/work/tessdata_best`), **per-column crop** (page split into left/right with a small overlap) — whole-page OCR interleaves the two columns.
- Dedup is non-destructive: a Nomis proverb whose `normalized_text` equals an existing entry's **adds `Nomis1864` to that entry's `sources`** (no new row, no overwrite); only genuinely new proverbs get new rows. Enrichment (modern_text/category/explanation) is preserved across id renumbering by re-attaching on `normalized_text` (`expand/reattach.py`).
- Best-effort quality (~75–80%); discard uncertain extractions; no second verification pass.
- LLM extraction runs **batched, one pass at a time** (SP2 session-limit lesson); robust JSON parsing (line-salvage for unescaped Ukrainian quotes).
- Re-embed is **full** (ids renumber → id-keyed manifest stale): delete `embed/manifest.json`, recreate the `proverbs-bge-m3` index, embed all (batch ≤ 100 — bge-m3 60k-token cap). Deploy + index refresh are **outward — confirm with the user**.
- Commit identity `MurzikVasilyevich <vasilyevichmurzik@gmail.com>` + session footer. Branch `feat/nomis`. Push: origin via `gh auth switch --user MurzikVasilyevich` (HTTPS); dmytro is SSH.
- **Task types:** `[IMPL]` = TDD implementer. `[CONTROLLER-RUN]` = controller (PDF acquisition, OCR, LLM extraction, enrichment, re-embed, deploy).

---

### Task 1 [IMPL]: Nomis adapter + build inclusion

**Files:**
- Create: `adapters/nomis.py`, `tests/test_nomis_adapter.py`
- Modify: `build.py` (conditional Nomis include), `core/schema.py` (add `Nomis1864` to `SOURCE_PRIORITY`)
- Test: `tests/test_build_nomis.py`, `tests/fixtures/nomis_min.csv`

**Interfaces:**
- Produces: `adapters.nomis.load(path: str) -> list[CanonicalRecord]` — reads `ref,text` CSV → records with `Annotation(source="Nomis1864", ref=…)`, skipping blank text. Mirrors `adapters.bobkova.load`.
- `build.build_records(sources_dir)` additionally loads `nomis.csv` when present.

- [ ] **Step 1: Write the failing adapter test** — `tests/test_nomis_adapter.py`:
```python
from adapters.nomis import load


def test_load_nomis(tmp_path):
    p = tmp_path / "nomis.csv"
    p.write_text("ref,text\n12,Без труда нема плода\n13,\n", encoding="utf-8")
    recs = load(str(p))
    assert len(recs) == 1                     # blank-text row skipped
    assert recs[0].text == "Без труда нема плода"
    assert recs[0].annotations[0].source == "Nomis1864"
    assert recs[0].annotations[0].ref == "12"
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_nomis_adapter.py -v` → FAIL (no module).

- [ ] **Step 3: Implement** — `adapters/nomis.py`:
```python
from __future__ import annotations

import pandas as pd

from core.schema import Annotation, CanonicalRecord

SOURCE = "Nomis1864"


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

- [ ] **Step 4: Run, verify pass** — PASS.

- [ ] **Step 5: Add `Nomis1864` to `core/schema.py` `SOURCE_PRIORITY`** (after `Ilkevich1841`):
```python
SOURCE_PRIORITY: dict[str, int] = {
    "Franko1901": 0,
    "Mlodzynskyi2009": 1,
    "Ilkevich1841": 2,
    "Nomis1864": 3,
}
```

- [ ] **Step 6: Wire Nomis into `build.py`** — in `build_records`, after the bobkova block (`build.py:19-22`), add:
```python
    nomis_path = os.path.join(sources_dir, "nomis.csv")
    if os.path.exists(nomis_path):
        from adapters import nomis
        records += nomis.load(nomis_path)
```

- [ ] **Step 7: Write the failing build test** — `tests/fixtures/nomis_min.csv`:
```csv
ref,text
1,Без труда нема плода
2,Цілком нова приказка від Номиса
```
`tests/test_build_nomis.py`:
```python
import os, csv
from core.schema import CanonicalRecord, Annotation
from core.normalize import normalize
from core.dedup import merge_exact


def test_nomis_dup_adds_source_and_netnew_appended():
    # one existing Franko proverb + a Nomis duplicate of it + a Nomis net-new
    existing = CanonicalRecord(text="Без труда нема плода",
                               annotations=[Annotation(source="Franko1901", ref="100")])
    nomis_dup = CanonicalRecord(text="Без труда нема плода",
                                annotations=[Annotation(source="Nomis1864", ref="1")])
    nomis_new = CanonicalRecord(text="Цілком нова приказка від Номиса",
                                annotations=[Annotation(source="Nomis1864", ref="2")])
    recs = [existing, nomis_dup, nomis_new]
    for r in recs:
        r.normalized_text = normalize(r.text)
    merged = merge_exact(recs)
    by_text = {r.text: r for r in merged}
    assert len(merged) == 2                                         # dup folded
    assert set(by_text["Без труда нема плода"].sources()) == {"Franko1901", "Nomis1864"}
    assert by_text["Цілком нова приказка від Номиса"].sources() == ["Nomis1864"]
```

- [ ] **Step 8: Run, verify pass** — `.venv/bin/python -m pytest tests/test_build_nomis.py -v` → PASS. (`merge_exact` already merges on `normalized_text`; this test pins the Nomis behavior. If it fails because `merge_exact` dedups by a different key, STOP and report — the dedup contract changed.)

- [ ] **Step 9: Commit**
```bash
git add adapters/nomis.py core/schema.py build.py tests/test_nomis_adapter.py tests/test_build_nomis.py tests/fixtures/nomis_min.csv
git commit -m "feat(nomis): adapter + build inclusion + source priority"
```

---

### Task 2 [IMPL]: Nomis OCR module (render + column-crop + tesseract)

**Files:** Create `expand/nomis_ocr.py`, `tests/test_nomis_ocr.py`.

**Interfaces:**
- Produces:
  - `column_boxes(width: int, height: int, overlap: int = 20) -> list[tuple[int,int,int,int]]` — returns two PIL crop boxes `(left, upper, right, lower)` splitting a page into left/right columns at the midpoint with `overlap` px shared at the gutter. Deterministic.
  - `ocr_image(path: str, lang: str = "ukr", psm: int = 6, tessdata: str | None = None) -> str` — run tesseract on an image, return text (I/O; smoke-tested by the controller in Task 3).
  - `ocr_pdf(pdf: str, out_txt_dir: str, dpi: int = 300, tessdata: str = "expand/work/tessdata_best") -> int` — render pages (pdftoppm), crop each into 2 columns, OCR each, write `page-NNNN.txt` (left column text then right), return page count. (I/O orchestrator; run in Task 3.)

- [ ] **Step 1: Write the failing test** — `tests/test_nomis_ocr.py` (tests only the deterministic geometry):
```python
from expand.nomis_ocr import column_boxes


def test_column_boxes_splits_with_overlap():
    boxes = column_boxes(1000, 1400, overlap=20)
    assert boxes == [(0, 0, 520, 1400), (480, 0, 1000, 1400)]


def test_column_boxes_odd_width():
    left, right = column_boxes(1001, 100, overlap=0)
    assert left == (0, 0, 500, 100)
    assert right == (500, 0, 1001, 100)
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_nomis_ocr.py -v` → FAIL (no module).

- [ ] **Step 3: Implement** — `expand/nomis_ocr.py`:
```python
from __future__ import annotations

import os
import subprocess


def column_boxes(width: int, height: int, overlap: int = 20) -> list[tuple[int, int, int, int]]:
    mid = width // 2
    left = (0, 0, mid + overlap, height)
    right = (mid - overlap, 0, width, height)
    return [left, right]


def ocr_image(path: str, lang: str = "ukr", psm: int = 6, tessdata: str | None = None) -> str:
    env = dict(os.environ)
    if tessdata:
        env["TESSDATA_PREFIX"] = os.path.abspath(tessdata)
    out = subprocess.run(
        ["tesseract", path, "stdout", "-l", lang, "--psm", str(psm)],
        capture_output=True, text=True, env=env, check=True,
    )
    return out.stdout


def ocr_pdf(pdf: str, out_txt_dir: str, dpi: int = 300,
            tessdata: str = "expand/work/tessdata_best") -> int:
    from PIL import Image
    os.makedirs(out_txt_dir, exist_ok=True)
    img_dir = os.path.join(out_txt_dir, "_img")
    os.makedirs(img_dir, exist_ok=True)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", pdf, os.path.join(img_dir, "page")], check=True)
    pages = sorted(f for f in os.listdir(img_dir) if f.endswith(".png"))
    for i, name in enumerate(pages, 1):
        im = Image.open(os.path.join(img_dir, name))
        parts = []
        for j, box in enumerate(column_boxes(im.width, im.height)):
            crop_path = os.path.join(img_dir, f"col-{i:04d}-{j}.png")
            im.crop(box).save(crop_path)
            parts.append(ocr_image(crop_path, tessdata=tessdata))
        with open(os.path.join(out_txt_dir, f"page-{i:04d}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(parts))
    return len(pages)
```
(Requires Pillow: `expand/work` already holds tessdata_best from SP3b; `Pillow` must be installed — Task 3 Step 0 confirms/install.)

- [ ] **Step 4: Run, verify pass** — PASS (geometry only; `ocr_image`/`ocr_pdf` are exercised on the real scan in Task 3).

- [ ] **Step 5: Commit**
```bash
git add expand/nomis_ocr.py tests/test_nomis_ocr.py
git commit -m "feat(nomis): OCR module — per-column crop + tesseract wiring"
```

---

### Task 3 [CONTROLLER-RUN]: Acquire scan + OCR

Controller-run.

- [ ] **Step 0:** Ensure deps: `.venv/bin/python -c "import PIL"` (else `.venv/bin/pip install Pillow`); confirm `tesseract --version` = 5.5.2 and `expand/work/tessdata_best/ukr.traineddata` exists (from SP3b); `pdftoppm -v`.
- [ ] **Step 1: Acquire the scan** — resolve the Nomis 1864 archive.org identifier (search `archive.org` for «Українські приказки прислів'я Номис 1864»; the SP3c pilot used it). Download the PDF → `data/sources/nomis.pdf`. Verify it's ~330pp (`pdfinfo`). Commit the vendored PDF.
- [ ] **Step 2: OCR** — `.venv/bin/python -c "from expand.nomis_ocr import ocr_pdf; print(ocr_pdf('data/sources/nomis.pdf','expand/work/nomis_txt'))"`. Confirm `page-0001.txt …` written; **spot-check** 2–3 pages that columns are cleanly separated (not interleaved) and the OCR is recognizable 1864-orthography text. If a page's columns are mis-split (text clipped at the gutter), adjust `overlap` or the split point in `nomis_ocr.column_boxes` (re-run Task 2 test) and re-OCR.
- [ ] **Step 3:** `expand/work/` is gitignored — do NOT commit the OCR text or page images. Record the page count + a quality note for Task 4.

---

### Task 4 [CONTROLLER-RUN]: LLM extraction → `data/sources/nomis.csv`

Controller-run. Data artifact (non-deterministic) — mirrors the SP2 batched-Workflow pattern.

- [ ] **Step 1: Extraction prompt** (per page of OCR text). System/task:
  > You are extracting genuine Ukrainian proverbs/приказки from OCR'd text of Номис (1864), a two-column critical edition in 1864 orthography. The text contains proverbs mixed with apparatus: entry numbers, variant readings, source sigla (e.g. «Бер.», «Гад.»), and editorial prose. Return a JSON array; each item `{"text": <proverb modernized to standard Ukrainian spelling>, "ref": <Nomis entry number if present else "">}`. Include ONLY actual proverbs/sayings. Discard headers, page numbers, sigla, variant-reading apparatus, commentary, and OCR garbage. If a line is too garbled to recover confidently, omit it. Modernize spelling (ѣ→і/е, drop ъ, і→и where appropriate) but keep the proverb's wording.
- [ ] **Step 2: Run extraction** — batch the `page-*.txt` files (e.g. ~10 pages/agent) through **sonnet** via the `enrich/batch.py` file-I/O + Workflow pattern. **One pass at a time**, in batches, to avoid the session usage limit. Parse outputs with line-salvage for unescaped quotes (reuse the SP2 parser). Drop items with empty/way-too-short `text`.
- [ ] **Step 3: Aggregate** → `data/sources/nomis.csv` with header `ref,text` (one row per extracted proverb; `text` = modernized). De-duplicate exact repeats within Nomis. Record the count.
- [ ] **Step 4: Spot-audit (n≈40)** — sample extracted rows; confirm ~75–80% are clean, correctly-modernized proverbs (not apparatus). Note the rate in `expand/REPORT.md`. If markedly worse (<60%), tighten the prompt and re-run the worst batches before proceeding.
- [ ] **Step 5: Commit** `data/sources/nomis.csv`:
```bash
git add data/sources/nomis.csv
git commit -m "feat(nomis): LLM-extracted modernized proverbs from the 1864 scan"
```

---

### Task 5 [CONTROLLER-RUN]: Merge + enrich net-new → corpus

Controller-run. Reuses the SP3a/b expansion flow (`build_records` → `reattach` → categorize net-new).

- [ ] **Step 1: Rebuild bare corpus with Nomis included** — with `data/sources/nomis.csv` present, run `build_records` to a temp bare CSV (Nomis now merges in; ids renumber). Read the **prior enriched** `corpus.csv` as `enriched_rows` and the freshly-built bare rows as `base_rows`.
- [ ] **Step 2: Re-attach enrichment** — `expand.reattach.reattach(base_rows, enriched_rows) -> (attached, new_ids)`. `attached` carries modern_text/category/explanation for all proverbs that existed before (matched on `normalized_text`); `new_ids` = the Nomis net-new (and any re-segmented) entries needing categorization. For Nomis net-new, `reattach` defaults `modern_text = text` (correct — Nomis text is already modernized) and `category=""`.
- [ ] **Step 3: Categorize net-new** — run the existing `enrich/` batch categorizer (haiku, the fixed 27-theme `enrich/taxonomy.csv`) over the `new_ids` rows only; merge the categories back (drop-invalid-key normalization per SP2). modern_text already set.
- [ ] **Step 4: Write final corpus** — write the enriched `corpus.csv` + `corpus.json`; print `_stats` (expect `per_source` to gain `Nomis1864`, total = 40,444 + net-new). Sanity-check: existing Franko/Bobkova/etc. counts unchanged except entries that gained `Nomis1864` in `sources`.
- [ ] **Step 5: Tests + commit** — `.venv/bin/python -m pytest -q` (all green, incl. Tasks 1–2). Commit `corpus.csv`, `corpus.json`, `sources.csv` (+`Nomis1864` row), and update `README.md` stats + Sources + the best-effort flag, and `expand/REPORT.md`:
```bash
git add corpus.csv corpus.json sources.csv README.md expand/REPORT.md
git commit -m "feat(nomis): merge Nomis into corpus (5th source) + categorize net-new"
```

---

### Task 6 [CONTROLLER-RUN]: Full re-embed + ship

Controller-run. The deploy + index refresh are **outward — confirm with the user**.

- [ ] **Step 1: Regenerate app exports** — `.venv/bin/python app/build_data.py corpus.csv enrich/taxonomy.csv sources.csv app/public/data corpus.xml`. Confirm `proverbs.json` count = new total.
- [ ] **Step 2: Full re-embed** — ids renumbered, so the manifest is stale: delete `embed/manifest.json`; **recreate the index** (`cd app && npx wrangler vectorize delete proverbs-bge-m3` then `npx wrangler vectorize create proverbs-bge-m3 --dimensions=1024 --metric=cosine`); run the embed pipeline over the full corpus (`CLOUDFLARE_ACCOUNT_ID=… python -m embed.run`, batch ≤ 100). Commit the regenerated `embed/manifest.json` + `app/public/data/*` + `corpus.xml`.
- [ ] **Step 3: Preview + smoke** — `cd app && node build.mjs && npx wrangler versions upload`; on the preview URL curl `/api/meta` (new count), `/api/search`, `/api/semantic?q=…`, `/api/similar/:id`. Confirm a known Nomis net-new proverb is searchable.
- [ ] **Step 4: Deploy** (confirm with user) — `npx wrangler deploy`; bump `sw.js` cache (vN+1); smoke production.
- [ ] **Step 5: Finish** — controller merges `feat/nomis` → main and pushes both remotes via finishing-a-development-branch; update the project memory.

---

## Self-Review

**1. Spec coverage:**
- §2 acquire/vendor PDF + registry row → Task 3 Step 1, Task 5 Step 5. ✓
- §3 OCR (render + column-crop + tesseract) → Task 2 (module) + Task 3 (run). ✓
- §4 LLM extraction → modernized `nomis.csv` (`ref,text`, text=modern_text), batched, spot-audit → Task 4. ✓
- §5 merge (adapter + build inclusion + dedup adds-source + variant-link + reattach) → Tasks 1, 5. ✓
- §6 categorize net-new → Task 5 Step 3. ✓
- §7 full re-embed + exports + redeploy → Task 6. ✓
- §9 testing (adapter, build dedup, crop geometry units; OCR/LLM as audited data artifacts) → Tasks 1, 2, 4 Step 4. ✓
- §10 deploy confirm → Task 6 Step 4. ✓

**2. Placeholder scan:** code-bearing tasks (1, 2) carry complete code + tests. Controller tasks carry exact commands; the archive.org id is resolved in Task 3 Step 1 (concrete action, source confirmed obtainable from the SP3c pilot). The extraction prompt is given verbatim. No TBD/"handle errors" steps.

**3. Type consistency:** `adapters.nomis.load(path)->list[CanonicalRecord]` matches `bobkova.load`'s shape and `build_records`' usage (Task 1). `nomis.csv` columns `ref,text` consistent between Task 1 (test/fixture), Task 4 (aggregate), and the adapter. `reattach(base_rows, enriched_rows)->(attached,new_ids)` used in Task 5 matches the real signature in `expand/reattach.py`. `column_boxes`/`ocr_pdf` signatures consistent between Task 2 (def) and Task 3 (run). Source key `Nomis1864` identical across adapter, schema, sources.csv, and stats.

**Spec refinement noted:** spec §4 listed `nomis.csv` as `text, modern_text, source_ref`; since `text = modern_text`, the plan stores `ref,text` (mirrors `bobkova.csv`; the adapter/enrichment set `modern_text = text`) — same data, less redundancy.

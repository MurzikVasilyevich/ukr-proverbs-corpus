# Ukrainian Proverbs Corpus — Expansion, Phase A: Bobkova ingest

**Date:** 2026-06-22
**Status:** Approved (design)
**Sub-project:** 3 of 4, **Phase A** of 3 (3a Bobkova ingest · 3b full-book OCR · 3c archive.org)
**Repo:** `ukr-proverbs-corpus` (existing)
**Depends on:** SP1 (canonical corpus), SP2 (enrichment) — both done.

---

## Roadmap context

The user chose "everything" for Expansion, which decomposes into three phases of very different
shape, built in order:
- **3a — Bobkova ingest** ← *this spec*: integrate the ~800 already-OCR'd Bobkova pages.
- **3b — full-book OCR**: OCR the remaining ~436 pages of Bobkova from the Dropbox PDF (heaviest;
  feasibility assessed at that phase).
- **3c — archive.org sources**: discover and ingest additional public-domain collections.

Phase A establishes the **source-addition pattern** (adapter + enrichment-preservation) that 3b/3c reuse.

## 1. Scope

Ingest the 64 already-OCR'd Bobkova page CSVs (~800 modern-Ukrainian proverbs) into the corpus:
fetch → consolidate → LLM OCR-cleanup → `bobkova` adapter → SP1 pipeline (exact-merge + variant-link
against the existing 35,165) → enriched export, **preserving all existing SP2 enrichment** and
enriching only net-new entries.

**Out of scope:** full-book OCR (3b), archive.org (3c), re-running enrichment over existing entries.

## 2. Source

**Bobkova** — *Українські народні прислів'я та приказки*, compiled by В.І. Бобкова та ін. (modern
Ukrainian orthography). Source PDF on Dropbox (pp. 19–516; only pp. covered by the 64 OCR'd CSVs are
in scope here). Citation key **`Bobkova`**; `Title`/`Year`/`Author` filled into `sources.csv` from the
source during implementation (year confirmed against the edition; left as a single explicit value, not
a placeholder).

## 3. Acquisition + OCR cleanup

- **Fetch:** pull the 64 `data/bobkova_1/pages_OCR/*.csv` from
  `MurzikVasilyevich/Ukraininan-proverbs-and-adages-WIP` (via raw GitHub) into a working dir.
- **Consolidate:** each page CSV has rows `index,text`; flatten across all 64 pages into a raw
  `(page, text)` list (~800 rows), preserving page provenance. Page number derived from the CSV
  filename (`005.csv` → page ref `p005` style, distinct from corpus ids).
- **OCR cleanup (controller, Workflow):** a small batched pass (~8 agents, SP2 file-based mechanism
  with the learned safeguards — one pass at a time, id-level repair for gaps, line-salvage for
  unescaped-quote JSON). Each agent fixes residual OCR errors (stray capital `Й` mid-word,
  mis-recognized characters, broken splits) **without changing meaning**, returning cleaned text per
  row. Output committed as **`data/sources/bobkova.csv`** (`ref,text`) — the cleaned source-of-truth
  for this source. (LLM output → committed data artifact, per the SP2 determinism note.)

## 4. Integration — preserving SP2 enrichment (crux)

Canonical `pNNNNNN` ids are assigned by sorted `normalized_text` over **all** entries, so adding
~800 rows renumbers them. SP2 enrichment (`category`, `modern_text`, cleaned `explanation`) is
id-keyed and would be orphaned. Resolution: **re-attach enrichment by `normalized_text`.**

1. Rebuild the base corpus *including* bobkova → new ids, `normalized_text`, recomputed `variant_group`
   (threshold 85, dissolve groups > 8, as SP2).
2. Build a `normalized_text → enrichment` map from the **existing enriched `corpus.csv`**
   (`category`, `modern_text`, cleaned `explanation`). For each new base entry:
   - **match** on `normalized_text` → reuse that enrichment (existing 35K preserved; bobkova rows that
     exact-merge into an existing proverb inherit it and just add `Bobkova` to `sources`).
   - **no match** (net-new bobkova proverb) → flag for enrichment.
3. **Enrich net-new entries** (controller, small Workflow): categorize against the fixed 27-theme
   taxonomy (`enrich/taxonomy.csv`); since Bobkova is already modern, `modern_text` = the cleaned
   `text` (no modernization pass needed); `explanation` empty (Bobkova has none).
4. Export the expanded enriched corpus (`corpus.csv` 10-col + `corpus.json`).

Losslessness/coverage assertions as in SP1/SP2: every entry has a `normalized_text` match **or** a
fresh enrichment; 100% id coverage; no record dropped.

## 5. Components / files

```
expand/
  __init__.py
  consolidate.py      # 64 page CSVs -> [(ref, text)]                         [TDD]
  reattach.py         # base rows + old enriched corpus -> (attached rows,
                      #   new_refs needing enrichment), keyed by normalized_text [TDD]
  cleanup.js          # Workflow: OCR-clean raw bobkova -> cleaned rows (controller)
  REPORT.md           # generated: added / merged-into-existing / net-new / enriched
adapters/bobkova.py   # data/sources/bobkova.csv -> list[CanonicalRecord]       [TDD]
build.py              # add bobkova.load(...) to build_records()                [IMPL]
data/sources/bobkova.csv   # committed cleaned artifact (ref,text)
sources.csv           # + Bobkova row
corpus.csv / corpus.json   # re-exported, expanded, enrichment preserved
```

Pure-Python pieces (`consolidate`, `reattach`, `adapters/bobkova`) are TDD'd; the LLM cleanup and
net-new enrichment are controller-run Workflows validated by coverage + a small audit.

`adapters/bobkova.load(path)` → records with `text` (cleaned), `keyword=""`,
`annotations=[Annotation(source="Bobkova", ref=page_ref)]`, `normalized_text` blank (build fills it).

## 6. Testing

- `consolidate.py` — fixture page CSVs → flattened `(ref, text)` rows in order; skips empty text.
- `adapters/bobkova.py` — maps cleaned rows to `CanonicalRecord`s with correct source attribution.
- `reattach.py` — entries whose `normalized_text` matches the old enriched corpus reuse its
  `category`/`modern_text`/`explanation`; unmatched entries are flagged as net-new; nothing dropped.
- Integration: small fixture (existing enriched corpus + a few bobkova rows, some matching, some new)
  → expected attached output + correct net-new set.
- LLM passes: coverage + schema checks (categories ∈ taxonomy) + a small manual audit, recorded in
  `expand/REPORT.md`.

## 7. Tech stack

Python 3 (pandas, rapidfuzz, pytest) reusing SP1/SP2 modules (`core/`, `enrich/schema`, `enrich/`);
Workflow tool for the LLM cleanup + net-new enrichment. Consistent with prior phases.

## 8. Expected output

Corpus grows from 35,165 by the count of net-new Bobkova proverbs (those not exact-merging into
existing entries); modern Bobkova variants variant-link to Franko's 1901 dialectal forms. All existing
SP2 enrichment preserved; net-new entries categorized (`modern_text` = text). `expand/REPORT.md` reports
added / merged / net-new / enriched counts and the cleanup/enrichment audit.

## 9. Open items / risks

- **Bobkova bibliographic year/author** confirmed during implementation (single explicit value in
  `sources.csv`).
- **OCR-cleanup non-determinism**: cleaned `data/sources/bobkova.csv` is a committed artifact, not a
  reproducible build (as SP2).
- **`modern_text` = text for Bobkova** assumes Bobkova is already standard modern Ukrainian; spot-check
  in the audit. If notable archaic forms appear, fall back to a modern-spelling pass for those.
- Re-attach matches on exact `normalized_text`; near-variant Bobkova proverbs are linked (variant_group)
  but enriched as net-new — acceptable (matches SP1/SP2 conservative dedup).

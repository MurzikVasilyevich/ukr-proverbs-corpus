# Ukrainian Proverbs Corpus — Expansion, Phase B: full Bobkova via pdftotext

**Date:** 2026-06-23
**Status:** Approved (design)
**Sub-project:** 3 of 4, **Phase B** of 3 (3a Bobkova ingest done · 3b full-book · 3c archive.org)
**Repo:** `ukr-proverbs-corpus` (existing)
**Depends on:** SP1 (corpus), SP2 (enrichment), SP3a (Bobkova ingest + the source-addition pattern) — all done.

---

## 1. Feasibility outcome (assessed before this spec)

The Bobkova source PDF (Dropbox, 525 pages, content pp.19–516) **has an embedded text layer** — `pdftotext`
extracts it directly. **No image OCR is required** (tesseract-ukr was installed for SP3c, not used here).
`pdftotext` on pp.19–516 yields **~4,630 raw proverb chunks** (vs SP3a's 760), but the text layer is
**messy**: justification inserted intra-word spaces in ~44% of chunks (e.g. «тяж кої»→«тяжкої»,
«До ж о в тн ев і»→«Дожовтневі»), with mixed separators (`* « » $`), embedded page numbers, and section
headers. So extraction is cheap but a real **segment + clean** pass is required.

## 2. Scope

Extract the full Bobkova book via `pdftotext`, LLM-segment+clean into proverbs, **replace**
`data/sources/bobkova.csv` with the full book (superseding SP3a's partial 760), and re-ingest via the
SP3a source-addition pattern — preserving all existing SP2 enrichment and categorizing only net-new.

**Out of scope:** archive.org sources (3c); image OCR; the front/back matter outside pp.19–516.

## 3. Acquisition + extraction

- **PDF:** download from the Dropbox URL in the WIP `sources.csv`; vendor as `data/sources/bobkova.pdf`
  (5.4 MB, committed for provenance — consistent with the committed `franko.csv`).
- **Extract:** `pdftotext -f 19 -l 516` **per page** → one raw text blob per page (page ref = PDF page
  number). Per-page granularity lets the cleaner attribute `ref` and bound each agent's work.

## 4. Segment + clean (controller Workflow)

Batch the per-page texts (~10 pages/agent → ~50 agents, one pass at a time per the SP2 lesson). Each
agent reads its pages' raw text and returns, for each page, a clean list of proverbs:
- split on separators (`* « » $`) and proverb boundaries;
- **rejoin intra-word spaces** (the 44% artifact) into correct Ukrainian words, preserving meaning;
- **drop** section headers, the book title, and embedded page numbers;
- leave the text otherwise verbatim (Bobkova is already modern — no modernization).

Output (per `{page, text}`) consolidated → the new full `data/sources/bobkova.csv` (`ref,text`),
**replacing** the SP3a file. File-based handoff with the SP2/SP3a safeguards: coverage check
(every page accounted for), id-level repair for gaps, line-salvage for unescaped-quote JSON.

## 5. Re-ingest (controller — reuses SP3a code unchanged)

Identical to SP3a Task 6, with the larger `bobkova.csv`:
1. `build(sources_dir, out_dir="/tmp/...")` — `build.py`'s existing bobkova hook + `adapters/bobkova.py`
   produce the expanded base (new ids, recomputed variant groups).
2. `expand/reattach.reattach(base, current_enriched_corpus)` — re-attach SP2 enrichment by
   `normalized_text`; existing entries preserved; net-new flagged.
3. Categorize net-new (~3,800) via a Workflow (27-theme taxonomy, drop-invalid normalization);
   `modern_text` = cleaned `text`; `explanation` empty.
4. `recompute_variant_groups(rows, 85, 8)`; export via `enrich.export`.
5. `sources.csv` Bobkova row already present (SP3a) — unchanged.

## 6. Components / files

```
expand/
  consolidate_pages.py   # per-page LLM-clean outputs -> [(ref,text)] for bobkova.csv   [TDD, new]
  reattach.py            # reused unchanged from SP3a
adapters/bobkova.py      # unchanged (reads data/sources/bobkova.csv)
build.py                 # unchanged (bobkova hook from SP3a)
data/sources/bobkova.pdf # vendored source (committed)
data/sources/bobkova.csv # REPLACED with full book (~4,000+ rows)
corpus.csv / corpus.json # re-exported, expanded
expand/REPORT.md         # updated: full-book counts
```

Almost all logic is reused from SP3a; the only new committed code is `consolidate_pages.py`
(merging per-page cleaned outputs into `bobkova.csv`, with coverage assertion), which is TDD'd.
Extraction and the two LLM passes are controller-run.

## 7. Testing

- `consolidate_pages.py` — fixtures: per-page cleaned JSON → flattened `(ref,text)` rows, in page order,
  empties dropped, coverage assertion fires when a page is missing.
- Re-ingest correctness inherits SP3a's tested `reattach`/`adapter`/`build` (full suite stays green).
- LLM passes validated by coverage + a small manual audit (segment+clean accuracy, esp. the spacing fix),
  recorded in `expand/REPORT.md`.

## 8. Tech stack

`pdftotext` (poppler) for extraction; Python 3 (pandas, rapidfuzz, pytest) reusing `core/`, `enrich/`,
`expand/`; Workflow tool for segment+clean and net-new categorize. Text-only LLM (no vision/OCR).

## 9. Expected output

Bobkova grows from 760 to ~4,000+ cleaned proverbs; corpus grows from 35,865 by the net-new count
(~3,000–3,800 after dedup/variant-link against existing). Existing SP2 enrichment preserved; net-new
categorized. More Bobkova↔Franko variant links. Honest counts + audit in `expand/REPORT.md`.

## 10. Open items / risks

- **Segment+clean quality** is the main risk (44% spacing artifacts + imperfect proverb boundaries).
  Mitigation: per-page LLM segmentation, coverage checks, sample audit. Residual errors documented as
  best-effort (LLM-cleaned data artifacts, like SP2/SP3a).
- **Replace vs SP3a 760:** the full re-extraction supersedes SP3a's 760 (same source, re-cleaned
  consistently). Overlapping proverbs dedup/variant-link normally.
- **Cost/scale:** ~50 + ~38 text agents, run one pass at a time (no session-limit issue at this scale,
  but watched).
- Non-determinism: cleaned `bobkova.csv` and enriched fields are committed data artifacts.

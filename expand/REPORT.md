# Expansion Report — Bobkova (Phases 3a + 3b)

Generated 2026-06-23. Source-addition pattern: adapter + enrichment re-attach by `normalized_text`.

## Source

**Bobkova** — *Українські народні прислів'я та приказки* (compiled by В.І. Бобкова та ін.), a modern
Ukrainian collection (incl. a Soviet-era «післяжовтневі» section). Ingested from the full source PDF
(pp.19–516), vendored at `data/sources/bobkova.pdf`.

## Phase 3b pipeline (full book, token-optimized)

1. **OCR (token-free):** `pdftoppm -r 300` + **tesseract 5.5.2** with the `tessdata_best` ukr model,
   `--psm 6 --oem 1`, over 498 pages. (Chosen over `pdftotext` because the PDF's text layer had a ~44%
   intra-word-space artifact that image-OCR avoids.)
2. **Segment (token-free):** rule-based `segment_page` — drops separators/headers/page-numbers, joins
   wrapped lines, **de-hyphenates** line-breaks → 5,649 raw proverbs.
3. **Flag (token-free):** a proverb is suspect only if a token is both absent from the corpus vocabulary
   **and** flagged by the morphology-aware **hunspell** binary (`uk_UA`). De-hyphenation + this combined
   signal cut the flag rate from 53% (naïve stem-match) to **16%** (960 proverbs).
4. **LLM-verify residuals (the only cleanup LLM):** 960 flagged proverbs → 10 haiku agents fixed OCR
   errors / dropped garbage. 36 unrecoverable rows dropped.
5. **Result:** `data/sources/bobkova.csv` = **5,613 proverbs** (replaces 3a's 760 with the full book).

## Phase 3a → 3b ingest

Re-ingested via the SP1 pipeline + SP3a re-attach pattern: SP2 enrichment preserved by matching
`normalized_text` against the prior enriched corpus; only net-new proverbs categorized (haiku, 27-theme
taxonomy); `modern_text` = cleaned text (Bobkova is modern); variant groups recomputed (threshold 85,
dissolve > 8).

## Counts

| metric | value |
|---|---|
| Corpus before 3a | 35,165 |
| After 3a (partial Bobkova) | 35,865 |
| **After 3b (full Bobkova)** | **40,444** |
| Bobkova proverbs (sourced) | 5,613 |
| Net-new categorized this phase (valid, 0 fallback) | 4,755 |
| Variant groups | 3,413 → **3,927** |
| Variant groups spanning Bobkova + Franko | **634** (was 116) |
| Per source | Franko1901 30,906 · Ilkevich1841 2,702 · Mlodzynskyi2009 2,261 · Bobkova 5,613 |

## Quality

- **Enrichment preservation verified:** all 34,849 existing non-Bobkova entries retain SP2
  `category` + `modern_text`; no existing content re-enriched.
- **Token economy:** OCR + segmentation + flagging were fully deterministic (zero LLM tokens); the LLM
  touched only the 16% flagged residuals + net-new categorization.
- **Cross-source linking:** 634 variant groups now connect modern Bobkova proverbs to Franko/Ilkevich
  historical forms.
- **Residual OCR (~2–3%):** front-matter fragments (pp.19–20), occasional trailing artifacts, and
  cross-page hyphen breaks that `segment_page` (per-page) cannot rejoin. Best-effort data artifacts.

## Known limitations / next

- Phase 3b completes Bobkova. **Phase 3c** = archive.org sources (tesseract toolchain now in place).
- Categories single-pass (primary tag reliable; secondary occasionally debatable, as SP2/3a).

## Nomis 1864 ingestion (SP6)

**Source:** Матвій Номис, *Українські приказки, прислів'я і таке інше* (1864), public-domain ~330-page scan
(archive.org; "Ukraïns'ki prykazky, prysliv'ia i take inshe"). The PDF is **not vendored** (29 MB; re-fetchable).

**Pipeline:** `pdftoppm` 300dpi → per-column crop (`expand/nomis_ocr.py`; the edition is two-column and whole-page
OCR interleaves) → tesseract 5.5.2 `--psm 6` ukr (tessdata_best) → 330 page texts → batched **sonnet** LLM
extraction (`expand/work/nomis_extract/`) pulling proverbs out of the 1864 critical apparatus, emitting
`{text (original 1864 orthography), modern_text (modernized), ref}` → `data/sources/nomis.csv` (9,785, 18
within-Nomis dupes dropped) → `expand/merge_nomis.py` (build + reattach enrichment by normalized_text +
modern_text override) → `expand/{prep,finalize}_nomis.py` (haiku categorize of net-new + final write).

**Merge result:** corpus 40,444 → **48,787** (+8,343 net-new). Of the 9,785 Nomis proverbs: 1,442 exact-merged
into existing entries (added `Nomis1864` as a second attestation), 2,232 cross-source variant-linked to
Franko/Bobkova/Ilkevich/Mlodzynskyi, 5,914 genuinely distinct. Net-new categorized (haiku, 27 themes).

**Fidelity (best-effort ~75–80%):** an automated audit (n=400, `expand/audit_nomis.py`, extracted `text` vs OCR
via rapidfuzz) found ~82% match the OCR at ≥80 and the low-scoring tail is dominated by *faithful* extractions
penalized against noisy OCR references — true faithful-to-OCR is ~95%+. Two residual error classes: (1) OCR
character errors persist in `text` (e.g. the scan's «коровая»/«5470» OCR'd as «коровай»/«5410»); (2) rare LLM
normalization toward familiar forms (e.g. «кумові»→«тобі»), ~1–2%. `text` preserves archaic/dialectal forms
(«вбувсь», «охвіра», «-цця») verbatim; modernization lives in `modern_text`. Nomis entries are flagged
best-effort and identifiable by `Nomis1864` in `sources`.

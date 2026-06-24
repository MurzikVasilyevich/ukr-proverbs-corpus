# verba — SP11: Text cleanup + plain-canonical / pretty-display typography → v1.0.1

**Date:** 2026-06-24
**Status:** Approved (design)
**Sub-project:** 11 — scrub OCR leading-junk + mixed-script homoglyphs; canonicalize all corpus text to **plain ASCII punctuation** (code-friendly); render **Ukrainian typography at display** (« » / „ " quotes, «—» тире, ’ apostrophe, … ellipsis) via a shared `prettify()`. Ship as corpus **v1.0.1**.
**Repo:** `verbacorpus`; build pipeline (Python) + `app/` (TS Worker/PWA/cards).
**Depends on:** corpus v1.0.0 + the build pipeline (`build.py`; `expand/reattach.py` attaches enrichment by `normalized_text`; `core/normalize.py`; `embed/run.py` incremental embeddings; SP10 versioning/release; SP8 cards; SP9 PWA).

---

## 1. Problem & scope

Two distinct issues surfaced from `p000001` = `' По парі пізнати…`:

**(a) Letter-level OCR defects (~210 entries):** 686/48,787 don't start with an uppercase Ukrainian letter; of those, ~210 are genuine defects (the rest are legitimate quotes/archaic letters). Breakdown:

| class | count | action |
|---|---|---|
| leading `\|` | 22 | strip |
| stray leading `.` `:` `,` `!` `/` `'` `(`, list-numbers (`(1`,`1 `,`1.`), digit | ~46 | strip + recapitalize |
| Latin/Greek homoglyphs (`Τοτο`→`Тото`, leading `P`/`H`/`C`…) | ~70 | repair word-wide (curated) |
| lowercase start | 74 | judge (case error vs fragment) |
| leading `-`/`—` | 30 | judge (dialogue vs junk) |
| `Ѣ` archaic-yat words | 9 | **preserve** (real orthography) |

**(b) Inconsistent punctuation typography (corpus-wide):** mixed quote glyphs (« 1345, " 84, „ 101, " 61, " 40), mixed dashes (hyphen 6983 mostly word-internal, en-dash 1456, em-dash 428), mixed apostrophes (' U+0027 725, ' U+2019 377), `...` vs `…`. Dialogue proverbs (~455) use en-dash «–» between turns where Ukrainian wants em-dash «—».

**Root cause of (a):** the pipeline's `isPresentable` only kept fragments out of the *display* face; it never scrubbed `text`. Fidelity ("preserve archaic orthography") was over-applied to OCR punctuation, which isn't orthography.

**In scope:** the ~210 letter-level fixes; **corpus-wide** punctuation canonicalization (all `text` + `modern_text`); a display-layer `prettify()`. **Out of scope:** the 9 `Ѣ` entries; a full corpus-wide mixed-script audit beyond the flagged entries; converting inline dialogue into multi-line «—»-prefixed direct speech (keep the one-line proverb form); schema changes.

## 2. Architecture — plain canonical data, pretty display

Three mechanisms, cleanly separated by what they touch and where they run.

### (A) Letter-level corpus fixes (~210 entries, Python) — *changes letters → changes `normalized_text`*
- **`clean_text(text)`** (`core/clean.py`, deterministic, unit-tested): strip the unambiguous leading garbage (`|`, stray punctuation, list-number patterns `^\(?\d+[.)]?\s+`) and recapitalize the new first letter. Never strip a balanced leading quote; never alter letters/`Ѣ`. Idempotent.
- **`corrections.csv`** (root: `id, text, modern_text, reason`): curated overrides for cases a rule can't safely decide — Latin/Greek homoglyph repair (word-wide), lowercase→uppercase judgment, dash judgment. LLM-proposed over only the flagged entries, then spot-reviewed.
- **Applied by `id`, AFTER enrichment is attached** (`expand/apply_corrections.py`): set corrected `text`, recompute `normalized_text`, set `modern_text` if provided. Because enrichment attaches by `normalized_text` (`reattach.py`), doing this post-attach by id means `modern_text`/`category` are **never dropped**. A dup-check flags/merges any new exact-duplicate (logged, not silent).

### (B) Canonical punctuation → plain ASCII (corpus-wide, Python) — *`normalized_text`-invariant → safe*
**`to_plain(text)`** (`core/clean.py`, deterministic, unit-tested) maps every entry's `text` and `modern_text` to a code-friendly canonical form:
- Quotes `« » „ " " " ‹ ›` → straight `"`.
- Apostrophes `’ ʼ \` ´ ‘` → ASCII `'` (U+0027).
- Dashes: an em/en-dash, or a **space-padded** hyphen, acting as тире → a **space-padded ASCII hyphen** ` - ` (this preserves the тире-vs-дефіс distinction via spacing); a **word-internal** hyphen (`будь-що`, no surrounding spaces) is left as `-`.
- Ellipsis `…` and `. . .` → `...`.
- Collapse repeated spaces; normalize spacing around ` - `; trim.
Because `core/normalize.py` already lowercases, strips all non-word/non-apostrophe punctuation, and folds apostrophes to `'`, **`normalized_text` is unchanged by `to_plain`** — so dedup, variant grouping, and enrichment re-attach are undisturbed. `to_plain` runs in the build/export on every record (so future sources are canonicalized too).

### (C) Display typography → Ukrainian (TS, render-time) — *no data change*
**`prettify(text)`** (NEW pure fn in `app/src/shared/text.ts`, unit-tested) renders the plain canonical text as Ukrainian typography, applied ONLY at display:
- `"…"` → `«…»` (balanced: alternate open/close across the string).
- space-padded ` - ` → ` — ` (em-dash тире).
- `'` → `’` (U+2019).
- `...` → `…`.
Used by **the PWA** (`main.ts`: list/hero/detail/swipe render), **the `/p/:id` page** (`buildProverbPage` in `meta.ts`), and **the card renderer** (`cardModel`/`card.ts`). Round-trip is lossless for the common cases: `«А?» — «Б»` →`to_plain`→ `"А?" - "Б"` →`prettify`→ `«А?» — «Б»`; `нап'є` ↔ `нап'є`; `будь-що` stays `будь-що` (unspaced, not тире).

## 3. Producing the curated corrections (mechanism A)

- `expand/scan_leading.py` (NEW) reports the flagged entries by class (also the verification scanner).
- An LLM pass (batched, like the original enrichment) reads the judgment/homoglyph entries and proposes corrected `text` (+ `modern_text` if it changes): repair OCR confusables to Cyrillic, fix obvious case/leading errors, **preserve the archaic words/orthography**, and when unsure **omit the row**. Output → `corrections.csv`.
- A reviewer spot-checks a sample for over-correction (no archaic form modernized, no meaning changed).

## 4. Ship as v1.0.1

- Rebuild (`build.py` + `to_plain` + reattach + `apply_corrections`) → canonical plain-ASCII `corpus.csv`/`corpus.json`; rebuild `app/public/data/*`.
- **Re-embed** only entries whose **`normalized_text` changed** — i.e. the ~210 letter-level fixes (punctuation-only canonicalization doesn't change `normalized_text` or the embedded meaning, so it is excluded from re-embedding). `embed/run.py` is incremental.
- Bump **VERSION → 1.0.1**, add a `## [1.0.1]` CHANGELOG entry (counts + what changed: leading-junk, homoglyphs, ASCII canonicalization, display typography), bump `CITATION.cff` + `croissant.json` version.
- Deploy the Worker (display now prettifies); cut the **v1.0.1** GitHub Release via `scripts/release.sh --publish`.

## 5. Components / files

- `core/clean.py` (NEW) — `clean_text()` (leading-junk + recapitalize) + `to_plain()` (ASCII canonicalization). [pytest]
- `expand/scan_leading.py` (NEW) — flag/report + verification scanner.
- `corrections.csv` (NEW, root) — curated id→correction overrides.
- `expand/apply_corrections.py` (NEW) — apply `clean_text` + `corrections.csv` by id post-attach, recompute `normalized_text`, dup-check. [pytest]
- `build.py` / enrichment build path (MODIFY) — wire `to_plain` (all records) + `clean_text`/`apply_corrections`; regenerate corpus.csv/json + `app/public/data`.
- `app/src/shared/text.ts` (NEW) — `prettify()`. [vitest]
- `app/src/client/main.ts`, `app/src/shared/meta.ts` (`buildProverbPage`, `cardModel`), `app/src/card.ts` (MODIFY) — render via `prettify()`.
- `VERSION`, `CHANGELOG.md`, `CITATION.cff`, `croissant.json` (MODIFY) → 1.0.1.

## 6. Testing

- **pytest** `clean_text`: strips leading `|`/stray punct/list-numbers + recapitalizes; leaves balanced quotes / `Ѣ…` / clean-uppercase unchanged; idempotent.
- **pytest** `to_plain`: `«А» — «Б»`→`"А" - "Б"`; `„цит"`→`"цит"`; `нап'є`(U+2019)→`нап'є`(U+0027); `будь-що` unchanged; `…`→`...`; idempotent; **assert `normalize(to_plain(t)) == normalize(t)`** for a sample (the invariant that protects enrichment).
- **pytest** `apply_corrections`: applies by id, recomputes `normalized_text`, **preserves the row's `category`/`explanation`** (enrichment-loss guard); a row with `modern_text` updates it.
- **vitest** `prettify`: `"А?" - "Б"`→`«А?» — «Б»`; `нап'є`(U+0027)→`нап'є`(U+2019); `...`→`…`; `будь-що` unchanged (unspaced hyphen); idempotent; **round-trip** `prettify(to_plain_fixture) === expected_ukr` on shared fixtures.
- **Post-build assertions:** rebuilt `corpus.csv` `text`/`modern_text` contain **no** `« » „ " " ’ – — …` (only ASCII `" ' - ...`); re-run `scan_leading.py` → only `"`-opening dialogue + `Ѣ` remain as non-uppercase starts; **zero** entries lost `category`/`modern_text`; total count unchanged (or reduced only by logged merges).
- **Manual (preview):** `/p/p000001` reads `По парі пізнати…`; a dialogue `/p/:id` + its card show `«…» — «…»` with `’`; the export (`/api/v1/export`, release CSV) shows plain ASCII `" ' -`.

## 7. Risks / open items

- **Enrichment loss:** only mechanism (A) changes `normalized_text`; applied by id post-attach with a test asserting no enrichment dropped. Mechanism (B) is `normalized_text`-invariant (tested) → inherently safe.
- **Lossy ASCII round-trip for nested quotes:** flattening `«…„…"…»` to all-`"` loses the nesting level; `prettify` then renders all as `« »`. Rare in proverbs; the curated pass can special-case any that matter. Documented, not silent.
- **`prettify` quote balancing on odd quote counts:** if an entry has an unbalanced `"`, alternate-open/close degrades gracefully (last quote may render as `«`); the canonicalization + curated pass aim to leave balanced counts.
- **Over-correction (fidelity):** LLM pass preserves archaic words and omits uncertain rows; review sample gates it. `clean_text`/`to_plain` touch only punctuation/leading-junk, never letters.
- **Re-embed scope:** only `normalized_text`-changed entries (~210) re-embed; verify the manifest excludes punctuation-only changes (else a needless full re-embed).
- **Display perf:** `prettify` is a cheap regex pass per rendered proverb; the PWA prettifies only the visible page (load-more/swipe render incrementally), the Worker prettifies per `/p`/card request (cached).

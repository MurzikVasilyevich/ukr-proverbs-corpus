# Ukrainian Proverbs Corpus — Enrichment

**Date:** 2026-06-22
**Status:** Approved (design)
**Sub-project:** 2 of 4 (see Roadmap in the SP1 spec)
**Repo:** `ukr-proverbs-corpus` (existing)
**Depends on:** Sub-project 1 (canonical corpus — 35,165 entries, built & published)

---

## 1. Scope

Layer four enrichments onto the canonical corpus, producing an enriched `corpus.csv` / `corpus.json`:

1. **Thematic categorization** — multi-label (1–3 themes), from a fixed 27-theme taxonomy (§3).
2. **Modern-spelling normalization** — new `modern_text` field: 1901 Galician / pre-reform orthography → modern standard Ukrainian. (Hardest, highest-risk dimension.)
3. **Explanation cleanup** — de-noise Franko's explanation text (OCR artifacts, stray whitespace, broken hyphenation).
4. **Variant-threshold tuning** — measure precision of the existing `variant_group`s and tune/cap the over-linking flagged in SP1.

**Out of scope:** new sources (SP3 expansion), API/PWA/bot (SP4 productization), translation, audio.

## 2. Engine and the determinism consequence

The enrichment engine is **Claude Code agents driven by the Workflow tool** — batched fan-out over the 35,165 entries. No external API key required.

**Critical difference from SP1:** LLM enrichment is **not byte-deterministic**. Re-running produces semantically-equivalent but not identical output. Therefore:
- The enriched **fields** (`category`, `modern_text`, cleaned `explanation`, tuned `variant_group`) are committed as **data artifacts** — they are the source of truth for enrichment, produced by a one-time, validated run.
- The SP1 structural pipeline (`build.py`) remains deterministic and unchanged; enrichment is a **separate layer applied after** a deterministic build, not folded into it.
- Regenerating enrichment requires Claude Code (the harness), documented in the README.

## 3. Taxonomy (fixed controlled vocabulary, 27 themes)

Data-derived from a 250-entry representative sample. Saved as `enrich/taxonomy.csv` (`key, ukrainian_label, scope_note`). Each proverb gets **1–3** keys, **first = primary** (the literal vehicle/target of the proverb). `idiom_expressive` is the catch-all for opaque formulae/curses where no thematic reading is defensible.

| key | ukrainian_label | scope note |
|---|---|---|
| work_labor | Праця і ремесло | working, diligence, idleness, crafts, tools, the ethic of effort |
| poverty_wealth | Бідність і багатство | rich vs poor, money, coins, debt, material want |
| food_hunger | Їжа і голод | eating, hunger, bread, specific foods, fasting |
| drink_alcohol | Пиття і п'янство | drinking, drunkenness, tavern life, горілка, пиво |
| family_kinship | Родина і спорідненість | parents, children, siblings, relatives, household as a unit |
| marriage_gender | Шлюб і стать | marriage, husbands/wives, widows, courtship, gender roles |
| speech_lying | Мова і брехня | talking, gossip, lying, silence, slander, words vs deeds |
| wisdom_folly | Розум і дурість | intelligence, foolishness, advice, learning, experience |
| fate_luck | Доля і щастя | luck, fortune, fate, chance, happiness, misfortune |
| time_seasons | Час і пори року | time, haste, delay, seasons, agricultural calendar, saints' days |
| death_illness | Смерть і хвороба | dying, illness, aging, bodily decay, death-curses |
| religion_god | Бог і церква | God, devil, saints, church, sin, prayer, blessing |
| social_relations | Громада і сусідство | neighbors, community, reputation, public shame/honor |
| class_power | Стани і влада | lords/serfs (пан/хлоп), nobility, clergy, officials, hierarchy |
| justice_truth | Правда і кривда | truth, justice, law, honesty, fairness, rights |
| animals | Тварини | animal-vehicle proverbs making a human point |
| body_health | Тіло і здоров'я | bodily states, strength, beauty, physical appearance |
| home_household | Хата і господарство | the house, domestic order, farm property |
| conflict_enmity | Сварка і ворожнеча | quarrels, fighting, revenge, enemies, troublemakers |
| friendship_love | Дружба і любов | friendship, love, loyalty, affection |
| travel_distance | Дорога і мандри | roads, travel, departure, far-off places, wandering |
| trade_money | Торгівля і гроші | buying, selling, markets, bargaining, prices |
| ethnic_local | Народи і місця | named ethnic groups, regions, local figures |
| emotion_mood | Почуття і настрій | anger, grief, fear, joy, envy, shame as states |
| nature_weather | Природа і погода | sky, weather, wind, water, plants, landscape |
| appearance_reputation | Зовнішність і слава | looks vs reality, good vs bad name |
| idiom_expressive | Фразеологія та вигуки | formulaic exclamations, curses, toasts, set phrases |

**Known classification challenges** (drive prompt design): pervasive multi-themability (instruct: pick primary vehicle + target); ~10–12% opaque idioms/curses (allow `idiom_expressive`); heavy dialectal/pre-reform orthography (supply glossed examples so the classifier doesn't dump parseable proverbs into the catch-all).

## 4. Schema changes (additive)

`corpus.csv` columns after enrichment:
`id, text, normalized_text, modern_text, keyword, explanation, category, sources, source_refs, variant_group`

- **`category`** (existing, was blank) → 1–3 taxonomy keys, semicolon-joined, primary first.
- **`modern_text`** (NEW, inserted after `normalized_text`) → modern-spelling rendering. Verbatim `text` is never modified.
- **`explanation`** → cleaned in place. Raw remains recoverable from `data/sources/franko.csv`.
- **`variant_group`** → recomputed with the tuned threshold/cap.
- `corpus.json` mirrors these: top-level `modern_text`, `category` (array, not joined string), and cleaned explanation inside `annotations`.

## 5. Pipeline

A deterministic SP1 `build.py` runs first to produce the base corpus; then enrichment passes apply.

- **Pass A — categorize + clean explanation.** Cheaper model, batch ~150 entries/agent. Input: batch (`id, text, keyword, explanation`) + the taxonomy. Output (schema-validated): per `id` → `{categories: [1–3 keys], explanation_clean: str}`. Validation: every key ∈ taxonomy; every input id present in output.
- **Pass B — modern-spelling.** Stronger model, batch ~100 entries/agent (harder task, smaller batches). Input: batch (`id, text`) + orthography guidance with glossed Galician examples. Output: per `id` → `{modern_text: str}`. Validation: non-empty; every id covered; sanity check that `modern_text` is not wildly longer/shorter than `text`.
- **Merge.** Join Pass A + Pass B back into the corpus by `id`. Assert 100% id coverage and zero dropped/added records (losslessness, as in SP1).
- **Pass C — variant tuning.** Sample variant groups (weighted toward large groups), judge-agents rate intra-group cohesion (are members true variants of one proverb?). Report precision at the current 0.85 threshold; choose a tuned threshold and/or a max-group-size split rule; recompute `variant_group` over the full corpus with the new parameters.
- **Validation pass.** Random sample (~200 entries) audited by judge-agents: category correctness + `modern_text` fidelity, scored. Plus hard schema checks. Results → `enrich/REPORT.md`.

## 6. Architecture / files

```
ukr-proverbs-corpus/
  enrich/
    taxonomy.csv          # fixed 27-theme controlled vocabulary
    workflow.js           # Workflow script: passes A, B, validation (fan-out)
    merge.py              # join pass outputs (JSON) into the corpus by id; assert coverage
    tune_variants.py      # apply tuned threshold/cap, recompute variant_group
    schema.py             # enrichment record schema + validators (categories ∈ taxonomy)
    REPORT.md             # generated: counts, accuracy audit, tuning decision
    out/                  # raw per-batch pass outputs (committed for provenance)
  core/ adapters/ build.py ...   # unchanged from SP1
  corpus.csv corpus.json         # re-exported with enriched columns
  README.md                      # updated: new columns, taxonomy, LLM-generated note
  tests/                         # tests for merge.py, schema validators, tune_variants
```

Pure-Python pieces (`merge.py`, `tune_variants.py`, `schema.py`) are TDD'd with fixtures. The LLM passes (`workflow.js`) are validated by schema checks + the sample audit rather than unit tests (non-deterministic).

## 7. Testing

- `enrich/schema.py` validators — table-driven: reject categories outside taxonomy, reject missing ids, accept valid records.
- `merge.py` — fixtures: correct join by id, coverage assertion fires on a missing id, no record added/dropped, columns written in spec order.
- `tune_variants.py` — fixtures: threshold/cap applied correctly, group ids re-assigned deterministically.
- Integration: a small end-to-end on a fixture corpus (mock pass outputs) → enriched corpus matches expected.
- Quality gate (not a unit test): the §5 validation pass; recorded in `enrich/REPORT.md`.

## 8. Tech stack

Python 3 (pandas, pytest) for merge/tune/schema; the Workflow tool for the LLM passes (model per pass: cheaper for Pass A, stronger for Pass B). Consistent with SP1.

## 9. Expected output

Enriched corpus: all 35,165 entries with 1–3 categories each (dominant themes ~ poverty_wealth, speech_lying, work_labor, wisdom_folly per the sample), a `modern_text` rendering, cleaned explanations, and a tuned `variant_group`. An `enrich/REPORT.md` with category distribution, audit accuracy, and the variant-tuning decision.

## 10. Open items / risks

- **Modern-spelling quality** is the main risk: 1901 Galician + pre-reform orthography is hard. Mitigation: stronger model for Pass B, glossed examples in the prompt, sample audit. If audit accuracy is poor, `modern_text` ships flagged as best-effort (documented), not silently.
- **Non-determinism:** enriched fields are committed artifacts, not reproducible builds (§2).
- **Batch sizes** (150 / 100) are starting values; tune for structured-output reliability during implementation.
- **Cost/scale:** ~600 agent runs total, within the 1000-agent workflow cap; heavy in-session token use (expected for this engine).

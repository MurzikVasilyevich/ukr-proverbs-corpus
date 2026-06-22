# ukr-proverbs-corpus

Canonical, deduplicated, source-attributed corpus of Ukrainian proverbs and adages,
unified from digitized historical sources.

It is **enriched**: every entry carries a modern-spelling rendering and 1–3 thematic categories.

## Contents
- `corpus.csv` — canonical source-of-truth (35165 entries).
- `corpus.json` — richer export (categories as arrays, per-source annotations).
- `sources.csv` — source registry.
- `enrich/taxonomy.csv` — the fixed 27-theme category vocabulary.
- `enrich/REPORT.md` — enrichment coverage, distribution, and quality audit.
- `enrich/pass_a.json`, `enrich/pass_b.json` — enrichment provenance (raw LLM pass outputs).
- `data/sources/` — committed snapshots of upstream inputs.

## Schema (`corpus.csv`)
| column | meaning |
|---|---|
| id | stable id (`pNNNNNN`) |
| text | verbatim proverb (1901 orthography preserved, never modified) |
| normalized_text | lowercased, punctuation-stripped match key |
| modern_text | modern standard Ukrainian spelling (LLM-generated) |
| keyword | lemma/term (Franko), if any |
| explanation | scholarly note (Franko preferred), cleaned |
| category | 1–3 theme keys from `enrich/taxonomy.csv`, `;`-joined, primary first |
| sources | `;`-joined source citation keys |
| source_refs | `;`-joined per-source references |
| variant_group | id linking probable dialectal variants |

## Categories (taxonomy)
27 fixed themes (see `enrich/taxonomy.csv`): work_labor, poverty_wealth, food_hunger,
drink_alcohol, family_kinship, marriage_gender, speech_lying, wisdom_folly, fate_luck,
time_seasons, death_illness, religion_god, social_relations, class_power, justice_truth,
animals, body_health, home_household, conflict_enmity, friendship_love, travel_distance,
trade_money, ethnic_local, emotion_mood, nature_weather, appearance_reputation, idiom_expressive.

## Enrichment
`category`, `modern_text`, cleaned `explanation`, and the tuned `variant_group` are **LLM-generated
data artifacts** (produced by batched Claude Code agents — not a deterministic build).
Regenerating them requires Claude Code. See `enrich/REPORT.md` for the coverage and quality audit.

## Sources
- **Franko 1901** — Іван Франко, *Галицько-руські народні приповідки* (~30906 entries, with explanations).
- **Mlodzynskyi 2009** — *Практичний російсько-український словник приказок*.
- **Ilkevich 1841** — Григорій Ількевич, *Галицкіи приповѣдки и загадки*.
- **Bobkova** — В.І. Бобкова та ін. (упоряд.), *Українські народні прислів'я та приказки* (modern Ukrainian; 760 proverbs, 700 net-new). Modern collection, so `modern_text` = `text`. See `expand/REPORT.md`.

## Rebuild
```bash
pip install -r requirements.txt
python fetch.py      # refresh data/sources snapshots
python build.py      # regenerate corpus.csv + corpus.json
python -m pytest     # run the test suite
```

## Known limitations
- `sources.csv` carries `Citationkey, Title, Year, Author` only — the upstream source files provide no BibTeX/Year/Author metadata, so BibTeX output (mentioned in the spec) is omitted for lack of source data; Year and Author were added by hand where known.
- Variant groups are link-only (non-destructive): records are grouped by fuzzy similarity (rapidfuzz `token_set_ratio` ≥ 85), never merged; groups larger than 8 are dissolved to curb over-linking. Final: 3413 groups.
- Categorization is best-effort, single-pass: a quality audit (n=40) found modern_text ~95% acceptable and category tags ~85% acceptable (~15% debatable/wrong, usually secondary tags or themes outside the 27-key vocabulary). The primary category tag is the most reliable.

## Stats (last build)
- Total entries: 35865 (100% enriched; +700 net-new from Bobkova)
- With explanation: 30605
- With modern_text: 35865
- Variant groups (tuned): 3497 (116 span Bobkova + Franko)
- Per source: Franko1901 30906, Ilkevich1841 2702, Mlodzynskyi2009 2261, Bobkova 760
- Top categories: emotion_mood, wisdom_folly, idiom_expressive, work_labor, social_relations

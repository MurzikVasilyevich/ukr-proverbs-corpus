# ukr-proverbs-corpus

Canonical, deduplicated, source-attributed corpus of Ukrainian proverbs and adages,
unified from digitized historical sources.

## Contents
- `corpus.csv` — canonical source-of-truth (35165 entries).
- `corpus.json` — richer export preserving per-source annotations.
- `sources.csv` — source registry.
- `data/sources/` — committed snapshots of upstream inputs.

## Schema (`corpus.csv`)
| column | meaning |
|---|---|
| id | stable id (`pNNNNNN`) |
| text | verbatim proverb |
| normalized_text | lowercased, punctuation-stripped match key |
| keyword | lemma/term (Franko), if any |
| explanation | scholarly note (Franko preferred), if any |
| category | thematic category (reserved; populated later) |
| sources | `;`-joined source citation keys |
| source_refs | `;`-joined per-source references |
| variant_group | id linking probable dialectal variants |

## Sources
- **Franko 1901** — Іван Франко, *Галицько-руські народні приповідки* (~30906 entries, with explanations).
- **Mlodzynskyi 2009** — *Практичний російсько-український словник приказок*.
- **Ilkevich 1841** — Григорій Ількевич, *Галицкіи приповѣдки и загадки*.

## Rebuild
```bash
pip install -r requirements.txt
python fetch.py      # refresh data/sources snapshots
python build.py      # regenerate corpus.csv + corpus.json
python -m pytest     # run the test suite
```

## Stats (last build)
- Total entries: 35165
- With explanation: 30605
- Variant groups: 3440
- Per source: Franko1901 30906, Mlodzynskyi2009 2261, Ilkevich1841 2702

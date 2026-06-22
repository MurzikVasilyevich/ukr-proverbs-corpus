# Ukrainian Proverbs Corpus — Enrichment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich all 35,165 corpus entries with thematic categories (multi-label, 27-theme taxonomy), a `modern_text` field, cleaned explanations, and a tuned `variant_group` — via Claude Code agents (Workflow), with the enriched fields committed as data artifacts.

**Architecture:** Deterministic Python supporting code (batching, merge, tuning, export, validators) is TDD'd by implementer subagents. The non-deterministic LLM passes run via the Workflow tool and are **controller-executed** (the Workflow tool cannot nest inside a subagent). File-based handoff: batch input JSON → per-batch output JSON → merge into `corpus.csv`/`corpus.json`.

**Tech Stack:** Python 3 (pandas, pytest); Workflow tool for LLM passes.

**Spec:** `docs/superpowers/specs/2026-06-22-ukr-proverbs-enrichment-design.md`

## Global Constraints

- Python 3.10+; dependencies limited to pandas, rapidfuzz, pytest (stdlib csv/json fine). Use `.venv/bin/python`.
- Verbatim `text` is NEVER modified. `modern_text` is a new, separate field.
- Categories: 1–3 keys per proverb, **all** drawn from the fixed taxonomy in `enrich/taxonomy.csv`; first key = primary; stored in `category` semicolon-joined.
- Enriched `corpus.csv` column order (10 cols): `id, text, normalized_text, modern_text, keyword, explanation, category, sources, source_refs, variant_group`.
- Losslessness: enrichment merge must cover 100% of ids and neither add nor drop records (assert in code).
- Enriched fields are LLM-generated **data artifacts** (not byte-reproducible); committed as the source of truth.
- Commits use local git identity `MurzikVasilyevich <vasilyevichmurzik@gmail.com>`; append the session footer (Co-Authored-By + Claude-Session) to every commit.
- Work on branch `feat/enrichment` (created by the controller before Task 1).
- **Task types:** `[IMPL]` = TDD implementer subagent task. `[CONTROLLER-RUN]` = executed by the controller (main loop) using the Workflow tool; not dispatched to an implementer.

---

### Task 1 [IMPL]: enrich/ scaffold + taxonomy.csv + schema validators

**Files:**
- Create: `enrich/__init__.py` (empty)
- Create: `enrich/taxonomy.csv`
- Create: `enrich/schema.py`
- Create: `tests/test_enrich_schema.py`

**Interfaces:**
- Produces:
  - `load_taxonomy(path="enrich/taxonomy.csv") -> dict[str, str]` — returns `{key: ukrainian_label}` for all 27 themes.
  - `TAXONOMY_KEYS: frozenset[str]` — the 27 keys (loaded once from the csv).
  - `validate_categories(cats: list[str], keys: frozenset[str]) -> list[str]` — raises `ValueError` if empty, >3, or any key ∉ `keys`; returns `cats` unchanged otherwise.
  - `validate_pass_a_record(rec: dict, keys: frozenset[str]) -> None` — raises `ValueError` unless `rec` has non-empty string `id`, a `categories` list passing `validate_categories`, and a string `explanation_clean`.
  - `validate_pass_b_record(rec: dict) -> None` — raises `ValueError` unless `rec` has non-empty string `id` and non-empty string `modern_text`.

- [ ] **Step 1: Create `enrich/taxonomy.csv`** (header `key,ukrainian_label,scope_note`, then these 27 rows verbatim):

```csv
key,ukrainian_label,scope_note
work_labor,Праця і ремесло,"working, diligence, idleness, crafts, tools, the ethic of effort"
poverty_wealth,Бідність і багатство,"rich vs poor, money, coins, debt, material want"
food_hunger,Їжа і голод,"eating, hunger, bread, specific foods, fasting"
drink_alcohol,Пиття і п'янство,"drinking, drunkenness, tavern life, горілка, пиво"
family_kinship,Родина і спорідненість,"parents, children, siblings, relatives, household as a unit"
marriage_gender,Шлюб і стать,"marriage, husbands/wives, widows, courtship, gender roles"
speech_lying,Мова і брехня,"talking, gossip, lying, silence, slander, words vs deeds"
wisdom_folly,Розум і дурість,"intelligence, foolishness, advice, learning, experience"
fate_luck,Доля і щастя,"luck, fortune, fate, chance, happiness, misfortune"
time_seasons,Час і пори року,"time, haste, delay, seasons, agricultural calendar, saints' days"
death_illness,Смерть і хвороба,"dying, illness, aging, bodily decay, death-curses"
religion_god,Бог і церква,"God, devil, saints, church, sin, prayer, blessing"
social_relations,Громада і сусідство,"neighbors, community, reputation, public shame/honor"
class_power,Стани і влада,"lords/serfs, nobility, clergy, officials, hierarchy"
justice_truth,Правда і кривда,"truth, justice, law, honesty, fairness, rights"
animals,Тварини,"animal-vehicle proverbs making a human point"
body_health,Тіло і здоров'я,"bodily states, strength, beauty, physical appearance"
home_household,Хата і господарство,"the house, domestic order, farm property"
conflict_enmity,Сварка і ворожнеча,"quarrels, fighting, revenge, enemies, troublemakers"
friendship_love,Дружба і любов,"friendship, love, loyalty, affection"
travel_distance,Дорога і мандри,"roads, travel, departure, far-off places, wandering"
trade_money,Торгівля і гроші,"buying, selling, markets, bargaining, prices"
ethnic_local,Народи і місця,"named ethnic groups, regions, local figures"
emotion_mood,Почуття і настрій,"anger, grief, fear, joy, envy, shame as states"
nature_weather,Природа і погода,"sky, weather, wind, water, plants, landscape"
appearance_reputation,Зовнішність і слава,"looks vs reality, good vs bad name"
idiom_expressive,Фразеологія та вигуки,"formulaic exclamations, curses, toasts, set phrases"
```

- [ ] **Step 2: Write the failing test** — `tests/test_enrich_schema.py`:

```python
import pytest
from enrich.schema import (
    load_taxonomy, TAXONOMY_KEYS, validate_categories,
    validate_pass_a_record, validate_pass_b_record,
)


def test_taxonomy_has_27_keys():
    tax = load_taxonomy()
    assert len(tax) == 27
    assert tax["work_labor"] == "Праця і ремесло"
    assert "idiom_expressive" in TAXONOMY_KEYS


def test_validate_categories_ok():
    assert validate_categories(["work_labor", "animals"], TAXONOMY_KEYS) == ["work_labor", "animals"]


@pytest.mark.parametrize("cats", [[], ["a", "b", "c", "d"], ["not_a_theme"]])
def test_validate_categories_rejects(cats):
    with pytest.raises(ValueError):
        validate_categories(cats, TAXONOMY_KEYS)


def test_pass_a_record_ok_and_bad():
    validate_pass_a_record({"id": "p000001", "categories": ["animals"], "explanation_clean": "x"}, TAXONOMY_KEYS)
    with pytest.raises(ValueError):
        validate_pass_a_record({"id": "", "categories": ["animals"], "explanation_clean": "x"}, TAXONOMY_KEYS)
    with pytest.raises(ValueError):
        validate_pass_a_record({"id": "p1", "categories": ["nope"], "explanation_clean": "x"}, TAXONOMY_KEYS)


def test_pass_b_record_ok_and_bad():
    validate_pass_b_record({"id": "p1", "modern_text": "сучасний текст"})
    with pytest.raises(ValueError):
        validate_pass_b_record({"id": "p1", "modern_text": ""})
```

- [ ] **Step 3: Run test, verify it fails** — `.venv/bin/python -m pytest tests/test_enrich_schema.py -v` → FAIL (`ModuleNotFoundError: enrich.schema`).

- [ ] **Step 4: Implement** — `enrich/schema.py`:

```python
from __future__ import annotations

import csv

_TAXONOMY_PATH = "enrich/taxonomy.csv"


def load_taxonomy(path: str = _TAXONOMY_PATH) -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        return {row["key"]: row["ukrainian_label"] for row in csv.DictReader(f)}


TAXONOMY_KEYS: frozenset[str] = frozenset(load_taxonomy().keys())


def validate_categories(cats: list[str], keys: frozenset[str]) -> list[str]:
    if not isinstance(cats, list) or not (1 <= len(cats) <= 3):
        raise ValueError(f"categories must be a list of 1-3 keys, got {cats!r}")
    bad = [c for c in cats if c not in keys]
    if bad:
        raise ValueError(f"categories not in taxonomy: {bad!r}")
    return cats


def validate_pass_a_record(rec: dict, keys: frozenset[str]) -> None:
    if not isinstance(rec.get("id"), str) or not rec["id"]:
        raise ValueError(f"pass-A record missing id: {rec!r}")
    validate_categories(rec.get("categories"), keys)
    if not isinstance(rec.get("explanation_clean"), str):
        raise ValueError(f"pass-A record missing explanation_clean: {rec!r}")


def validate_pass_b_record(rec: dict) -> None:
    if not isinstance(rec.get("id"), str) or not rec["id"]:
        raise ValueError(f"pass-B record missing id: {rec!r}")
    if not isinstance(rec.get("modern_text"), str) or not rec["modern_text"].strip():
        raise ValueError(f"pass-B record missing modern_text: {rec!r}")
```

- [ ] **Step 5: Run test, verify pass** — `.venv/bin/python -m pytest tests/test_enrich_schema.py -v` → PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add enrich/__init__.py enrich/taxonomy.csv enrich/schema.py tests/test_enrich_schema.py
git commit -m "feat(enrich): taxonomy + enrichment schema validators"
```

---

### Task 2 [IMPL]: enrich/batch.py — split corpus into batch input files

**Files:**
- Create: `enrich/batch.py`
- Create: `tests/test_enrich_batch.py`

**Interfaces:**
- Consumes: `corpus.csv` (columns per Global Constraints).
- Produces:
  - `make_batches(corpus_path: str, out_dir: str, fields: list[str], size: int) -> list[str]` — reads `corpus_path`, writes batch files `{out_dir}/batch_{i:04d}.json` each containing a JSON list of dicts with only the requested `fields` (always including `id`), `size` rows per file (last may be smaller). Returns the written paths. Order preserved.

- [ ] **Step 1: Write the failing test** — `tests/test_enrich_batch.py`:

```python
import csv, json
from enrich.batch import make_batches


def _write_corpus(p, n):
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "text", "keyword", "explanation"])
        w.writeheader()
        for i in range(1, n + 1):
            w.writerow({"id": f"p{i:06d}", "text": f"t{i}", "keyword": "", "explanation": f"e{i}"})


def test_make_batches_splits_and_projects(tmp_path):
    corpus = tmp_path / "corpus.csv"; _write_corpus(corpus, 5)
    out = tmp_path / "in"
    paths = make_batches(str(corpus), str(out), fields=["id", "text"], size=2)
    assert len(paths) == 3                      # 2 + 2 + 1
    b0 = json.loads((out / "batch_0000.json").read_text(encoding="utf-8"))
    assert b0 == [{"id": "p000001", "text": "t1"}, {"id": "p000002", "text": "t2"}]
    b2 = json.loads((out / "batch_0002.json").read_text(encoding="utf-8"))
    assert b2 == [{"id": "p000005", "text": "t5"}]
    # id always included even if not requested
    paths2 = make_batches(str(corpus), str(tmp_path / "in2"), fields=["text"], size=10)
    rec = json.loads((tmp_path / "in2" / "batch_0000.json").read_text(encoding="utf-8"))[0]
    assert "id" in rec
```

- [ ] **Step 2: Run test, verify fail** — `.venv/bin/python -m pytest tests/test_enrich_batch.py -v` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement** — `enrich/batch.py`:

```python
from __future__ import annotations

import csv
import json
import os


def make_batches(corpus_path: str, out_dir: str, fields: list[str], size: int) -> list[str]:
    if size < 1:
        raise ValueError("size must be >= 1")
    cols = list(fields)
    if "id" not in cols:
        cols = ["id"] + cols
    os.makedirs(out_dir, exist_ok=True)
    with open(corpus_path, encoding="utf-8") as f:
        rows = [{c: r[c] for c in cols} for r in csv.DictReader(f)]
    paths: list[str] = []
    for i in range(0, len(rows), size):
        chunk = rows[i:i + size]
        p = os.path.join(out_dir, f"batch_{i // size:04d}.json")
        with open(p, "w", encoding="utf-8") as out:
            json.dump(chunk, out, ensure_ascii=False)
        paths.append(p)
    return paths
```

- [ ] **Step 4: Run test, verify pass** — PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add enrich/batch.py tests/test_enrich_batch.py
git commit -m "feat(enrich): corpus batching for workflow passes"
```

---

### Task 3 [IMPL]: enrich/merge.py — merge pass outputs into enriched rows

**Files:**
- Create: `enrich/merge.py`
- Create: `tests/test_enrich_merge.py`

**Interfaces:**
- Consumes: `enrich.schema.validate_pass_a_record`, `validate_pass_b_record`, `TAXONOMY_KEYS`.
- Produces:
  - `load_outputs(dir_path: str) -> dict[str, dict]` — reads every `*.json` (each a JSON list of records) in `dir_path`, validates nothing here, returns `{id: record}`; raises `ValueError` on a duplicate id across files.
  - `merge(corpus_rows: list[dict], pass_a: dict[str, dict], pass_b: dict[str, dict], keys=TAXONOMY_KEYS) -> list[dict]` — for each corpus row (by `id`): validate its pass_a and pass_b records; set `modern_text` (from B), `category` = `;`.join(A categories), `explanation` = A `explanation_clean`; keep all other columns. Raises `ValueError` if any corpus id is missing from pass_a or pass_b, or if pass_a/pass_b contain ids not in the corpus. Returns enriched rows in corpus order (each a dict with keys: id, text, normalized_text, modern_text, keyword, explanation, category, sources, source_refs, variant_group).

- [ ] **Step 1: Write the failing test** — `tests/test_enrich_merge.py`:

```python
import json
import pytest
from enrich.merge import load_outputs, merge


def _corpus():
    return [
        {"id": "p000001", "text": "Т1", "normalized_text": "т1", "keyword": "k1",
         "explanation": "raw1", "category": "", "sources": "Franko1901", "source_refs": "А", "variant_group": ""},
        {"id": "p000002", "text": "Т2", "normalized_text": "т2", "keyword": "",
         "explanation": "raw2", "category": "", "sources": "Mlodzynskyi2009", "source_refs": "2", "variant_group": "v0001"},
    ]


def test_merge_sets_enriched_fields():
    a = {"p000001": {"id": "p000001", "categories": ["animals", "wisdom_folly"], "explanation_clean": "clean1"},
         "p000002": {"id": "p000002", "categories": ["food_hunger"], "explanation_clean": "clean2"}}
    b = {"p000001": {"id": "p000001", "modern_text": "Т1 модерн"},
         "p000002": {"id": "p000002", "modern_text": "Т2 модерн"}}
    out = merge(_corpus(), a, b)
    assert out[0]["modern_text"] == "Т1 модерн"
    assert out[0]["category"] == "animals;wisdom_folly"
    assert out[0]["explanation"] == "clean1"
    assert out[0]["text"] == "Т1"  # untouched
    # column order
    assert list(out[0].keys()) == ["id", "text", "normalized_text", "modern_text", "keyword",
                                   "explanation", "category", "sources", "source_refs", "variant_group"]


def test_merge_missing_id_raises():
    a = {"p000001": {"id": "p000001", "categories": ["animals"], "explanation_clean": "c"}}
    b = {"p000001": {"id": "p000001", "modern_text": "m"}}
    with pytest.raises(ValueError):
        merge(_corpus(), a, b)  # p000002 missing


def test_load_outputs_dup_id_raises(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps([{"id": "p1", "x": 1}]), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps([{"id": "p1", "x": 2}]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_outputs(str(tmp_path))
```

- [ ] **Step 2: Run test, verify fail** — FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement** — `enrich/merge.py`:

```python
from __future__ import annotations

import glob
import json
import os

from enrich.schema import TAXONOMY_KEYS, validate_pass_a_record, validate_pass_b_record

_COLUMNS = ["id", "text", "normalized_text", "modern_text", "keyword",
            "explanation", "category", "sources", "source_refs", "variant_group"]


def load_outputs(dir_path: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(glob.glob(os.path.join(dir_path, "*.json"))):
        with open(p, encoding="utf-8") as f:
            for rec in json.load(f):
                rid = rec.get("id")
                if rid in out:
                    raise ValueError(f"duplicate id {rid!r} across output files")
                out[rid] = rec
    return out


def merge(corpus_rows, pass_a, pass_b, keys=TAXONOMY_KEYS):
    corpus_ids = {r["id"] for r in corpus_rows}
    extra_a = set(pass_a) - corpus_ids
    extra_b = set(pass_b) - corpus_ids
    if extra_a or extra_b:
        raise ValueError(f"pass output has ids not in corpus: {sorted(extra_a | extra_b)[:5]}")
    result = []
    for row in corpus_rows:
        rid = row["id"]
        if rid not in pass_a:
            raise ValueError(f"id {rid} missing from pass A")
        if rid not in pass_b:
            raise ValueError(f"id {rid} missing from pass B")
        a, b = pass_a[rid], pass_b[rid]
        validate_pass_a_record(a, keys)
        validate_pass_b_record(b)
        enriched = {
            "id": rid,
            "text": row["text"],
            "normalized_text": row["normalized_text"],
            "modern_text": b["modern_text"],
            "keyword": row["keyword"],
            "explanation": a["explanation_clean"],
            "category": ";".join(a["categories"]),
            "sources": row["sources"],
            "source_refs": row["source_refs"],
            "variant_group": row["variant_group"],
        }
        result.append({c: enriched[c] for c in _COLUMNS})
    return result
```

- [ ] **Step 4: Run test, verify pass** — PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add enrich/merge.py tests/test_enrich_merge.py
git commit -m "feat(enrich): merge pass outputs into enriched rows with coverage checks"
```

---

### Task 4 [IMPL]: enrich/export.py — write enriched corpus.csv + corpus.json

**Files:**
- Create: `enrich/export.py`
- Create: `tests/test_enrich_export.py`

**Interfaces:**
- Produces:
  - `write_enriched_csv(rows: list[dict], path: str) -> None` — writes the 10 columns in Global-Constraints order; UTF-8; `category` written as-is (already `;`-joined).
  - `enrich_json(base_json: list[dict], rows_by_id: dict[str, dict]) -> list[dict]` — takes the existing `corpus.json` objects and, per record, adds `modern_text` (from the enriched row), replaces `category` with a list (split the enriched `;`-joined string), and sets the explanation of the first annotation having a non-empty explanation to the enriched (cleaned) `explanation`. Returns new objects (does not mutate inputs).
  - `write_json(objs: list[dict], path: str) -> None` — `ensure_ascii=False, indent=2`, trailing newline.

- [ ] **Step 1: Write the failing test** — `tests/test_enrich_export.py`:

```python
import csv, json
from enrich.export import write_enriched_csv, enrich_json, write_json


def _rows():
    return [{"id": "p000001", "text": "Т1", "normalized_text": "т1", "modern_text": "М1",
             "keyword": "k", "explanation": "clean1", "category": "animals;wisdom_folly",
             "sources": "Franko1901", "source_refs": "А", "variant_group": ""}]


def test_write_enriched_csv(tmp_path):
    p = tmp_path / "c.csv"; write_enriched_csv(_rows(), str(p))
    r = list(csv.DictReader(p.open(encoding="utf-8")))[0]
    assert list(r.keys()) == ["id", "text", "normalized_text", "modern_text", "keyword",
                              "explanation", "category", "sources", "source_refs", "variant_group"]
    assert r["modern_text"] == "М1" and r["category"] == "animals;wisdom_folly"


def test_enrich_json_adds_modern_and_category_list():
    base = [{"id": "p000001", "text": "Т1", "normalized_text": "т1", "keyword": "k",
             "category": None, "variant_group": None,
             "annotations": [{"source": "Franko1901", "ref": "А", "explanation": "raw1"}]}]
    rows = {r["id"]: r for r in _rows()}
    out = enrich_json(base, rows)
    assert out[0]["modern_text"] == "М1"
    assert out[0]["category"] == ["animals", "wisdom_folly"]
    assert out[0]["annotations"][0]["explanation"] == "clean1"
    # input not mutated
    assert base[0].get("modern_text") is None
```

- [ ] **Step 2: Run test, verify fail** — FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement** — `enrich/export.py`:

```python
from __future__ import annotations

import copy
import csv
import json

_COLUMNS = ["id", "text", "normalized_text", "modern_text", "keyword",
            "explanation", "category", "sources", "source_refs", "variant_group"]


def write_enriched_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in _COLUMNS})


def enrich_json(base_json: list[dict], rows_by_id: dict[str, dict]) -> list[dict]:
    out = []
    for obj in base_json:
        o = copy.deepcopy(obj)
        row = rows_by_id[o["id"]]
        o["modern_text"] = row["modern_text"]
        o["category"] = row["category"].split(";") if row["category"] else []
        clean = row["explanation"]
        for ann in o.get("annotations", []):
            if ann.get("explanation"):
                ann["explanation"] = clean
                break
        out.append(o)
    return out


def write_json(objs: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(objs, f, ensure_ascii=False, indent=2)
        f.write("\n")
```

- [ ] **Step 4: Run test, verify pass** — PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add enrich/export.py tests/test_enrich_export.py
git commit -m "feat(enrich): enriched csv/json export"
```

---

### Task 5 [IMPL]: enrich/tune_variants.py — recompute variant_group with tuned params

**Files:**
- Create: `enrich/tune_variants.py`
- Create: `tests/test_enrich_tune.py`

**Interfaces:**
- Consumes: `core.dedup.link_variants`, `core.schema.CanonicalRecord`.
- Produces:
  - `recompute_variant_groups(rows: list[dict], threshold: int, max_group_size: int | None) -> list[dict]` — builds `CanonicalRecord`s from rows' `text`/`normalized_text`, calls `link_variants(records, threshold=threshold)`, then if `max_group_size` is set, any variant group larger than it is dissolved (its members get `variant_group=""`) — a conservative anti-over-linking rule. Writes the resulting `variant_group` back onto copies of the input rows (other fields untouched). Returns new rows in input order.

- [ ] **Step 1: Write the failing test** — `tests/test_enrich_tune.py`:

```python
from enrich.tune_variants import recompute_variant_groups


def _rows(pairs):
    return [{"id": f"p{i:06d}", "text": t, "normalized_text": nt, "variant_group": "OLD"}
            for i, (t, nt) in enumerate(pairs, 1)]


def test_links_at_threshold_and_writes_back():
    rows = _rows([("баба з воза", "баба з воза"), ("баба із воза", "баба із воза"),
                  ("цілком інша річ", "цілком інша річ")])
    out = recompute_variant_groups(rows, threshold=80, max_group_size=None)
    assert out[0]["variant_group"] == out[1]["variant_group"] != ""
    assert out[2]["variant_group"] == ""          # singleton cleared
    assert out[0]["text"] == "баба з воза"          # untouched


def test_max_group_size_dissolves_large_groups():
    # four near-identical -> one group of 4; cap at 3 dissolves it
    rows = _rows([("як ту", "як ту а"), ("як ту", "як ту б"), ("як ту", "як ту в"), ("як ту", "як ту г")])
    out = recompute_variant_groups(rows, threshold=70, max_group_size=3)
    assert all(r["variant_group"] == "" for r in out)
```

- [ ] **Step 2: Run test, verify fail** — FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement** — `enrich/tune_variants.py`:

```python
from __future__ import annotations

from collections import Counter

from core.dedup import link_variants
from core.schema import CanonicalRecord


def recompute_variant_groups(rows, threshold, max_group_size=None):
    records = [CanonicalRecord(text=r["text"], normalized_text=r["normalized_text"]) for r in rows]
    link_variants(records, threshold=threshold)
    labels = [rec.variant_group for rec in records]
    if max_group_size is not None:
        sizes = Counter(l for l in labels if l)
        labels = ["" if (l and sizes[l] > max_group_size) else l for l in labels]
    out = []
    for r, label in zip(rows, labels):
        nr = dict(r)
        nr["variant_group"] = label
        out.append(nr)
    return out
```

- [ ] **Step 4: Run test, verify pass** — PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add enrich/tune_variants.py tests/test_enrich_tune.py
git commit -m "feat(enrich): variant-group recomputation with tunable threshold + size cap"
```

---

### Task 6 [IMPL]: enrich/prompts.py — frozen prompt builders for Pass A / Pass B

**Files:**
- Create: `enrich/prompts.py`
- Create: `tests/test_enrich_prompts.py`

**Interfaces:**
- Consumes: `enrich.schema.load_taxonomy`.
- Produces:
  - `pass_a_prompt(batch_path: str, taxonomy: dict[str, str]) -> str` — builds the categorization+cleanup instruction. MUST: embed every taxonomy key + label; instruct multi-label 1–3, primary first; allow `idiom_expressive` for opaque entries; warn about Galician/pre-reform orthography; tell the agent to Read `batch_path` and return one record per input id with fields `id, categories, explanation_clean`.
  - `pass_b_prompt(batch_path: str) -> str` — builds the modern-spelling instruction. MUST: explain source is 1901 Galician/etymological orthography; give ≥3 glossed examples (e.g. `богато→багато`, `сї→ся`, `ѣ→і`); instruct to output modern standard Ukrainian preserving meaning and word order; tell the agent to Read `batch_path` and return one record per id with fields `id, modern_text`; never drop or merge entries.
  - `PASS_A_SCHEMA`, `PASS_B_SCHEMA` — JSON Schema dicts (array of objects) for the structured output of each pass.

- [ ] **Step 1: Write the failing test** — `tests/test_enrich_prompts.py`:

```python
from enrich.prompts import pass_a_prompt, pass_b_prompt, PASS_A_SCHEMA, PASS_B_SCHEMA
from enrich.schema import load_taxonomy


def test_pass_a_prompt_contains_all_keys_and_path():
    tax = load_taxonomy()
    p = pass_a_prompt("/tmp/in/batch_0001.json", tax)
    for key in tax:
        assert key in p
    assert "/tmp/in/batch_0001.json" in p
    assert "1" in p and "3" in p              # multi-label range mentioned
    assert "idiom_expressive" in p


def test_pass_b_prompt_has_examples_and_path():
    p = pass_b_prompt("/tmp/in/batch_0001.json")
    assert "/tmp/in/batch_0001.json" in p
    assert "богато" in p                       # at least one glossed example
    assert "modern_text" in p


def test_schemas_are_arrays_of_objects():
    assert PASS_A_SCHEMA["type"] == "array"
    assert set(PASS_A_SCHEMA["items"]["required"]) == {"id", "categories", "explanation_clean"}
    assert set(PASS_B_SCHEMA["items"]["required"]) == {"id", "modern_text"}
```

- [ ] **Step 2: Run test, verify fail** — FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement** — `enrich/prompts.py`:

```python
from __future__ import annotations

PASS_A_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["id", "categories", "explanation_clean"],
        "properties": {
            "id": {"type": "string"},
            "categories": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
            "explanation_clean": {"type": "string"},
        },
    },
}

PASS_B_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["id", "modern_text"],
        "properties": {"id": {"type": "string"}, "modern_text": {"type": "string"}},
    },
}


def pass_a_prompt(batch_path: str, taxonomy: dict[str, str]) -> str:
    lines = "\n".join(f"- {k}: {v}" for k, v in taxonomy.items())
    return f"""You are a Ukrainian paremiologist tagging proverbs by theme and cleaning their explanations.

Read this JSON file — a list of proverbs, each with `id`, `text`, `keyword`, `explanation`:
{batch_path}

The text is in 1901 Galician / pre-reform Ukrainian orthography — read past dialectal spelling to the meaning.

THEMES (use ONLY these keys):
{lines}

For EVERY proverb in the file, return an object with:
- `id`: the proverb's id, unchanged.
- `categories`: 1 to 3 theme keys from the list above, MOST relevant FIRST (the primary vehicle/target of the proverb). Use `idiom_expressive` only when no thematic reading is defensible (opaque curses/formulae).
- `explanation_clean`: the input `explanation` with OCR noise, stray whitespace, and broken hyphenation removed. If the input explanation is empty, return "".

Return one object per input id — do not skip, merge, or invent ids."""


def pass_b_prompt(batch_path: str) -> str:
    return f"""You are a Ukrainian linguist modernizing the spelling of historical proverbs.

Read this JSON file — a list of proverbs, each with `id` and `text`:
{batch_path}

The `text` is in Ivan Franko's 1901 Galician / etymological orthography. Render each into MODERN STANDARD Ukrainian spelling, preserving meaning, word order, and dialectal lexicon where it has no standard equivalent. Examples of the kind of change intended:
- богато -> багато
- archaic reflexive сї -> ся
- ѣ (yat) -> і  (e.g. дѣти -> діти)
- pre-reform hard-sign / doubled forms -> modern forms

For EVERY proverb, return an object with:
- `id`: unchanged.
- `modern_text`: the modernized spelling (never empty; if already modern, return it unchanged).

Return one object per input id — never drop or merge entries."""
```

- [ ] **Step 4: Run test, verify pass** — PASS (3 passed). (If `test_pass_b_prompt` fails on the example marker, ensure the literal `богато` appears in `pass_b_prompt`.)

- [ ] **Step 5: Commit**

```bash
git add enrich/prompts.py tests/test_enrich_prompts.py
git commit -m "feat(enrich): frozen Pass A/B prompt builders + output schemas"
```

---

### Task 7 [CONTROLLER-RUN]: Generate batch inputs + run Pass A (categorize + clean)

Executed by the controller (Workflow tool). Not an implementer task.

- [ ] **Step 1:** Build base corpus fresh and snapshot pre-enrichment counts:
  `.venv/bin/python build.py` then record total + variant_groups.
- [ ] **Step 2:** Generate Pass A batch inputs (fields `id,text,keyword,explanation`, size 150):
  `.venv/bin/python -c "from enrich.batch import make_batches; print(len(make_batches('corpus.csv','enrich/work/a_in',['id','text','keyword','explanation'],150)))"` → ~235 files.
- [ ] **Step 3:** Run the Pass A workflow: one agent per batch (cheaper model), each Reads its `enrich/work/a_in/batch_NNNN.json`, applies `pass_a_prompt`, returns `PASS_A_SCHEMA` output; the controller writes each batch result to `enrich/work/a_out/batch_NNNN.json`. Use the agent counter / concurrency cap; process in chunks if the aggregate return is large. Validate each record with `validate_pass_a_record` as written.
- [ ] **Step 4:** Verify coverage: number of ids across `enrich/work/a_out/*.json` equals corpus size; every category ∈ taxonomy. Re-run any failed/missing batches.

(No commit yet — outputs are committed in Task 9.)

---

### Task 8 [CONTROLLER-RUN]: Run Pass B (modern-spelling)

Executed by the controller (Workflow tool).

- [ ] **Step 1:** Generate Pass B batch inputs (fields `id,text`, size 100):
  `.venv/bin/python -c "from enrich.batch import make_batches; print(len(make_batches('corpus.csv','enrich/work/b_in',['id','text'],100)))"` → ~352 files.
- [ ] **Step 2:** Run the Pass B workflow: one agent per batch (stronger model), each Reads its input, applies `pass_b_prompt`, returns `PASS_B_SCHEMA`; controller writes `enrich/work/b_out/batch_NNNN.json`. Validate with `validate_pass_b_record`.
- [ ] **Step 3:** Verify coverage = corpus size; re-run gaps.

---

### Task 9 [CONTROLLER-RUN]: Merge, tune variants, validate, export

Executed by the controller.

- [ ] **Step 1: Merge.**
  ```python
  from enrich.merge import load_outputs, merge
  import csv
  rows = list(csv.DictReader(open("corpus.csv", encoding="utf-8")))
  a = load_outputs("enrich/work/a_out"); b = load_outputs("enrich/work/b_out")
  enriched = merge(rows, a, b)   # raises if any id uncovered
  ```
- [ ] **Step 2: Variant tuning.** Sample ~40 variant groups (weighted to large ones); dispatch judge agents to rate intra-group cohesion; from the precision result choose `threshold` (≥85) and `max_group_size`. Apply:
  ```python
  from enrich.tune_variants import recompute_variant_groups
  enriched = recompute_variant_groups(enriched, threshold=CHOSEN, max_group_size=CHOSEN_OR_None)
  ```
  Record the decision and measured precision in `enrich/REPORT.md`.
- [ ] **Step 3: Export.**
  ```python
  import json
  from enrich.export import write_enriched_csv, enrich_json, write_json
  write_enriched_csv(enriched, "corpus.csv")
  base = json.load(open("corpus.json", encoding="utf-8"))
  write_json(enrich_json(base, {r["id"]: r for r in enriched}), "corpus.json")
  ```
- [ ] **Step 4: Validation audit.** Random sample ~200 enriched entries; judge agents rate (a) category correctness, (b) `modern_text` fidelity. Write counts, category distribution, audit accuracy, and the variant decision to `enrich/REPORT.md`. If `modern_text` audit accuracy is poor, note `modern_text` is best-effort in `REPORT.md` and the README.
- [ ] **Step 5: Hard checks.** `corpus.csv` has 10 columns in order; row count = pre-enrichment count; every `category` cell non-empty with keys ∈ taxonomy; `corpus.json` parses with the same record count.
- [ ] **Step 6: Commit** the enriched artifacts + provenance:
  ```bash
  git add corpus.csv corpus.json enrich/work/a_out enrich/work/b_out enrich/REPORT.md
  git commit -m "feat(enrich): enriched corpus (categories, modern_text, cleaned explanations, tuned variants)"
  ```
  (`enrich/work/a_in` and `b_in` are regenerable inputs — add `enrich/work/*_in/` to `.gitignore`.)

---

### Task 10 [IMPL]: README update + final suite + push

**Files:**
- Modify: `README.md`
- Modify: `.gitignore` (add `enrich/work/*_in/`)

- [ ] **Step 1:** Update `README.md`: document the new `modern_text` column and multi-label `category`; add a "Taxonomy" section (link `enrich/taxonomy.csv`, 27 themes); add an "Enrichment" section noting fields are LLM-generated (regeneration needs Claude Code) and linking `enrich/REPORT.md`; refresh the stats block with the post-enrichment category distribution and variant-group count.
- [ ] **Step 2:** Add `enrich/work/*_in/` to `.gitignore`.
- [ ] **Step 3:** Run the full suite: `.venv/bin/python -m pytest -q` → all pass (SP1 + enrich tests).
- [ ] **Step 4: Commit & push.**
  ```bash
  git add README.md .gitignore
  git commit -m "docs(enrich): document enriched schema, taxonomy, and enrichment report"
  # controller merges feat/enrichment -> main and pushes origin + dmytro via finishing-a-development-branch
  ```

---

## Self-Review

**1. Spec coverage:**
- §1 categorization → Tasks 1 (taxonomy/validators), 6 (Pass A prompt), 7 (run), 9 (merge). ✓
- §1 modern-spelling → Tasks 6 (Pass B prompt), 8 (run), 9 (merge). ✓
- §1 explanation cleanup → Pass A (`explanation_clean`), merge. ✓
- §1 variant tuning → Task 5 (recompute) + Task 9 Step 2 (analysis/decision). ✓
- §3 taxonomy (27 themes) → Task 1 `taxonomy.csv` verbatim. ✓
- §4 schema (10 cols, modern_text, category joined, explanation in place) → Tasks 3, 4. ✓
- §5 pipeline (Pass A/B, merge, tune, validation) → Tasks 6–9. ✓
- §6 files (`enrich/` layout) → all tasks. ✓
- §7 testing → Tasks 1–6 each TDD; integration via merge/export tests + Task 9 checks. ✓
- §2/§10 non-determinism, artifacts committed → Task 9 Step 6. ✓

**2. Placeholder scan:** `CHOSEN`/`CHOSEN_OR_None` in Task 9 Step 2 are runtime decisions from the tuning analysis (the controller fills them from measured precision), not unfilled plan placeholders — the decision procedure is specified. Counts in README (Task 10) come from real output. No "TBD/implement later" steps. Code steps all contain complete code.

**3. Type consistency:** `validate_pass_a_record(rec, keys)` / `validate_pass_b_record(rec)` signatures match between Task 1 (def) and Task 3 (use). `merge(corpus_rows, pass_a, pass_b, keys)` consistent Task 3 ↔ Task 9. `recompute_variant_groups(rows, threshold, max_group_size)` consistent Task 5 ↔ Task 9. The 10-column order is identical in Tasks 3, 4, and Global Constraints. `pass_a_prompt`/`pass_b_prompt`/`PASS_A_SCHEMA`/`PASS_B_SCHEMA` consistent Task 6 ↔ Tasks 7/8.

No issues found.

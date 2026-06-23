# Ukrainian Proverbs — Semantic Search (SP5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in meaning-based search + find-similar over the 40,444-proverb corpus using Workers AI `bge-m3` embeddings and a managed Cloudflare Vectorize index.

**Architecture:** A Python `embed/` pipeline composes per-proverb text (`text`+`modern_text`+`explanation`), embeds only new/changed entries (manifest diff), and upserts vectors to Vectorize. The existing Worker gains `/api/semantic` and `/api/similar/:id`: it embeds the query via the `AI` binding, queries the `VECTORIZE` binding, then maps result ids to the in-memory corpus and applies score-cutoff + category/source filters. The client adds a «за змістом» toggle and a «Схожі прислів'я» detail section; lexical search stays the offline default.

**Tech Stack:** Python 3 (pytest) for the embed pipeline; TypeScript + Cloudflare Workers (AI + Vectorize bindings) + vitest for the app.

**Spec:** `docs/superpowers/specs/2026-06-23-ukr-proverbs-semantic-search-design.md`

## Global Constraints

- Embedding model: **`@cf/baai/bge-m3`** — 1024 dimensions, **cosine** metric. Vectorize index name: **`proverbs-bge-m3`**.
- Embed-text composition (uniform): `text`, then `modern_text` **only if it differs** from `text`, then `explanation` **only if present**, truncated to the first **1000** characters — joined by `"\n"`.
- Vectorize **topK max = 100** (platform limit). `/api/semantic` uses topK 100; the score-cutoff + category/source filter are applied **in the Worker** against the in-memory corpus (vectors store only `{id}` metadata).
- Default semantic score cutoff: **0.4**, overridable via `?minScore=`. `limit` default 50, max 200 (consistent with `/api/search`).
- All API responses: JSON, `Access-Control-Allow-Origin: *`, same error style as existing routes. Lexical `/api/search` and offline behaviour are **unchanged**.
- Python pipeline run manually; uses `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` from env. Tests never hit the network (inject stubs).
- Commit identity `MurzikVasilyevich <vasilyevichmurzik@gmail.com>`; append the session footer. Branch `feat/semantic-search`. Push: origin needs `gh auth switch --user MurzikVasilyevich` (HTTPS); dmytro is SSH.
- **Task types:** `[IMPL]` = TDD implementer. `[CONTROLLER-RUN]` = controller (account/billing, index creation, embedding run, deploy — confirm with user).

---

### Task 1 [IMPL]: embed/compose.py — embed-text composition + hash

**Files:** Create `embed/__init__.py` (empty), `embed/compose.py`, `tests/test_embed_compose.py`.

**Interfaces:**
- Produces:
  - `compose_embed_text(row: dict, max_expl: int = 1000) -> str` — joins `row["text"]`, `row["modern_text"]` (only if `.strip()` differs from text's), `row["explanation"][:max_expl]` (only if non-empty after strip) with `"\n"`.
  - `content_hash(s: str) -> str` — `hashlib.sha1(s.encode("utf-8")).hexdigest()`.

- [ ] **Step 1: Write the failing test** — `tests/test_embed_compose.py`:
```python
from embed.compose import compose_embed_text, content_hash


def test_compose_all_fields():
    row = {"text": "А", "modern_text": "Б", "explanation": "Пояснення."}
    assert compose_embed_text(row) == "А\nБ\nПояснення."


def test_compose_skips_equal_modern_and_empty_explanation():
    row = {"text": "Сало", "modern_text": "Сало", "explanation": ""}
    assert compose_embed_text(row) == "Сало"


def test_compose_truncates_explanation():
    row = {"text": "Т", "modern_text": "Т", "explanation": "x" * 5000}
    out = compose_embed_text(row, max_expl=1000)
    assert out == "Т\n" + "x" * 1000


def test_hash_stable_and_changes():
    assert content_hash("a") == content_hash("a")
    assert content_hash("a") != content_hash("b")
    assert len(content_hash("a")) == 40
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_embed_compose.py -v` → FAIL (no module).

- [ ] **Step 3: Implement** — `embed/compose.py`:
```python
import hashlib


def compose_embed_text(row: dict, max_expl: int = 1000) -> str:
    text = (row.get("text") or "").strip()
    parts = [text]
    modern = (row.get("modern_text") or "").strip()
    if modern and modern != text:
        parts.append(modern)
    expl = (row.get("explanation") or "").strip()
    if expl:
        parts.append(expl[:max_expl])
    return "\n".join(parts)


def content_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()
```
Also create empty `embed/__init__.py`.

- [ ] **Step 4: Run, verify pass** — PASS (4 passed).

- [ ] **Step 5: Commit**
```bash
git add embed/__init__.py embed/compose.py tests/test_embed_compose.py
git commit -m "feat(embed): proverb embed-text composition + content hash"
```

---

### Task 2 [IMPL]: embed/manifest.py — manifest load/save/diff

**Files:** Create `embed/manifest.py`, `tests/test_embed_manifest.py`.

**Interfaces:**
- Produces:
  - `load_manifest(path: str) -> dict` — JSON `{id: hash}`; `{}` if the file is missing.
  - `save_manifest(path: str, mapping: dict) -> None` — write JSON (sorted keys, indent 2).
  - `diff(current: dict, previous: dict) -> dict` — returns `{"to_upsert": [...], "to_delete": [...]}`: `to_upsert` = ids in `current` whose hash is new or changed vs `previous` (sorted); `to_delete` = ids in `previous` absent from `current` (sorted).

- [ ] **Step 1: Write the failing test** — `tests/test_embed_manifest.py`:
```python
import json
from embed.manifest import load_manifest, save_manifest, diff


def test_load_missing_returns_empty(tmp_path):
    assert load_manifest(str(tmp_path / "nope.json")) == {}


def test_save_then_load_roundtrip(tmp_path):
    p = str(tmp_path / "m.json")
    save_manifest(p, {"p2": "h2", "p1": "h1"})
    assert load_manifest(p) == {"p1": "h1", "p2": "h2"}


def test_diff_detects_new_changed_removed_unchanged():
    current = {"p1": "h1", "p2": "H2new", "p3": "h3"}   # p1 same, p2 changed, p3 new
    previous = {"p1": "h1", "p2": "h2", "p9": "h9"}      # p9 removed
    d = diff(current, previous)
    assert d == {"to_upsert": ["p2", "p3"], "to_delete": ["p9"]}


def test_diff_empty_previous_upserts_all():
    assert diff({"p1": "h1"}, {}) == {"to_upsert": ["p1"], "to_delete": []}
```

- [ ] **Step 2: Run, verify fail** — FAIL.

- [ ] **Step 3: Implement** — `embed/manifest.py`:
```python
import json
import os


def load_manifest(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_manifest(path: str, mapping: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, sort_keys=True, indent=2)


def diff(current: dict, previous: dict) -> dict:
    to_upsert = sorted(k for k, v in current.items() if previous.get(k) != v)
    to_delete = sorted(k for k in previous if k not in current)
    return {"to_upsert": to_upsert, "to_delete": to_delete}
```

- [ ] **Step 4: Run, verify pass** — PASS.

- [ ] **Step 5: Commit**
```bash
git add embed/manifest.py tests/test_embed_manifest.py
git commit -m "feat(embed): incremental manifest (load/save/diff)"
```

---

### Task 3 [IMPL]: embed/run.py — build orchestrator + CLI wiring

**Files:** Create `embed/run.py`, `tests/test_embed_run.py`.

**Interfaces:**
- Consumes: `compose_embed_text`, `content_hash` (Task 1); `load_manifest`, `save_manifest`, `diff` (Task 2).
- Produces:
  - `build_index(corpus_path, manifest_path, *, embed_fn, upsert_fn, delete_fn, batch_size=100) -> dict` —
    loads `corpus.csv`; builds `current = {id: content_hash(compose_embed_text(row))}` and `texts = {id: embed_text}`; `d = diff(current, load_manifest(manifest_path))`; for each `batch_size` slice of `d["to_upsert"]`: `vecs = embed_fn([texts[id] for id in batch])` then `upsert_fn([{ "id": id, "values": v } for id, v in zip(batch, vecs)])`; if `d["to_delete"]`: `delete_fn(d["to_delete"])`; `save_manifest(manifest_path, current)`; return `{"upserted": len(to_upsert), "deleted": len(to_delete), "total": len(current)}`.
    Order: upsert all, then delete, then save manifest (so a mid-run crash re-tries on next run).
  - `main()` — CLI wiring (real `embed_fn` via Workers AI REST, `upsert_fn`/`delete_fn` via `wrangler`). Not unit-tested.

- [ ] **Step 1: Write the failing test** — `tests/test_embed_run.py`:
```python
import csv
from embed.run import build_index


def _write_corpus(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "text", "modern_text", "explanation"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_build_index_first_run_upserts_all(tmp_path):
    corpus = str(tmp_path / "c.csv"); manifest = str(tmp_path / "m.json")
    _write_corpus(corpus, [
        {"id": "p1", "text": "А", "modern_text": "А", "explanation": ""},
        {"id": "p2", "text": "Б", "modern_text": "В", "explanation": "по"},
    ])
    upserts, deletes = [], []
    stats = build_index(
        corpus, manifest,
        embed_fn=lambda texts: [[0.1, 0.2] for _ in texts],
        upsert_fn=lambda items: upserts.extend(items),
        delete_fn=lambda ids: deletes.extend(ids),
    )
    assert stats == {"upserted": 2, "deleted": 0, "total": 2}
    assert {u["id"] for u in upserts} == {"p1", "p2"}
    assert upserts[0]["values"] == [0.1, 0.2]


def test_build_index_second_run_only_delta(tmp_path):
    corpus = str(tmp_path / "c.csv"); manifest = str(tmp_path / "m.json")
    base = [{"id": "p1", "text": "А", "modern_text": "А", "explanation": ""},
            {"id": "p2", "text": "Б", "modern_text": "Б", "explanation": ""}]
    _write_corpus(corpus, base)
    build_index(corpus, manifest, embed_fn=lambda t: [[0.0] for _ in t],
                upsert_fn=lambda i: None, delete_fn=lambda i: None)
    # change p2, remove p1, add p3
    _write_corpus(corpus, [
        {"id": "p2", "text": "Б", "modern_text": "Б-нове", "explanation": ""},
        {"id": "p3", "text": "Г", "modern_text": "Г", "explanation": ""},
    ])
    upserts, deletes = [], []
    stats = build_index(corpus, manifest, embed_fn=lambda t: [[0.0] for _ in t],
                        upsert_fn=lambda i: upserts.extend(i), delete_fn=lambda i: deletes.extend(i))
    assert {u["id"] for u in upserts} == {"p2", "p3"}
    assert deletes == ["p1"]
    assert stats == {"upserted": 2, "deleted": 1, "total": 2}
```

- [ ] **Step 2: Run, verify fail** — FAIL.

- [ ] **Step 3: Implement** — `embed/run.py`:
```python
import csv
import os

from embed.compose import compose_embed_text, content_hash
from embed.manifest import load_manifest, save_manifest, diff


def build_index(corpus_path, manifest_path, *, embed_fn, upsert_fn, delete_fn, batch_size=100):
    with open(corpus_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    texts = {r["id"]: compose_embed_text(r) for r in rows}
    current = {rid: content_hash(t) for rid, t in texts.items()}
    d = diff(current, load_manifest(manifest_path))

    to_upsert = d["to_upsert"]
    for i in range(0, len(to_upsert), batch_size):
        batch = to_upsert[i:i + batch_size]
        vecs = embed_fn([texts[rid] for rid in batch])
        upsert_fn([{"id": rid, "values": v} for rid, v in zip(batch, vecs)])
    if d["to_delete"]:
        delete_fn(d["to_delete"])
    save_manifest(manifest_path, current)
    return {"upserted": len(to_upsert), "deleted": len(d["to_delete"]), "total": len(current)}


def _workers_ai_embed(texts):
    """Embed via the Workers AI REST API. Requires CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN."""
    import requests
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/baai/bge-m3"
    resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json={"text": texts}, timeout=120)
    resp.raise_for_status()
    return resp.json()["result"]["data"]


def _wrangler_upsert(items):
    """Write NDJSON and upsert via wrangler from app/."""
    import json
    import subprocess
    ndjson = "\n".join(json.dumps(it, ensure_ascii=False) for it in items)
    path = "/tmp/vectorize-upsert.ndjson"
    with open(path, "w", encoding="utf-8") as f:
        f.write(ndjson + "\n")
    subprocess.run(["npx", "wrangler", "vectorize", "insert", "proverbs-bge-m3", "--file", path],
                   cwd="app", check=True)


def _wrangler_delete(ids):
    import subprocess
    subprocess.run(["npx", "wrangler", "vectorize", "delete-vectors", "proverbs-bge-m3", "--ids", *ids],
                   cwd="app", check=True)


def main():
    stats = build_index(
        "corpus.csv", "embed/manifest.json",
        embed_fn=_workers_ai_embed, upsert_fn=_wrangler_upsert, delete_fn=_wrangler_delete,
    )
    print(f"embed: upserted={stats['upserted']} deleted={stats['deleted']} total={stats['total']}")


if __name__ == "__main__":
    main()
```
(`main()`/`_workers_ai_embed`/`_wrangler_*` are CLI wiring exercised by the controller in Task 7, not unit tests.)

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_embed_run.py -v` → PASS.

- [ ] **Step 5: Commit**
```bash
git add embed/run.py tests/test_embed_run.py
git commit -m "feat(embed): incremental build orchestrator + CLI wiring"
```

---

### Task 4 [IMPL]: app/src/shared/semantic.ts — pure mapping/filter

**Files:** Create `app/src/shared/semantic.ts`, `app/test/semantic.test.ts`.

**Interfaces:**
- Consumes: `Proverb` from `./corpus`.
- Produces:
  - `type Match = { id: string; score: number }`
  - `type Scored = Proverb & { score: number }`
  - `mapMatches(matches: Match[], byId: Map<string, Proverb>, opts: {category?: string; source?: string; minScore?: number; limit?: number; excludeId?: string}) -> {total: number; results: Scored[]}` — drop matches below `minScore` (default 0); map id→proverb (skip ids absent from `byId`); drop `excludeId`; apply `category` (in `category[]`) and `source` (in `sources[]`) filters; `total` = matched count pre-pagination; slice to `limit` (default 50, min 1, max 200).

- [ ] **Step 1: Write the failing test** — `app/test/semantic.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { mapMatches, type Match } from "../src/shared/semantic";
import { type Proverb } from "../src/shared/corpus";

const P = (id: string, category: string[], sources: string[]): Proverb =>
  ({ id, text: id, modern_text: id, category, sources, variant_group: "" });
const byId = new Map<string, Proverb>([
  ["p1", P("p1", ["fate_luck"], ["Franko1901"])],
  ["p2", P("p2", ["work_labor"], ["Bobkova"])],
  ["p3", P("p3", ["work_labor"], ["Franko1901"])],
]);
const matches: Match[] = [
  { id: "p1", score: 0.9 }, { id: "p2", score: 0.7 }, { id: "p3", score: 0.3 }, { id: "zz", score: 0.95 },
];

describe("mapMatches", () => {
  it("maps, skips unknown ids, preserves order + score", () => {
    const r = mapMatches(matches, byId, {});
    expect(r.results.map((x) => x.id)).toEqual(["p1", "p2", "p3"]); // zz dropped
    expect(r.results[0].score).toBe(0.9);
    expect(r.total).toBe(3);
  });
  it("applies minScore", () => {
    expect(mapMatches(matches, byId, { minScore: 0.5 }).results.map((x) => x.id)).toEqual(["p1", "p2"]);
  });
  it("applies category + source filters", () => {
    expect(mapMatches(matches, byId, { category: "work_labor" }).results.map((x) => x.id)).toEqual(["p2", "p3"]);
    expect(mapMatches(matches, byId, { source: "Franko1901" }).results.map((x) => x.id)).toEqual(["p1", "p3"]);
  });
  it("excludeId + limit", () => {
    expect(mapMatches(matches, byId, { excludeId: "p1", limit: 1 }).results.map((x) => x.id)).toEqual(["p2"]);
    expect(mapMatches(matches, byId, { excludeId: "p1" }).total).toBe(2);
  });
});
```

- [ ] **Step 2: Run, verify fail** — from `app/`: `npx vitest run test/semantic.test.ts` → FAIL.

- [ ] **Step 3: Implement** — `app/src/shared/semantic.ts`:
```typescript
import { type Proverb } from "./corpus";

export type Match = { id: string; score: number };
export type Scored = Proverb & { score: number };

export function mapMatches(
  matches: Match[],
  byId: Map<string, Proverb>,
  opts: { category?: string; source?: string; minScore?: number; limit?: number; excludeId?: string },
): { total: number; results: Scored[] } {
  const minScore = opts.minScore ?? 0;
  const limit = Math.min(Math.max(opts.limit ?? 50, 1), 200);
  const matched: Scored[] = [];
  for (const m of matches) {
    if (m.score < minScore) continue;
    if (m.id === opts.excludeId) continue;
    const p = byId.get(m.id);
    if (!p) continue;
    if (opts.category && !p.category.includes(opts.category)) continue;
    if (opts.source && !p.sources.includes(opts.source)) continue;
    matched.push({ ...p, score: m.score });
  }
  return { total: matched.length, results: matched.slice(0, limit) };
}
```

- [ ] **Step 4: Run, verify pass** — PASS.

- [ ] **Step 5: Commit**
```bash
git add app/src/shared/semantic.ts app/test/semantic.test.ts
git commit -m "feat(app): pure semantic match mapping/filter helper"
```

---

### Task 5 [IMPL]: Worker /api/semantic + /api/similar + bindings

**Files:** Modify `app/src/index.ts`, `app/wrangler.jsonc`; Create `app/test/semantic-api.test.ts`.

**Interfaces:**
- Consumes: `mapMatches`, `Match` (Task 4); existing in-memory corpus loader + `J()` helper in `index.ts`.
- Produces: two routes on the default Worker. `Env` gains `AI` and `VECTORIZE`.

- [ ] **Step 1: Add bindings to `app/wrangler.jsonc`** — add these top-level keys (alongside `assets`):
```jsonc
  "ai": { "binding": "AI" },
  "vectorize": [{ "binding": "VECTORIZE", "index_name": "proverbs-bge-m3" }],
```

- [ ] **Step 2: Write the failing test** — `app/test/semantic-api.test.ts` (injects a mock env combining the real ASSETS with fake AI + VECTORIZE; fixture ids `p1`,`p2` come from `test/fixtures-site/data/proverbs.json`):
```typescript
import { env, createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { describe, it, expect } from "vitest";
import worker from "../src/index";

const fakeAI = { run: async () => ({ shape: [1, 2], data: [[0.1, 0.2]] }) };
function envWith(vectorize: any) {
  return { ...env, AI: fakeAI, VECTORIZE: vectorize } as any;
}
async function call(path: string, vectorize: any) {
  const ctx = createExecutionContext();
  const res = await worker.fetch(new Request("https://x" + path), envWith(vectorize), ctx);
  await waitOnExecutionContext(ctx);
  return res;
}

describe("/api/semantic", () => {
  it("returns scored proverbs above cutoff", async () => {
    const vectorize = { query: async () => ({ matches: [{ id: "p1", score: 0.9 }, { id: "p2", score: 0.1 }] }) };
    const body = await (await call("/api/semantic?q=горе&minScore=0.5", vectorize)).json() as any;
    expect(body.total).toBe(1);
    expect(body.results[0].id).toBe("p1");
    expect(body.results[0].score).toBe(0.9);
  });
  it("400 on missing q", async () => {
    expect((await call("/api/semantic", { query: async () => ({ matches: [] }) })).status).toBe(400);
  });
});

describe("/api/similar/:id", () => {
  it("excludes the query id", async () => {
    const vectorize = {
      getByIds: async () => [{ id: "p1", values: [0.1, 0.2] }],
      query: async () => ({ matches: [{ id: "p1", score: 1.0 }, { id: "p2", score: 0.8 }] }),
    };
    const body = await (await call("/api/similar/p1", vectorize)).json() as any;
    expect(body.results.map((r: any) => r.id)).toEqual(["p2"]);
  });
  it("404 when id not indexed", async () => {
    const vectorize = { getByIds: async () => [] };
    expect((await call("/api/similar/zz", vectorize)).status).toBe(404);
  });
});
```

- [ ] **Step 3: Run, verify fail** — from `app/`: `npx vitest run test/semantic-api.test.ts` → FAIL.

- [ ] **Step 4: Implement** — in `app/src/index.ts`:
  - Add the import: `import { mapMatches, type Match } from "./shared/semantic";`
  - Extend the `Env` interface:
```typescript
interface Env {
  ASSETS: { fetch: (req: Request | string) => Promise<Response> };
  AI: { run: (model: string, inputs: { text: string[] }) => Promise<{ data: number[][] }> };
  VECTORIZE: {
    query: (vector: number[], opts: { topK: number }) => Promise<{ matches: Match[] }>;
    getByIds: (ids: string[]) => Promise<Array<{ id: string; values: number[] }>>;
  };
}
```
  - Add a module-scope constant near the top: `const SEMANTIC_MIN_SCORE = 0.4;`
  - Inside `fetch`, after the corpus is loaded (`const { proverbs, explanations, meta } = await load(env);`) and before the existing route checks, add a `byId` map once: reuse a helper. Add these route handlers among the `/api/*` checks:
```typescript
    if (path === "/api/semantic") {
      const q = (qp.get("q") ?? "").trim();
      if (!q) return J({ error: "missing q" }, 400);
      if (!env.AI || !env.VECTORIZE) return J({ error: "semantic search unavailable" }, 503);
      try {
        const { data } = await env.AI.run("@cf/baai/bge-m3", { text: [q] });
        const { matches } = await env.VECTORIZE.query(data[0], { topK: 100 });
        const byId = new Map(proverbs.map((p) => [p.id, p]));
        const minScore = qp.get("minScore") ? Number(qp.get("minScore")) : SEMANTIC_MIN_SCORE;
        return J(mapMatches(matches, byId, {
          category: qp.get("category") ?? undefined,
          source: qp.get("source") ?? undefined,
          minScore: Number.isFinite(minScore) ? minScore : SEMANTIC_MIN_SCORE,
          limit: qp.get("limit") ? Number(qp.get("limit")) : undefined,
        }));
      } catch {
        return J({ error: "semantic search failed" }, 502);
      }
    }
    const sim = path.match(/^\/api\/similar\/(.+)$/);
    if (sim) {
      if (!env.VECTORIZE) return J({ error: "semantic search unavailable" }, 503);
      const id = decodeURIComponent(sim[1]);
      try {
        const recs = await env.VECTORIZE.getByIds([id]);
        if (!recs.length) return J({ error: "not indexed" }, 404);
        const lim = qp.get("limit") ? Number(qp.get("limit")) : 6;
        const { matches } = await env.VECTORIZE.query(recs[0].values, { topK: Math.min((Number.isFinite(lim) ? lim : 6) + 1, 100) });
        const byId = new Map(proverbs.map((p) => [p.id, p]));
        return J(mapMatches(matches, byId, { excludeId: id, limit: Number.isFinite(lim) ? lim : 6 }));
      } catch {
        return J({ error: "similar lookup failed" }, 502);
      }
    }
```
  (Place these before the final `return J({ error: "unknown endpoint" }, 404);`. The existing `/api/proverb/:id` regex stays above or below — order is unambiguous since paths differ.)

- [ ] **Step 5: Run, verify pass** — from `app/`: `npx vitest run` → all green (corpus + api + semantic + semantic-api).

- [ ] **Step 6: Commit**
```bash
git add app/src/index.ts app/wrangler.jsonc app/test/semantic-api.test.ts
git commit -m "feat(app): /api/semantic + /api/similar (AI + Vectorize bindings)"
```

---

### Task 6 [IMPL]: Client — «за змістом» toggle + «Схожі прислів'я»

**Files:** Modify `app/src/client/main.ts`, `app/public/index.html`, `app/public/styles.css`.

**Interfaces:** Consumes the existing `/api/semantic` + `/api/similar/:id`. No exported API (browser entry point). Read `app/src/client/main.ts` first — integrate with the existing `boot/renderResults/openDetail` structure.

- [ ] **Step 1: HTML** — in `app/public/index.html`, inside `.search-wrap` (after the `#q` input, before `#count`), add the toggle:
```html
      <button id="semToggle" class="sem-toggle" type="button" role="switch" aria-checked="false" title="Пошук за змістом (потрібен інтернет)">за змістом</button>
```

- [ ] **Step 2: CSS** — append to `app/public/styles.css`:
```css
.sem-toggle { font-family: var(--sans); font-size: .76rem; letter-spacing: .02em; cursor: pointer;
  background: none; border: 1px solid var(--rule); color: var(--muted); border-radius: 999px;
  padding: .25rem .7rem; white-space: nowrap; transition: background .12s, color .12s, border-color .12s; }
.sem-toggle[aria-checked="true"] { background: var(--wine); color: #fff; border-color: var(--wine); }
.sem-toggle:disabled { opacity: .4; cursor: not-allowed; }
.entry-score, .sim-score { font-family: var(--mono); font-size: .68rem; color: var(--faint); }
.detail-similar { margin: 1.1rem 0 0; padding-top: 1.1rem; border-top: 1px solid var(--rule); }
.detail-similar h4 { font-size: .68rem; letter-spacing: .14em; text-transform: uppercase; color: var(--faint); margin: 0 0 .5rem; }
.detail-similar li { font-family: var(--serif); color: var(--ink); margin: .35rem 0; line-height: 1.35; cursor: pointer; }
.detail-similar li:hover { color: var(--wine); }
.sem-hint { font-family: var(--sans); font-size: .72rem; color: var(--faint); margin-top: .4rem; }
```

- [ ] **Step 3: Wire the toggle + semantic search** — in `app/src/client/main.ts`:
  - Add module state near the other `let` declarations: `let semanticMode = false;`
  - In `boot()`, after the `#q` input listener, add:
```typescript
  const semBtn = $("semToggle") as HTMLButtonElement;
  const syncOnline = () => { if (!navigator.onLine) { semanticMode = false; semBtn.setAttribute("aria-checked", "false"); } semBtn.disabled = !navigator.onLine; };
  syncOnline();
  window.addEventListener("online", syncOnline);
  window.addEventListener("offline", syncOnline);
  semBtn.addEventListener("click", () => {
    if (semBtn.disabled) return;
    semanticMode = !semanticMode;
    semBtn.setAttribute("aria-checked", String(semanticMode));
    renderResults();
  });
```
  - Replace the body of `renderResults()` so it branches to semantic when the toggle is on and there's a query. Keep the existing lexical/landing logic for the non-semantic path. New `renderResults`:
```typescript
async function renderResults() {
  const q = ($("q") as HTMLInputElement).value.trim();

  if (semanticMode && q) {
    $("count").textContent = "Пошук за змістом…";
    try {
      const url = `/api/semantic?q=${encodeURIComponent(q)}` +
        (activeCat ? `&category=${activeCat}` : "") + (activeSource ? `&source=${activeSource}` : "") + "&limit=80";
      const data = await fetch(url).then((r) => r.json());
      $("count").textContent = `За змістом: ${fmt(data.total)}`;
      paintEntries(data.results, "За змістом", true);
    } catch {
      $("count").textContent = "";
      $("results").innerHTML = `<p class="empty">Семантичний пошук недоступний. Спробуйте звичайний пошук.</p>`;
    }
    return;
  }

  const filtering = !!(q || activeCat || activeSource);
  let head: string, count: string, results: Proverb[];
  if (!filtering) {
    results = landingSample; head = "Навмання з корпусу"; count = `${fmt(meta.count)} всього`;
  } else {
    let pool = all;
    if (q) {
      const ids = new Set(mini.search(q, { prefix: true, fuzzy: 0.2 }).map((r) => r.id as string));
      pool = all.filter((p) => ids.has(p.id));
    }
    const r = searchProverbs(pool, { category: activeCat || undefined, source: activeSource || undefined, limit: 80 });
    results = r.results; head = "Результати"; count = `Знайдено ${fmt(r.total)}`;
  }
  $("count").textContent = count;
  paintEntries(results, head, false);
}

function paintEntries(results: Array<Proverb & { score?: number }>, head: string, showScore: boolean) {
  if (!results.length) {
    $("results").innerHTML = `<p class="empty">Нічого не знайдено. Спробуйте інше слово або зніміть фільтри.</p>`;
    return;
  }
  $("results").innerHTML =
    `<p class="results-head">${head}</p>` +
    results.map((p) =>
      `<article class="entry" data-id="${p.id}">
        <div class="entry-cat">№&nbsp;${esc(p.id.replace(/^p0*/, ""))}${showScore && p.score !== undefined ? `<br><span class="entry-score">${p.score.toFixed(2)}</span>` : ""}</div>
        <div>
          <div class="entry-text">${esc(p.text)}</div>
          ${differs(p) ? `<div class="entry-modern">${esc(p.modern_text)}</div>` : ""}
          <div class="entry-tags">
            ${p.category.map((c) => `<span class="tag">${esc(catLabel(c))}</span>`).join("")}
            <span class="tag-src">${esc(p.sources.map(srcLabel).join(" · "))}</span>
          </div>
        </div>
      </article>`).join("");
  for (const el of Array.from(document.querySelectorAll<HTMLElement>(".entry"))) {
    el.addEventListener("click", () => {
      const p = all.find((x) => x.id === el.dataset.id);
      if (p) openDetail(p);
    });
  }
}
```
  (The existing `renderResults` body moves wholesale into the non-semantic branch above; `paintEntries` replaces the old inline entry-render so both paths share it. Update the debounced listener — `$("q").addEventListener("input", debounce(renderResults, 180))` already calls `renderResults`, now async; that's fine.)

  - In `openDetail(p)`, before `dlg.showModal();`, append a placeholder and lazy-load similar (only when online):
```typescript
  if (navigator.onLine) {
    fetch(`/api/similar/${encodeURIComponent(p.id)}?limit=6`).then((r) => r.json()).then((data) => {
      if (!data.results || !data.results.length) return;
      const form = dlg.querySelector(".detail-inner");
      if (!form) return;
      const sec = document.createElement("div");
      sec.className = "detail-similar";
      sec.innerHTML = `<h4>Схожі прислів'я</h4><ul>${data.results.map((s: Proverb) => `<li data-id="${s.id}">${esc(s.text)}</li>`).join("")}</ul>`;
      form.insertBefore(sec, form.querySelector(".detail-close"));
      for (const li of Array.from(sec.querySelectorAll<HTMLElement>("li"))) {
        li.addEventListener("click", () => { const sp = all.find((x) => x.id === li.dataset.id); if (sp) { dlg.close(); openDetail(sp); } });
      }
    }).catch(() => {});
  }
```

- [ ] **Step 4: Build, verify compiles** — from `app/`: `node build.mjs` → `Built public/app.js`, no esbuild errors.

- [ ] **Step 5: Commit**
```bash
git add app/src/client/main.ts app/public/index.html app/public/styles.css
git commit -m "feat(app): «за змістом» semantic toggle + «Схожі прислів'я» detail section"
```

---

### Task 7 [CONTROLLER-RUN]: Index setup, embed run, preview smoke, deploy

Controller-run. **Requires the user to enable the Workers Paid plan first** (billing — user action).

- [ ] **Step 1: Confirm Workers Paid is enabled** by the user (Vectorize needs it for >5M stored dims). Verify `wrangler whoami`.
- [ ] **Step 2: Create the index** — `cd app && npx wrangler vectorize create proverbs-bge-m3 --dimensions=1024 --metric=cosine`. Confirm it lists in `npx wrangler vectorize list`.
- [ ] **Step 3: Run the embed pipeline** from repo root — `CLOUDFLARE_ACCOUNT_ID=<acct> .venv/bin/python -m embed.run` (token already in env). Confirm `embed/manifest.json` written with 40,444 ids and the upsert count. Commit `embed/manifest.json`.
- [ ] **Step 4: Preview deploy + smoke** — `cd app && node build.mjs && npx wrangler versions upload`; on the preview URL curl `/api/semantic?q=<a meaning phrase>` and `/api/similar/p000001`, eyeball relevance, **tune `SEMANTIC_MIN_SCORE`** if results are too loose/empty (edit, rebuild, re-upload). Check the «за змістом» toggle + similar section in the browser; confirm offline disables the toggle.
- [ ] **Step 5: Deploy** (confirm with user) — `npx wrangler deploy`. Smoke the production URL.
- [ ] **Step 6: README + finish** — document the embed pipeline (`python -m embed.run`), the new endpoints, and the Workers Paid requirement; commit. Controller merges `feat/semantic-search` → main and pushes both remotes via finishing-a-development-branch.

---

## Self-Review

**1. Spec coverage:**
- §2 embeddings (bge-m3, text+modern+explanation≤1000) → Tasks 1, 3. ✓
- §3 incremental pipeline (compose/hash/manifest/diff/run, id-only metadata) → Tasks 1–3. ✓
- §4 API (`/api/semantic` topK→filter→cutoff; `/api/similar` getByIds→query→exclude-self; 400/404/503/502) → Task 5; pure mapping → Task 4. ✓
- §5 client («за змістом» toggle, «Схожі прислів'я», offline degradation) → Task 6. ✓
- §7 ops (Workers Paid by user, index creation, bindings, deploy) → Task 5 (bindings) + Task 7. ✓
- §8 testing (pytest compose/manifest/run; vitest semantic + semantic-api over mocked bindings; preview smoke) → Tasks 1–5, 7. ✓
- §9 cost / §10 risks (score cutoff tunable; topK capped) → Task 7 Step 4; topK=100 correction noted in Global Constraints. ✓

**2. Placeholder scan:** All code steps contain complete code. The score cutoff is a concrete constant (`0.4`) tuned in Task 7 Step 4 (a real action, not a placeholder). `<acct>` in Task 7 is an env value the controller supplies. No TBD/"handle errors" steps.

**3. Type consistency:** `Match {id,score}` defined in Task 4, used identically in Task 5's `Env.VECTORIZE` + tests. `mapMatches` signature identical between Task 4 (def), Task 5 (use), and tests. `Proverb` shape unchanged from prior tasks. Embed-text composition identical in Task 1 (def) and Task 3 (use via `compose_embed_text`). Index name `proverbs-bge-m3` consistent across run.py, wrangler.jsonc, and Task 7. `env.AI.run` return `{data}` and `VECTORIZE.query` return `{matches}` consistent between Task 5 code, its `Env` types, and the test mocks.

**Spec/reality correction:** spec §4 said topK=200; Vectorize caps topK at 100 → plan uses 100 (Global Constraints + Task 5). Retrieve-then-filter intent preserved; narrow-filter thinness noted as an accepted v1 limitation (spec §10).

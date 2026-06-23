# Ukrainian Proverbs Corpus — Productization 4a+4b — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship multi-format exports + a Cloudflare Worker serving a searchable, offline PWA and a REST API over the 40,444-proverb corpus, mirroring the ua-bez-tabu stack.

**Architecture:** Python `build_data.py` emits a compact `proverbs.json` (+ lazy `explanations.json`, `meta.json`, `corpus.xml`). A TypeScript Worker serves `/api/*` (loading `proverbs.json` from the ASSETS binding into module scope — NOT bundled) and static assets; the PWA does client-side MiniSearch with a service worker for offline. Shared search/filter logic in `src/shared/corpus.ts` is used by both Worker and client.

**Tech Stack:** Python 3 (pytest) for exports; TypeScript + esbuild + Cloudflare Workers (wrangler) + MiniSearch + vitest (@cloudflare/vitest-pool-workers).

**Spec:** `docs/superpowers/specs/2026-06-23-ukr-proverbs-productize.md`
**Reference:** the working app at `/home/dmytro/github/ua-bez-tabu/app/` (read for wrangler/esbuild/sw idioms; do NOT copy its data model).

## Global Constraints

- App lives under `app/` in this repo. Node ESM (`"type":"module"`). Python uses `.venv/bin/python`.
- `proverbs.json` compact record shape EXACTLY: `{id, text, modern_text, category[], sources[], variant_group}` (category/sources are arrays; `variant_group` "" if none). No explanations in it.
- The Worker **fetches** `proverbs.json` / `explanations.json` from the `ASSETS` binding at runtime and caches in module scope — it must NOT `import` them (5–7 MB would exceed Worker size limits).
- API endpoints: `/api/search`, `/api/proverb/:id`, `/api/random`, `/api/categories`, `/api/meta`; JSON; permissive CORS (`Access-Control-Allow-Origin: *`); search `limit` default 50, max 200.
- Search matches `text` + `modern_text`; `category`/`source` are exact filters. 27 theme keys from `enrich/taxonomy.csv`; 4 sources (Franko1901, Mlodzynskyi2009, Ilkevich1841, Bobkova).
- Deploy (`wrangler deploy`) is an outward action — controller confirms with the user before running.
- Commits use local identity `MurzikVasilyevich <vasilyevichmurzik@gmail.com>`; append the session footer. Branch `feat/productize`.
- Push: origin needs `gh auth switch --user MurzikVasilyevich` (HTTPS); dmytro is SSH.
- **Task types:** `[IMPL]` = TDD implementer. `[CONTROLLER-RUN]` = controller (data gen, wrangler dev/deploy).

---

### Task 1 [IMPL]: app/build_data.py — exports

**Files:**
- Create: `app/build_data.py`
- Create: `tests/test_build_data.py`
- Create: `tests/fixtures/productize_corpus.csv`

**Interfaces:**
- Produces: `build(corpus_path, taxonomy_path, sources_path, out_dir, xml_path) -> dict` (returns stats). Writes `{out_dir}/proverbs.json`, `{out_dir}/explanations.json`, `{out_dir}/meta.json`, and `xml_path`.
  - `proverbs.json`: list of `{id, text, modern_text, category (split ";"→list, [] if empty), sources (split ";"→list), variant_group}`, sorted by id.
  - `explanations.json`: `{id: explanation}` only for rows with non-empty explanation.
  - `meta.json`: `{count, taxonomy: {key: ukrainian_label}, sources: [{key,title,year,author}], with_explanation, per_category: {key:count}}`.
  - `corpus.xml`: `<corpus><proverb id=…><text/><modern_text/><category/>…</proverb>…</corpus>`, UTF-8.

- [ ] **Step 1: Fixture** — `tests/fixtures/productize_corpus.csv` (header = the 10 corpus columns):
```csv
id,text,normalized_text,modern_text,keyword,explanation,category,sources,source_refs,variant_group
p000001,Аби болото а жаби будуть,аби болото а жаби будуть,Аби болото а жаби будуть,болото,Сатира.,food_hunger;animals,Franko1901;Bobkova,Б;5,v0001
p000002,Як є мине ся,як є мине ся,Як є мине ся,,,fate_luck,Mlodzynskyi2009,2,
```

- [ ] **Step 2: Write the failing test** — `tests/test_build_data.py`:
```python
import json, csv, os, xml.etree.ElementTree as ET
from app.build_data import build

TAX = "enrich/taxonomy.csv"
SRC = "sources.csv"


def test_build_outputs(tmp_path):
    out = tmp_path / "data"; xml = tmp_path / "corpus.xml"
    stats = build("tests/fixtures/productize_corpus.csv", TAX, SRC, str(out), str(xml))
    prov = json.loads((out / "proverbs.json").read_text(encoding="utf-8"))
    assert stats["count"] == 2
    assert prov[0]["id"] == "p000001"
    assert prov[0]["category"] == ["food_hunger", "animals"]
    assert prov[0]["sources"] == ["Franko1901", "Bobkova"]
    assert "modern_text" in prov[0] and "explanation" not in prov[0]
    expl = json.loads((out / "explanations.json").read_text(encoding="utf-8"))
    assert expl == {"p000001": "Сатира."}                # only non-empty
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["count"] == 2
    assert meta["taxonomy"]["food_hunger"] == "Їжа і голод"
    assert any(s["key"] == "Bobkova" for s in meta["sources"])
    root = ET.fromstring(xml.read_text(encoding="utf-8"))
    assert root.tag == "corpus" and len(root.findall("proverb")) == 2
```

- [ ] **Step 3: Run test, verify fail** — `.venv/bin/python -m pytest tests/test_build_data.py -v` → FAIL (ModuleNotFoundError).

- [ ] **Step 4: Implement** — `app/build_data.py`:
```python
from __future__ import annotations

import csv
import json
import os
from collections import Counter
from xml.sax.saxutils import escape


def _load_taxonomy(path):
    with open(path, encoding="utf-8") as f:
        return {r["key"]: r["ukrainian_label"] for r in csv.DictReader(f)}


def _load_sources(path):
    with open(path, encoding="utf-8") as f:
        out = []
        for r in csv.DictReader(f):
            r = {k.lstrip("﻿"): v for k, v in r.items()}
            out.append({"key": r.get("Citationkey", ""), "title": r.get("Title", ""),
                        "year": r.get("Year", ""), "author": r.get("Author", "")})
    return out


def build(corpus_path, taxonomy_path, sources_path, out_dir, xml_path):
    os.makedirs(out_dir, exist_ok=True)
    with open(corpus_path, encoding="utf-8") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: r["id"])

    proverbs, explanations = [], {}
    per_cat = Counter()
    for r in rows:
        cats = [c for c in r["category"].split(";") if c]
        proverbs.append({
            "id": r["id"], "text": r["text"], "modern_text": r["modern_text"],
            "category": cats, "sources": [s for s in r["sources"].split(";") if s],
            "variant_group": r["variant_group"],
        })
        for c in cats:
            per_cat[c] += 1
        if r["explanation"].strip():
            explanations[r["id"]] = r["explanation"]

    with open(os.path.join(out_dir, "proverbs.json"), "w", encoding="utf-8") as f:
        json.dump(proverbs, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "explanations.json"), "w", encoding="utf-8") as f:
        json.dump(explanations, f, ensure_ascii=False, separators=(",", ":"))

    meta = {
        "count": len(proverbs),
        "with_explanation": len(explanations),
        "taxonomy": _load_taxonomy(taxonomy_path),
        "sources": _load_sources(sources_path),
        "per_category": dict(per_cat.most_common()),
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<corpus>\n')
        for p in proverbs:
            f.write(f'  <proverb id="{p["id"]}">')
            f.write(f'<text>{escape(p["text"])}</text>')
            f.write(f'<modern_text>{escape(p["modern_text"])}</modern_text>')
            f.write(f'<category>{escape(";".join(p["category"]))}</category>')
            f.write(f'<sources>{escape(";".join(p["sources"]))}</sources>')
            f.write("</proverb>\n")
        f.write("</corpus>\n")
    return meta


if __name__ == "__main__":
    import sys
    # CLI: build_data.py <corpus.csv> <taxonomy.csv> <sources.csv> <out_dir> <xml_path>
    print(build(*sys.argv[1:6]))
```
(The `__main__` shim lets the controller invoke it as `python app/build_data.py corpus.csv enrich/taxonomy.csv sources.csv app/public/data corpus.xml` in Task 6.)

- [ ] **Step 5: Run test, verify pass** — PASS (1 passed).

- [ ] **Step 6: Commit**
```bash
git add app/build_data.py tests/test_build_data.py tests/fixtures/productize_corpus.csv
git commit -m "feat(app): corpus exports (compact json + explanations + meta + xml)"
```

---

### Task 2 [IMPL]: app scaffold (config + deps)

**Files:** Create `app/package.json`, `app/wrangler.jsonc`, `app/tsconfig.json`, `app/tsconfig.worker.json`, `app/build.mjs`, `app/.gitignore`.

**Interfaces:** Produces the build/deploy/test toolchain. `npm run build` = generate data (Task 6 wires the real corpus) + esbuild client; `wrangler dev`/`deploy`; `vitest run`.

- [ ] **Step 1:** `app/package.json`:
```json
{
  "name": "ukr-proverbs-corpus-app",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "sync-data": ".venv/bin/python build_data.py ../corpus.csv ../enrich/taxonomy.csv ../sources.csv public/data ../corpus.xml",
    "build": "node build.mjs",
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "test": "vitest run"
  },
  "dependencies": { "minisearch": "^7.1.0" },
  "devDependencies": {
    "@cloudflare/vitest-pool-workers": "^0.9.6",
    "esbuild": "^0.25.10",
    "typescript": "^5.9.3",
    "vitest": "~3.2.4",
    "wrangler": "^4.103.0"
  }
}
```
(Note: `sync-data` here is documentation; the real data is generated by the controller in Task 6 via `build_data.py` invoked with repo-root paths. `build.mjs` only bundles the client.)

- [ ] **Step 2:** `app/wrangler.jsonc`:
```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "ukr-proverbs-corpus",
  "main": "src/index.ts",
  "compatibility_date": "2025-10-11",
  "assets": {
    "directory": "./public",
    "binding": "ASSETS",
    "not_found_handling": "single-page-application",
    "run_worker_first": ["/api/*"]
  },
  "observability": { "enabled": true }
}
```

- [ ] **Step 3:** `app/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "es2022", "module": "es2022", "moduleResolution": "bundler",
    "lib": ["es2022", "dom"], "strict": true, "skipLibCheck": true,
    "types": ["@cloudflare/workers-types"], "noEmit": true, "esModuleInterop": true
  },
  "include": ["src/**/*.ts", "test/**/*.ts"]
}
```
`app/tsconfig.worker.json`:
```json
{ "extends": "./tsconfig.json", "include": ["src/index.ts", "src/shared/**/*.ts"] }
```

- [ ] **Step 4:** `app/build.mjs`:
```javascript
import { build } from "esbuild";
import { mkdir } from "node:fs/promises";

await mkdir("public/data", { recursive: true });
await build({
  entryPoints: ["src/client/main.ts"],
  bundle: true, minify: true, sourcemap: true,
  format: "esm", target: ["es2022"],
  outfile: "public/app.js",
});
console.log("Built public/app.js");
```

- [ ] **Step 5:** `app/.gitignore`:
```
node_modules/
.wrangler/
public/app.js
public/app.js.map
```

- [ ] **Step 6: Install + sanity** — from `app/`: `npm install` (network). Confirm `npx tsc -p tsconfig.json --noEmit` runs (no source yet → no errors; if it complains about no inputs, that's fine). Commit.
```bash
git add app/package.json app/wrangler.jsonc app/tsconfig.json app/tsconfig.worker.json app/build.mjs app/.gitignore app/package-lock.json
git commit -m "feat(app): Cloudflare Worker scaffold (wrangler, esbuild, vitest)"
```

---

### Task 3 [IMPL]: app/src/shared/corpus.ts — search/filter/random

**Files:** Create `app/src/shared/corpus.ts`, `app/test/corpus.test.ts`.

**Interfaces:**
- Produces:
  - `type Proverb = { id: string; text: string; modern_text: string; category: string[]; sources: string[]; variant_group: string }`
  - `searchProverbs(all: Proverb[], opts: {q?: string; category?: string; source?: string; limit?: number; offset?: number}) -> {total: number; results: Proverb[]}` — case-insensitive substring of `q` over `text`+`modern_text`; exact `category` (in `category[]`) and `source` (in `sources[]`) filters; pagination (limit default 50, max 200, offset default 0). `total` is the count before pagination.
  - `randomProverb(all: Proverb[], opts: {category?: string; source?: string}, rnd?: () => number) -> Proverb | null` — random match honoring filters; `rnd` injectable for tests (default `Math.random`).

- [ ] **Step 1: Write the failing test** — `app/test/corpus.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { searchProverbs, randomProverb, type Proverb } from "../src/shared/corpus";

const DATA: Proverb[] = [
  { id: "p1", text: "Горе море", modern_text: "Горе море", category: ["fate_luck"], sources: ["Franko1901"], variant_group: "" },
  { id: "p2", text: "Робота кипить", modern_text: "Робота кипить", category: ["work_labor"], sources: ["Bobkova"], variant_group: "" },
  { id: "p3", text: "Робота і горе", modern_text: "Робота і горе", category: ["work_labor", "fate_luck"], sources: ["Bobkova"], variant_group: "" },
];

describe("searchProverbs", () => {
  it("substring over text", () => {
    const r = searchProverbs(DATA, { q: "робота" });
    expect(r.total).toBe(2);
    expect(r.results.map((p) => p.id).sort()).toEqual(["p2", "p3"]);
  });
  it("category + source filters", () => {
    expect(searchProverbs(DATA, { category: "fate_luck" }).total).toBe(2);
    expect(searchProverbs(DATA, { source: "Bobkova" }).total).toBe(2);
    expect(searchProverbs(DATA, { q: "горе", category: "work_labor" }).total).toBe(1);
  });
  it("pagination + limit cap", () => {
    const r = searchProverbs(DATA, { limit: 1, offset: 1 });
    expect(r.total).toBe(3);
    expect(r.results.length).toBe(1);
    expect(searchProverbs(DATA, { limit: 9999 }).results.length).toBe(3); // capped, only 3 exist
  });
});

describe("randomProverb", () => {
  it("honors filter and rnd", () => {
    const p = randomProverb(DATA, { source: "Bobkova" }, () => 0);
    expect(p?.sources).toContain("Bobkova");
    expect(randomProverb([], {})).toBeNull();
  });
});
```

- [ ] **Step 2: Run test, verify fail** — from `app/`: `npx vitest run test/corpus.test.ts` → FAIL (module not found).

- [ ] **Step 3: Implement** — `app/src/shared/corpus.ts`:
```typescript
export type Proverb = {
  id: string;
  text: string;
  modern_text: string;
  category: string[];
  sources: string[];
  variant_group: string;
};

export type SearchOpts = {
  q?: string; category?: string; source?: string; limit?: number; offset?: number;
};

export function searchProverbs(all: Proverb[], opts: SearchOpts): { total: number; results: Proverb[] } {
  const q = (opts.q ?? "").trim().toLowerCase();
  const limit = Math.min(Math.max(opts.limit ?? 50, 1), 200);
  const offset = Math.max(opts.offset ?? 0, 0);
  const matched = all.filter((p) => {
    if (q && !(p.text.toLowerCase().includes(q) || p.modern_text.toLowerCase().includes(q))) return false;
    if (opts.category && !p.category.includes(opts.category)) return false;
    if (opts.source && !p.sources.includes(opts.source)) return false;
    return true;
  });
  return { total: matched.length, results: matched.slice(offset, offset + limit) };
}

export function randomProverb(
  all: Proverb[],
  opts: { category?: string; source?: string },
  rnd: () => number = Math.random,
): Proverb | null {
  const pool = searchProverbs(all, { category: opts.category, source: opts.source, limit: 200000 }).results;
  if (pool.length === 0) return null;
  return pool[Math.floor(rnd() * pool.length)];
}
```

- [ ] **Step 4: Run test, verify pass** — `npx vitest run test/corpus.test.ts` → PASS.

- [ ] **Step 5: Commit**
```bash
git add app/src/shared/corpus.ts app/test/corpus.test.ts
git commit -m "feat(app): shared search/filter/random over proverbs"
```

---

### Task 4 [IMPL]: app/src/index.ts — Worker REST API

**Files:** Create `app/src/index.ts`, `app/test/api.test.ts`, `app/test/fixtures/proverbs.json`, `app/test/fixtures/explanations.json`, `app/test/fixtures/meta.json`, `app/vitest.config.ts`.

**Interfaces:**
- Consumes: `searchProverbs`, `randomProverb`, `Proverb` from `./shared/corpus`.
- Produces: a Worker `default { fetch(request, env) }` where `env.ASSETS` is the asset binding. Loads `/data/proverbs.json`, `/data/explanations.json`, `/data/meta.json` via `env.ASSETS.fetch` once, cached in module scope. Routes:
  - `/api/search` → `searchProverbs` over query params → `{total, results}`.
  - `/api/proverb/:id` → proverb + `explanation` (from explanations map) or 404.
  - `/api/random` → `{...proverb}` or 404 if none.
  - `/api/categories` → `meta.taxonomy` merged with `meta.per_category` counts.
  - `/api/meta` → meta.json.
  - other `/api/*` → 404 `{error}`. All responses: `content-type: application/json`, `Access-Control-Allow-Origin: *`.

- [ ] **Step 1: Fixtures** — `app/test/fixtures/proverbs.json`:
```json
[{"id":"p1","text":"Горе море","modern_text":"Горе море","category":["fate_luck"],"sources":["Franko1901"],"variant_group":""},
 {"id":"p2","text":"Робота кипить","modern_text":"Робота кипить","category":["work_labor"],"sources":["Bobkova"],"variant_group":""}]
```
`app/test/fixtures/explanations.json`: `{"p1":"Про горе."}`
`app/test/fixtures/meta.json`: `{"count":2,"taxonomy":{"fate_luck":"Доля і щастя","work_labor":"Праця і ремесло"},"sources":[],"per_category":{"work_labor":1,"fate_luck":1}}`

- [ ] **Step 2:** `app/vitest.config.ts`:
```typescript
import { defineWorkersConfig } from "@cloudflare/vitest-pool-workers/config";

export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: {
        main: "./src/index.ts",
        miniflare: {
          compatibilityDate: "2025-10-11",
          assets: { directory: "./test/fixtures-site" },
        },
      },
    },
  },
});
```
Then create `app/test/fixtures-site/data/` and copy the three fixture JSONs into it (so `env.ASSETS.fetch('/data/...')` resolves in tests):
```bash
mkdir -p app/test/fixtures-site/data
cp app/test/fixtures/proverbs.json app/test/fixtures/explanations.json app/test/fixtures/meta.json app/test/fixtures-site/data/
```

- [ ] **Step 3: Write the failing test** — `app/test/api.test.ts`:
```typescript
import { env, createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { describe, it, expect } from "vitest";
import worker from "../src/index";

async function call(path: string) {
  const ctx = createExecutionContext();
  const res = await worker.fetch(new Request("https://x" + path), env as any, ctx);
  await waitOnExecutionContext(ctx);
  return res;
}

describe("API", () => {
  it("search by q", async () => {
    const res = await call("/api/search?q=робота");
    expect(res.headers.get("access-control-allow-origin")).toBe("*");
    const body = await res.json() as any;
    expect(body.total).toBe(1);
    expect(body.results[0].id).toBe("p2");
  });
  it("proverb by id includes explanation", async () => {
    const body = await (await call("/api/proverb/p1")).json() as any;
    expect(body.explanation).toBe("Про горе.");
  });
  it("404 on unknown id and unknown api route", async () => {
    expect((await call("/api/proverb/zzz")).status).toBe(404);
    expect((await call("/api/nope")).status).toBe(404);
  });
  it("categories with counts", async () => {
    const body = await (await call("/api/categories")).json() as any;
    expect(body.find((c: any) => c.key === "work_labor").count).toBe(1);
  });
});
```

- [ ] **Step 4: Run test, verify fail** — from `app/`: `npx vitest run test/api.test.ts` → FAIL (no `src/index.ts`).

- [ ] **Step 5: Implement** — `app/src/index.ts`:
```typescript
import { searchProverbs, randomProverb, type Proverb } from "./shared/corpus";

interface Env { ASSETS: { fetch: (req: Request | string) => Promise<Response> } }

let cache: Promise<{ proverbs: Proverb[]; explanations: Record<string, string>; meta: any }> | null = null;

function load(env: Env) {
  if (!cache) {
    cache = (async () => {
      const get = async (p: string) => (await env.ASSETS.fetch("https://assets" + p)).json();
      const [proverbs, explanations, meta] = await Promise.all([
        get("/data/proverbs.json") as Promise<Proverb[]>,
        get("/data/explanations.json") as Promise<Record<string, string>>,
        get("/data/meta.json") as Promise<any>,
      ]);
      return { proverbs, explanations, meta };
    })();
  }
  return cache;
}

const J = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "access-control-allow-origin": "*" },
  });

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    if (!path.startsWith("/api/")) return env.ASSETS.fetch(request);
    const { proverbs, explanations, meta } = await load(env);
    const qp = url.searchParams;

    if (path === "/api/search") {
      return J(searchProverbs(proverbs, {
        q: qp.get("q") ?? undefined, category: qp.get("category") ?? undefined,
        source: qp.get("source") ?? undefined,
        limit: qp.get("limit") ? Number(qp.get("limit")) : undefined,
        offset: qp.get("offset") ? Number(qp.get("offset")) : undefined,
      }));
    }
    if (path === "/api/random") {
      const p = randomProverb(proverbs, { category: qp.get("category") ?? undefined, source: qp.get("source") ?? undefined });
      return p ? J(p) : J({ error: "no match" }, 404);
    }
    if (path === "/api/categories") {
      const counts = meta.per_category ?? {};
      return J(Object.entries(meta.taxonomy as Record<string, string>).map(([key, label]) => ({ key, label, count: counts[key] ?? 0 })));
    }
    if (path === "/api/meta") return J(meta);
    const m = path.match(/^\/api\/proverb\/(.+)$/);
    if (m) {
      const p = proverbs.find((x) => x.id === decodeURIComponent(m[1]));
      return p ? J({ ...p, explanation: explanations[p.id] ?? null }) : J({ error: "not found" }, 404);
    }
    return J({ error: "unknown endpoint" }, 404);
  },
};
```

- [ ] **Step 6: Run test, verify pass** — `npx vitest run` → PASS (corpus + api).

- [ ] **Step 7: Commit**
```bash
git add app/src/index.ts app/test/api.test.ts app/test/fixtures app/test/fixtures-site app/vitest.config.ts
git commit -m "feat(app): Worker REST API over ASSETS-loaded corpus"
```

---

### Task 5 [IMPL]: PWA client (UI, offline, installable)

**Files:** Create `app/public/index.html`, `app/public/styles.css`, `app/public/manifest.webmanifest`, `app/public/icons/icon.svg`, `app/public/sw.js`, `app/src/client/main.ts`.

**Interfaces:** Consumes the static `/data/proverbs.json`, `/data/meta.json`, `/data/explanations.json` and (optionally) the `/api/*` endpoints. The client builds a MiniSearch index over `proverbs.json`. No exported API (browser entry point).

- [ ] **Step 1:** `app/public/index.html` (app shell; `app.js` is the esbuild bundle):
```html
<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Українські прислів'я та приказки</title>
  <link rel="manifest" href="/manifest.webmanifest" />
  <link rel="stylesheet" href="/styles.css" />
</head>
<body>
  <header>
    <h1>Українські прислів'я та приказки</h1>
    <input id="q" type="search" placeholder="Пошук…" autocomplete="off" />
    <div id="filters"></div>
    <button id="random">Випадкове</button>
    <p id="count"></p>
  </header>
  <main id="results"></main>
  <dialog id="detail"></dialog>
  <script type="module" src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2:** `app/public/styles.css` (minimal, responsive — Ukrainian-friendly):
```css
:root { font-family: system-ui, sans-serif; }
body { margin: 0; color: #1a1a1a; }
header { position: sticky; top: 0; background: #fff; padding: 1rem; border-bottom: 1px solid #ddd; }
h1 { font-size: 1.2rem; margin: 0 0 .5rem; }
#q { width: 100%; padding: .6rem; font-size: 1rem; box-sizing: border-box; }
#filters { display: flex; flex-wrap: wrap; gap: .3rem; margin: .5rem 0; }
.chip { font-size: .8rem; padding: .2rem .5rem; border: 1px solid #ccc; border-radius: 1rem; cursor: pointer; background: #f6f6f6; }
.chip.active { background: #2563eb; color: #fff; border-color: #2563eb; }
#results { padding: 1rem; display: grid; gap: .5rem; max-width: 800px; margin: 0 auto; }
.card { padding: .7rem; border: 1px solid #eee; border-radius: .4rem; cursor: pointer; }
.card .modern { color: #555; font-size: .9rem; }
.badge { font-size: .7rem; background: #eef; border-radius: .3rem; padding: 0 .3rem; margin-right: .2rem; }
dialog { max-width: 600px; }
```

- [ ] **Step 3:** `app/public/manifest.webmanifest`:
```json
{
  "name": "Українські прислів'я та приказки",
  "short_name": "Прислів'я",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#2563eb",
  "icons": [{ "src": "/icons/icon.svg", "sizes": "any", "type": "image/svg+xml" }]
}
```

- [ ] **Step 4:** `app/public/icons/icon.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#2563eb"/><text x="32" y="44" font-size="36" text-anchor="middle" fill="#fff" font-family="serif">П</text></svg>
```

- [ ] **Step 5:** `app/public/sw.js` (offline precache of shell + data):
```javascript
const CACHE = "ukr-proverbs-v1";
const SHELL = ["/", "/styles.css", "/app.js", "/manifest.webmanifest", "/data/proverbs.json", "/data/meta.json"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) return; // network for API
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request).then((resp) => {
    const copy = resp.clone();
    caches.open(CACHE).then((c) => c.put(e.request, copy));
    return resp;
  }).catch(() => caches.match("/"))));
});
```

- [ ] **Step 6:** `app/src/client/main.ts` (MiniSearch UI):
```typescript
import MiniSearch from "minisearch";
import { searchProverbs, randomProverb, type Proverb } from "../shared/corpus";

const $ = (id: string) => document.getElementById(id)!;
let all: Proverb[] = [];
let mini: MiniSearch<Proverb>;
let meta: any;
let activeCat = "";
let activeSource = "";

async function boot() {
  [all, meta] = await Promise.all([
    fetch("/data/proverbs.json").then((r) => r.json()),
    fetch("/data/meta.json").then((r) => r.json()),
  ]);
  mini = new MiniSearch<Proverb>({ fields: ["text", "modern_text"], storeFields: ["id"], idField: "id" });
  mini.addAll(all);
  renderFilters();
  render();
  ($("q") as HTMLInputElement).addEventListener("input", debounce(render, 200));
  $("random").addEventListener("click", () => {
    const p = randomProverb(all, { category: activeCat || undefined, source: activeSource || undefined });
    if (p) openDetail(p);
  });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
}

function renderFilters() {
  const cats = Object.entries(meta.taxonomy as Record<string, string>)
    .map(([k, label]) => `<span class="chip" data-cat="${k}">${label}</span>`).join("");
  const srcs = (["Franko1901", "Mlodzynskyi2009", "Ilkevich1841", "Bobkova"])
    .map((s) => `<span class="chip" data-src="${s}">${s}</span>`).join("");
  $("filters").innerHTML = cats + srcs;
  $("filters").querySelectorAll<HTMLElement>(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (chip.dataset.cat !== undefined) activeCat = activeCat === chip.dataset.cat ? "" : chip.dataset.cat!;
      if (chip.dataset.src !== undefined) activeSource = activeSource === chip.dataset.src ? "" : chip.dataset.src!;
      $("filters").querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      if (activeCat) $("filters").querySelector(`[data-cat="${activeCat}"]`)?.classList.add("active");
      if (activeSource) $("filters").querySelector(`[data-src="${activeSource}"]`)?.classList.add("active");
      render();
    });
  });
}

function render() {
  const q = ($("q") as HTMLInputElement).value.trim();
  let pool = all;
  if (q) {
    const ids = new Set(mini.search(q, { prefix: true, fuzzy: 0.2 }).map((r) => r.id as string));
    pool = all.filter((p) => ids.has(p.id));
  }
  const { total, results } = searchProverbs(pool, { category: activeCat || undefined, source: activeSource || undefined, limit: 200 });
  $("count").textContent = `Знайдено: ${total}`;
  $("results").innerHTML = results.map((p, i) =>
    `<div class="card" data-i="${i}">${escapeHtml(p.text)}${p.modern_text && p.modern_text !== p.text ? `<div class="modern">${escapeHtml(p.modern_text)}</div>` : ""}<div>${p.category.map((c) => `<span class="badge">${meta.taxonomy[c] ?? c}</span>`).join("")}</div></div>`).join("");
  $("results").querySelectorAll<HTMLElement>(".card").forEach((card) =>
    card.addEventListener("click", () => openDetail(results[Number(card.dataset.i)])));
}

async function openDetail(p: Proverb) {
  const expl = await fetch(`/data/explanations.json`).then((r) => r.json()).then((e) => e[p.id]).catch(() => null);
  const dlg = $("detail") as HTMLDialogElement;
  dlg.innerHTML = `<form method="dialog"><h3>${escapeHtml(p.text)}</h3>` +
    (p.modern_text && p.modern_text !== p.text ? `<p><i>${escapeHtml(p.modern_text)}</i></p>` : "") +
    (expl ? `<p>${escapeHtml(expl)}</p>` : "") +
    `<p>${p.category.map((c) => `<span class="badge">${meta.taxonomy[c] ?? c}</span>`).join("")} · ${p.sources.join(", ")}</p>` +
    `<button>Закрити</button></form>`;
  dlg.showModal();
}

function escapeHtml(s: string) { return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!)); }
function debounce(fn: () => void, ms: number) { let t: number; return () => { clearTimeout(t); t = setTimeout(fn, ms) as unknown as number; }; }

boot();
```

- [ ] **Step 7: Build + verify it compiles** — from `app/`: `node build.mjs` → produces `public/app.js` (no esbuild errors). (Data files aren't needed to compile.)

- [ ] **Step 8: Commit**
```bash
git add app/public/index.html app/public/styles.css app/public/manifest.webmanifest app/public/icons/icon.svg app/public/sw.js app/src/client/main.ts
git commit -m "feat(app): offline PWA UI with MiniSearch + filters + detail"
```

---

### Task 6 [CONTROLLER-RUN]: Generate real data + local smoke test

Controller-run.

- [ ] **Step 1: Generate data** from repo root (the `__main__` shim is in `build_data.py` from Task 1):
  `.venv/bin/python app/build_data.py corpus.csv enrich/taxonomy.csv sources.csv app/public/data corpus.xml`
  Verify `app/public/data/proverbs.json` exists; record its size (target ~5–7 MB) and the row count (40,444).
- [ ] **Step 2: Build client**: `cd app && node build.mjs`.
- [ ] **Step 3: Smoke test** `wrangler dev` (background): curl `/api/meta`, `/api/search?q=горе&limit=2`, `/api/proverb/p000001`, `/api/random`; load `/` and confirm the PWA renders + search works. Note proverbs.json gzipped transfer size.
- [ ] **Step 4: Run vitest**: `cd app && npx vitest run` — all green.
- [ ] **Step 5: Commit** generated data + xml:
```bash
git add app/public/data/proverbs.json app/public/data/explanations.json app/public/data/meta.json corpus.xml
git commit -m "feat(app): generate corpus exports for the app (40,444)"
```

---

### Task 7 [CONTROLLER-RUN]: Deploy (confirm) + README + finish

Controller-run.

- [ ] **Step 1: README** — add a "Web app / API" section to the repo `README.md`: the live URL (after deploy), the API endpoints, how to run locally (`cd app && npm install && node build.mjs && wrangler dev`). Commit.
- [ ] **Step 2: Confirm deploy with the user.** Then verify `wrangler whoami` (uses `CLOUDFLARE_API_TOKEN`); the active account must own the `ukr-proverbs-corpus` worker name.
- [ ] **Step 3: Deploy** — `cd app && npx wrangler deploy`. Capture the `*.workers.dev` URL; smoke-test it (curl `/api/meta`, open `/`). Put the URL in README; commit.
- [ ] **Step 4: Finish** — controller merges `feat/productize` → main and pushes origin + dmytro via finishing-a-development-branch.

---

## Self-Review

**1. Spec coverage:**
- §2 exports (proverbs/explanations/meta/xml) → Task 1; real generation → Task 6. ✓
- §3 client-side MiniSearch + SW offline + Worker ASSETS-load → Tasks 5 (client+sw), 4 (Worker fetches ASSETS, not import). ✓
- §4 REST API endpoints → Task 4. ✓
- §5 PWA (search/filters/detail/random/installable/offline) → Task 5. ✓
- §6 components (build_data, wrangler/esbuild/vitest, shared/corpus, index, client, public) → Tasks 1–5. ✓
- §7 testing (pytest build_data; vitest corpus + api) → Tasks 1,3,4. ✓
- §8 stack → Task 2. ✓
- §9 deploy (confirm) → Task 7. ✓

**2. Placeholder scan:** README live URL filled after deploy (Task 7); `proverbs.json` size is a measured target with mitigation in spec §10. The `__main__` shim note in Task 6 Step 1 is a concrete instruction (`build(*sys.argv[1:6])`). All code steps contain complete code. No "TBD/handle errors" steps.

**3. Type consistency:** `Proverb` shape identical in build_data output (Task 1), corpus.ts (Task 3), index.ts + fixtures (Task 4), main.ts (Task 5). `searchProverbs`/`randomProverb` signatures match between Task 3 (def) and Tasks 4/5 (use). API endpoint paths in Task 4 match spec §4 and the README (Task 7). wrangler ASSETS binding name `ASSETS` consistent (Task 2 config ↔ Task 4 `env.ASSETS`).

One gap fixed inline: Task 6 Step 1 notes adding a `__main__` shim to `build_data.py` so it's CLI-invokable (Task 1 defines `build()` as a function; the controller calls it via CLI) — implementer should include `import sys` + `if __name__ == "__main__": build(*sys.argv[1:6])` at the end of `build_data.py` in Task 1.

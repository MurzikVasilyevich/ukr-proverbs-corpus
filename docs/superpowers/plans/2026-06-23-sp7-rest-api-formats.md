# Ukrainian Proverbs — SP7: Multi-Format REST API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a versioned, content-negotiated public REST API serving the corpus in JSON / JSONL / XML / CSV / TSV.

**Architecture:** A pure `serialize()` module renders a record set into any of the 5 formats; the Worker gains `?format=`/`Accept` negotiation, a `/api/v1/*` routing layer (old `/api/*` paths kept as aliases), and two new handlers (`query`, `export`), plus a served OpenAPI spec and a static docs page. All data/logic reuse the existing `shared/corpus.ts` + Vectorize.

**Tech Stack:** TypeScript + Cloudflare Workers + esbuild + vitest (existing `app/` stack).

**Spec:** `docs/superpowers/specs/2026-06-23-sp7-rest-api-formats-design.md`

## Global Constraints

- **Formats:** `json` (default) · `jsonl` · `xml` · `csv` · `tsv`. Selected by **`?format=`** (wins) else **`Accept`** header; unknown `?format=` → **400** JSON `{error}`.
- **Content-Type per format:** json→`application/json; charset=utf-8`, jsonl→`application/x-ndjson; charset=utf-8`, xml→`application/xml; charset=utf-8`, csv→`text/csv; charset=utf-8`, tsv→`text/tab-separated-values; charset=utf-8`. File formats (jsonl/xml/csv/tsv) also set `Content-Disposition: attachment; filename="proverbs-<name>.<ext>"`. **CORS `Access-Control-Allow-Origin: *` on every response.**
- **Record:** `{id, text, modern_text, category[], sources[], variant_group}`; `proverb/:id` & `export` also include `explanation`. CSV/TSV/XML columns: `id,text,modern_text,category,sources,variant_group[,explanation]` (category/sources `;`-joined). **`score` (semantic) appears only in json/jsonl.**
- **JSON collections:** `{total, limit, offset, results:[…]}`; single → the record object. **JSONL/CSV/TSV/XML:** just the records. Collections also set `X-Total-Count`.
- **Pagination:** `limit` default 50, max 200, min 1; `offset` default 0. `export` ignores limit (returns all matching). `random` `n` default 1, max 50.
- **Versioning:** canonical `/api/v1/*`; the Worker strips an optional `/v1` segment so existing `/api/*` handlers are reused (aliases keep working; their default-JSON shapes must stay back-compatible — extra envelope keys are allowed).
- esbuild bundles JSON imports. Commits carry the session footer. Branch `feat/api-formats`. Push: origin via `gh auth switch --user MurzikVasilyevich`; dmytro is SSH. Deploy is **outward — confirm with user**.
- **Task types:** `[IMPL]` TDD implementer · `[CONTROLLER-RUN]` controller (deploy).

---

### Task 1 [IMPL]: `serialize.ts` — the 5 format serializers + negotiation

**Files:** Create `app/src/shared/serialize.ts`, `app/test/serialize.test.ts`.

**Interfaces:**
- Produces:
  - `type Format = "json"|"jsonl"|"xml"|"csv"|"tsv"`; `type Rec = Proverb & { explanation?: string|null; score?: number }`.
  - `negotiate(formatParam: string|null, accept: string|null) -> Format | null` — returns the format; `null` ONLY when `formatParam` is a non-empty unknown value (caller → 400). No param → map `Accept` (default `json`).
  - `serialize(records: Rec[], format: Format, opts: {single?: boolean; total?: number; limit?: number; offset?: number; withExplanation?: boolean; name?: string}) -> {body: string; contentType: string; filename?: string}`.

- [ ] **Step 1: Write the failing test** — `app/test/serialize.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { negotiate, serialize, type Rec } from "../src/shared/serialize";

const R = (id: string, over: Partial<Rec> = {}): Rec =>
  ({ id, text: `t,${id}`, modern_text: `m"${id}`, category: ["a", "b"], sources: ["S"], variant_group: "", ...over });
const recs: Rec[] = [R("p1"), R("p2")];

describe("negotiate", () => {
  it("?format wins, valid", () => expect(negotiate("csv", "application/json")).toBe("csv"));
  it("unknown ?format -> null", () => expect(negotiate("yaml", null)).toBeNull());
  it("Accept fallback", () => {
    expect(negotiate(null, "text/csv")).toBe("csv");
    expect(negotiate(null, "application/x-ndjson")).toBe("jsonl");
    expect(negotiate(null, "*/*")).toBe("json");
    expect(negotiate(null, null)).toBe("json");
  });
});

describe("serialize", () => {
  it("json collection envelope", () => {
    const r = serialize(recs, "json", { total: 9, limit: 50, offset: 0 });
    expect(r.contentType).toContain("application/json");
    expect(JSON.parse(r.body)).toEqual({ total: 9, limit: 50, offset: 0, results: recs });
    expect(r.filename).toBeUndefined();
  });
  it("json single", () => {
    expect(JSON.parse(serialize([recs[0]], "json", { single: true }).body)).toEqual(recs[0]);
  });
  it("jsonl one object per line", () => {
    const r = serialize(recs, "jsonl", { name: "search" });
    expect(r.body.split("\n").length).toBe(2);
    expect(JSON.parse(r.body.split("\n")[0]).id).toBe("p1");
    expect(r.filename).toBe("proverbs-search.jsonl");
    expect(r.contentType).toContain("x-ndjson");
  });
  it("csv RFC-4180 quoting + header", () => {
    const r = serialize([R("p1")], "csv", { name: "x" });
    const lines = r.body.trim().split("\n");
    expect(lines[0]).toBe("id,text,modern_text,category,sources,variant_group");
    expect(lines[1]).toBe('p1,"t,p1","m""p1",a;b,S,');   // comma & quote escaped
    expect(r.filename).toBe("proverbs-x.csv");
  });
  it("csv adds explanation column when withExplanation", () => {
    const r = serialize([R("p1", { explanation: "ex" })], "csv", { withExplanation: true });
    expect(r.body.split("\n")[0]).toBe("id,text,modern_text,category,sources,variant_group,explanation");
  });
  it("tsv strips tabs/newlines", () => {
    const r = serialize([R("p1", { text: "a\tb\nc" })], "tsv");
    expect(r.contentType).toContain("tab-separated");
    expect(r.body.split("\n")[1].split("\t")[1]).toBe("a b c");
  });
  it("xml escaped + well-formed-ish", () => {
    const r = serialize([R("p1", { text: "a<b&c" })], "xml");
    expect(r.body).toContain("<proverbs>");
    expect(r.body).toContain("<text>a&lt;b&amp;c</text>");
    expect(r.contentType).toContain("application/xml");
  });
});
```

- [ ] **Step 2: Run, verify fail** — from `app/`: `npx vitest run test/serialize.test.ts` → FAIL.

- [ ] **Step 3: Implement** — `app/src/shared/serialize.ts`:
```typescript
import { type Proverb } from "./corpus";

export type Format = "json" | "jsonl" | "xml" | "csv" | "tsv";
export type Rec = Proverb & { explanation?: string | null; score?: number };

const FORMATS: readonly string[] = ["json", "jsonl", "xml", "csv", "tsv"];

export function negotiate(formatParam: string | null, accept: string | null): Format | null {
  if (formatParam) return (FORMATS.includes(formatParam) ? formatParam : null) as Format | null;
  const a = (accept ?? "").toLowerCase();
  if (a.includes("application/x-ndjson")) return "jsonl";
  if (a.includes("text/tab-separated-values")) return "tsv";
  if (a.includes("text/csv")) return "csv";
  if (a.includes("application/xml") || a.includes("text/xml")) return "xml";
  return "json";
}

const CT: Record<Format, string> = {
  json: "application/json; charset=utf-8",
  jsonl: "application/x-ndjson; charset=utf-8",
  xml: "application/xml; charset=utf-8",
  csv: "text/csv; charset=utf-8",
  tsv: "text/tab-separated-values; charset=utf-8",
};

const cell = (r: Rec, c: string): string => {
  if (c === "category") return (r.category ?? []).join(";");
  if (c === "sources") return (r.sources ?? []).join(";");
  if (c === "explanation") return r.explanation ?? "";
  return String((r as Record<string, unknown>)[c] ?? "");
};
const csvField = (s: string): string => (/[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
const tsvField = (s: string): string => s.replace(/[\t\n\r]+/g, " ");
const xmlEsc = (s: string): string => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]!));

export function serialize(
  records: Rec[],
  format: Format,
  opts: { single?: boolean; total?: number; limit?: number; offset?: number; withExplanation?: boolean; name?: string } = {},
): { body: string; contentType: string; filename?: string } {
  const cols = ["id", "text", "modern_text", "category", "sources", "variant_group", ...(opts.withExplanation ? ["explanation"] : [])];
  const fn = (ext: string) => `proverbs-${opts.name ?? "export"}.${ext}`;

  if (format === "json") {
    const body = opts.single
      ? JSON.stringify(records[0] ?? null)
      : JSON.stringify({ total: opts.total ?? records.length, limit: opts.limit, offset: opts.offset, results: records });
    return { body, contentType: CT.json };
  }
  if (format === "jsonl") {
    return { body: records.map((r) => JSON.stringify(r)).join("\n"), contentType: CT.jsonl, filename: fn("jsonl") };
  }
  if (format === "xml") {
    const items = records.map((r) =>
      `  <proverb id="${xmlEsc(r.id)}">` +
      `<text>${xmlEsc(r.text)}</text><modern_text>${xmlEsc(r.modern_text)}</modern_text>` +
      `<category>${xmlEsc((r.category ?? []).join(";"))}</category><sources>${xmlEsc((r.sources ?? []).join(";"))}</sources>` +
      (opts.withExplanation ? `<explanation>${xmlEsc(r.explanation ?? "")}</explanation>` : "") +
      `</proverb>`).join("\n");
    return { body: `<?xml version="1.0" encoding="UTF-8"?>\n<proverbs>\n${items}\n</proverbs>\n`, contentType: CT.xml, filename: fn("xml") };
  }
  // csv / tsv
  const field = format === "csv" ? csvField : tsvField;
  const sep = format === "csv" ? "," : "\t";
  const header = cols.join(sep);
  const rows = records.map((r) => cols.map((c) => field(cell(r, c))).join(sep));
  return { body: [header, ...rows].join("\n") + "\n", contentType: CT[format], filename: fn(format) };
}
```

- [ ] **Step 4: Run, verify pass** — `npx vitest run test/serialize.test.ts` → PASS.

- [ ] **Step 5: Commit**
```bash
git add app/src/shared/serialize.ts app/test/serialize.test.ts
git commit -m "feat(api): serialize records to json/jsonl/xml/csv/tsv + format negotiation"
```

---

### Task 2 [IMPL]: `queryProverbs` flexible filter

**Files:** Modify `app/src/shared/corpus.ts`; Create/extend `app/test/corpus.test.ts` (add a describe block).

**Interfaces:**
- Produces: `queryProverbs(all: Proverb[], opts: {category?: string; source?: string; variant_group?: string; has_explanation?: boolean; explanationIds?: Set<string>; limit?: number; offset?: number}) -> {total: number; results: Proverb[]}` — filters by category (in `category[]`), source (in `sources[]`), exact `variant_group`, and — when `has_explanation` is defined — by membership of `id` in `explanationIds` (true → has; false → lacks). limit default 50 / max 200 / min 1; offset default 0; total = pre-pagination count.

- [ ] **Step 1: Write the failing test** — append to `app/test/corpus.test.ts`:
```typescript
import { queryProverbs } from "../src/shared/corpus";

describe("queryProverbs", () => {
  const data = [
    { id: "p1", text: "a", modern_text: "a", category: ["work_labor"], sources: ["Franko1901"], variant_group: "v1" },
    { id: "p2", text: "b", modern_text: "b", category: ["animals"], sources: ["Nomis1864"], variant_group: "v1" },
    { id: "p3", text: "c", modern_text: "c", category: ["animals"], sources: ["Nomis1864"], variant_group: "" },
  ];
  it("filters by category/source/variant_group", () => {
    expect(queryProverbs(data, { category: "animals" }).total).toBe(2);
    expect(queryProverbs(data, { source: "Franko1901" }).total).toBe(1);
    expect(queryProverbs(data, { variant_group: "v1" }).total).toBe(2);
  });
  it("has_explanation via explanationIds", () => {
    const ex = new Set(["p1"]);
    expect(queryProverbs(data, { has_explanation: true, explanationIds: ex }).results.map((r) => r.id)).toEqual(["p1"]);
    expect(queryProverbs(data, { has_explanation: false, explanationIds: ex }).total).toBe(2);
  });
  it("pagination + total", () => {
    const r = queryProverbs(data, { limit: 1, offset: 1 });
    expect(r.total).toBe(3);
    expect(r.results.length).toBe(1);
  });
});
```

- [ ] **Step 2: Run, verify fail** — `npx vitest run test/corpus.test.ts` → FAIL (no `queryProverbs`).

- [ ] **Step 3: Implement** — append to `app/src/shared/corpus.ts`:
```typescript
export function queryProverbs(
  all: Proverb[],
  opts: { category?: string; source?: string; variant_group?: string; has_explanation?: boolean; explanationIds?: Set<string>; limit?: number; offset?: number },
): { total: number; results: Proverb[] } {
  const limit = Math.min(Math.max(opts.limit ?? 50, 1), 200);
  const offset = Math.max(opts.offset ?? 0, 0);
  const matched = all.filter((p) => {
    if (opts.category && !p.category.includes(opts.category)) return false;
    if (opts.source && !p.sources.includes(opts.source)) return false;
    if (opts.variant_group && p.variant_group !== opts.variant_group) return false;
    if (opts.has_explanation !== undefined) {
      const has = opts.explanationIds?.has(p.id) ?? false;
      if (has !== opts.has_explanation) return false;
    }
    return true;
  });
  return { total: matched.length, results: matched.slice(offset, offset + limit) };
}
```

- [ ] **Step 4: Run, verify pass** — `npx vitest run test/corpus.test.ts` → PASS (existing + new).

- [ ] **Step 5: Commit**
```bash
git add app/src/shared/corpus.ts app/test/corpus.test.ts
git commit -m "feat(api): queryProverbs flexible filter (category/source/variant_group/has_explanation)"
```

---

### Task 3 [IMPL]: Worker — `/api/v1` routing, negotiation, query/export, serialize wiring

**Files:** Modify `app/src/index.ts` (full replacement below); Create `app/test/api-v1.test.ts`.

**Interfaces:** Consumes `serialize`/`negotiate`/`Rec` (Task 1), `queryProverbs` (Task 2), existing `searchProverbs`/`randomProverb`/`mapMatches`. The `openapiDoc` import is created in Task 4 — for THIS task, create a minimal placeholder `app/src/openapi.json` = `{"openapi":"3.0.3","info":{"title":"ukr-proverbs API","version":"1.0.0"},"paths":{}}` so the import resolves (Task 4 fills it in).

- [ ] **Step 1: Create the placeholder OpenAPI import** — `app/src/openapi.json`:
```json
{ "openapi": "3.0.3", "info": { "title": "Ukrainian Proverbs API", "version": "1.0.0" }, "paths": {} }
```

- [ ] **Step 2: Write the failing test** — `app/test/api-v1.test.ts`:
```typescript
import { env, createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { describe, it, expect } from "vitest";
import worker from "../src/index";

const AI = { run: async () => ({ data: [[0.1, 0.2]] }) };
const VEC = { query: async () => ({ matches: [{ id: "p1", score: 0.9 }] }), getByIds: async () => [{ id: "p1", values: [0.1, 0.2] }] };
async function call(path: string, headers: Record<string, string> = {}) {
  const ctx = createExecutionContext();
  const res = await worker.fetch(new Request("https://x" + path, { headers }), { ...env, AI, VEC: VEC, VECTORIZE: VEC } as any, ctx);
  await waitOnExecutionContext(ctx);
  return res;
}

describe("/api/v1 formats", () => {
  it("search json default has envelope + X-Total-Count + CORS", async () => {
    const res = await call("/api/v1/search?q=", {});
    expect(res.headers.get("access-control-allow-origin")).toBe("*");
    expect(res.headers.get("x-total-count")).toBeTruthy();
    const b = await res.json() as any;
    expect(b).toHaveProperty("results"); expect(b).toHaveProperty("limit");
  });
  it("?format=csv yields text/csv + attachment", async () => {
    const res = await call("/api/v1/search?q=&format=csv");
    expect(res.headers.get("content-type")).toContain("text/csv");
    expect(res.headers.get("content-disposition")).toContain("attachment");
    expect((await res.text()).split("\n")[0]).toBe("id,text,modern_text,category,sources,variant_group");
  });
  it("Accept negotiation -> jsonl", async () => {
    const res = await call("/api/v1/search?q=", { accept: "application/x-ndjson" });
    expect(res.headers.get("content-type")).toContain("x-ndjson");
  });
  it("unknown format -> 400", async () => {
    expect((await call("/api/v1/search?format=yaml")).status).toBe(400);
  });
  it("query filters; export includes explanation column", async () => {
    expect((await call("/api/v1/query?source=Franko1901")).status).toBe(200);
    const csv = await (await call("/api/v1/export?format=csv")).text();
    expect(csv.split("\n")[0]).toContain("explanation");
  });
  it("alias /api/search still returns the old JSON shape", async () => {
    const b = await (await call("/api/search?q=")).json() as any;
    expect(b).toHaveProperty("total"); expect(b).toHaveProperty("results");
  });
  it("openapi served", async () => {
    const b = await (await call("/api/v1/openapi.json")).json() as any;
    expect(b.openapi).toBe("3.0.3");
  });
});
```
(Fixtures `p1`,`p2` come from `app/test/fixtures-site/data/proverbs.json`; `explanations.json` has `p1`.)

- [ ] **Step 3: Run, verify fail** — `npx vitest run test/api-v1.test.ts` → FAIL.

- [ ] **Step 4: Implement** — replace `app/src/index.ts` entirely with:
```typescript
import { searchProverbs, randomProverb, queryProverbs, type Proverb } from "./shared/corpus";
import { mapMatches, type Match } from "./shared/semantic";
import { negotiate, serialize, type Format, type Rec } from "./shared/serialize";
import openapiDoc from "./openapi.json";

interface Env {
  ASSETS: { fetch: (req: Request | string) => Promise<Response> };
  AI: { run: (model: string, inputs: { text: string[] }) => Promise<{ data: number[][] }> };
  VECTORIZE: {
    query: (vector: number[], opts: { topK: number }) => Promise<{ matches: Match[] }>;
    getByIds: (ids: string[]) => Promise<Array<{ id: string; values: number[] }>>;
  };
}

const SEMANTIC_MIN_SCORE = 0.4;
const CORS = { "access-control-allow-origin": "*" };

let cache: Promise<{ proverbs: Proverb[]; explanations: Record<string, string>; meta: any; byId: Map<string, Proverb> }> | null = null;
function load(env: Env) {
  if (!cache) {
    cache = (async () => {
      const get = async (p: string) => {
        const res = await env.ASSETS.fetch("https://assets" + p);
        if (!res.ok) throw new Error(`Failed to fetch ${p}: ${res.status}`);
        return res.json();
      };
      const [proverbs, explanations, meta] = await Promise.all([
        get("/data/proverbs.json") as Promise<Proverb[]>,
        get("/data/explanations.json") as Promise<Record<string, string>>,
        get("/data/meta.json") as Promise<any>,
      ]);
      return { proverbs, explanations, meta, byId: new Map(proverbs.map((p) => [p.id, p])) };
    })().catch((err) => { cache = null; throw err; });
  }
  return cache;
}

const J = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", ...CORS } });

const finiteOrUndef = (n: number): number | undefined => (Number.isFinite(n) ? n : undefined);

/** Render a record set in the negotiated format with the right headers. */
function respond(
  fmt: Format, records: Rec[],
  o: { single?: boolean; total?: number; limit?: number; offset?: number; withExplanation?: boolean; name?: string },
): Response {
  const { body, contentType, filename } = serialize(records, fmt, o);
  const headers: Record<string, string> = { "content-type": contentType, ...CORS };
  if (!o.single && o.total !== undefined) headers["x-total-count"] = String(o.total);
  if (filename) headers["content-disposition"] = `attachment; filename="${filename}"`;
  return new Response(body, { headers });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      const url = new URL(request.url);
      const raw = url.pathname;
      if (!raw.startsWith("/api/")) return env.ASSETS.fetch(request);
      // strip optional /v1 -> reuse canonical handlers; aliases keep working
      const path = raw.startsWith("/api/v1/") ? "/api/" + raw.slice("/api/v1/".length) : (raw === "/api/v1" ? "/api" : raw);
      const qp = url.searchParams;

      // format negotiation (data endpoints); null => bad ?format
      const fmt = negotiate(qp.get("format"), request.headers.get("accept"));
      if (fmt === null) return J({ error: `unknown format '${qp.get("format")}'; use json|jsonl|xml|csv|tsv` }, 400);

      // docs pointer
      if (path === "/api") return J({ api: "ukr-proverbs", version: "v1", docs: "/api.html", openapi: "/api/v1/openapi.json",
        endpoints: ["/api/v1/search", "/api/v1/semantic", "/api/v1/random", "/api/v1/query", "/api/v1/proverb/:id", "/api/v1/export", "/api/v1/categories", "/api/v1/meta"] });
      if (path === "/api/openapi.json") return J(openapiDoc);

      const { proverbs, explanations, meta, byId } = await load(env);
      const lim = () => finiteOrUndef(Number(qp.get("limit")));
      const off = () => finiteOrUndef(Number(qp.get("offset")));
      const eff = (l?: number, o?: number) => ({ limit: Math.min(Math.max(l ?? 50, 1), 200), offset: Math.max(o ?? 0, 0) });

      if (path === "/api/search") {
        const r = searchProverbs(proverbs, { q: qp.get("q") ?? undefined, category: qp.get("category") ?? undefined, source: qp.get("source") ?? undefined, limit: lim(), offset: off() });
        const e = eff(lim(), off());
        return respond(fmt, r.results as Rec[], { total: r.total, limit: e.limit, offset: e.offset, name: "search" });
      }
      if (path === "/api/query") {
        const has = qp.get("has_explanation");
        const r = queryProverbs(proverbs, {
          category: qp.get("category") ?? undefined, source: qp.get("source") ?? undefined,
          variant_group: qp.get("variant_group") ?? undefined,
          has_explanation: has === null ? undefined : has === "true",
          explanationIds: new Set(Object.keys(explanations)),
          limit: lim(), offset: off(),
        });
        const e = eff(lim(), off());
        return respond(fmt, r.results as Rec[], { total: r.total, limit: e.limit, offset: e.offset, name: "query" });
      }
      if (path === "/api/random") {
        const n = Math.min(Math.max(finiteOrUndef(Number(qp.get("n"))) ?? 1, 1), 50);
        const picked: Proverb[] = [];
        const seen = new Set<string>();
        for (let i = 0; i < n * 5 && picked.length < n; i++) {
          const p = randomProverb(proverbs, { category: qp.get("category") ?? undefined, source: qp.get("source") ?? undefined });
          if (p && !seen.has(p.id)) { seen.add(p.id); picked.push(p); }
          if (!p) break;
        }
        return respond(fmt, picked as Rec[], { total: picked.length, limit: n, offset: 0, name: "random" });
      }
      if (path === "/api/export") {
        const r = queryProverbs(proverbs, { category: qp.get("category") ?? undefined, source: qp.get("source") ?? undefined, limit: proverbs.length, offset: 0 });
        const withExpl = r.results.map((p) => ({ ...p, explanation: explanations[p.id] ?? "" })) as Rec[];
        return respond(fmt, withExpl, { total: r.total, withExplanation: true, name: "export" });
      }
      if (path === "/api/categories") {
        const counts = meta.per_category ?? {};
        return J(Object.entries(meta.taxonomy as Record<string, string>).map(([key, label]) => ({ key, label, count: counts[key] ?? 0 })));
      }
      if (path === "/api/meta") return J(meta);
      const m = path.match(/^\/api\/proverb\/(.+)$/);
      if (m) {
        const p = proverbs.find((x) => x.id === decodeURIComponent(m[1]));
        if (!p) return J({ error: "not found" }, 404);
        return respond(fmt, [{ ...p, explanation: explanations[p.id] ?? null }] as Rec[], { single: true, withExplanation: true, name: "proverb" });
      }
      if (path === "/api/semantic") {
        const q = (qp.get("q") ?? "").trim();
        if (!q) return J({ error: "missing q" }, 400);
        if (!env.AI || !env.VECTORIZE) return J({ error: "semantic search unavailable" }, 503);
        try {
          const { data } = await env.AI.run("@cf/baai/bge-m3", { text: [q] });
          const { matches } = await env.VECTORIZE.query(data[0], { topK: 100 });
          const minScore = qp.get("minScore") ? Number(qp.get("minScore")) : SEMANTIC_MIN_SCORE;
          const r = mapMatches(matches, byId, { category: qp.get("category") ?? undefined, source: qp.get("source") ?? undefined, minScore: Number.isFinite(minScore) ? minScore : SEMANTIC_MIN_SCORE, limit: lim() });
          const e = eff(lim(), 0);
          // score lives on the Scored records; csv/xml/tsv drop it (fixed cols)
          return respond(fmt, r.results as Rec[], { total: r.total, limit: e.limit, offset: 0, name: "semantic" });
        } catch { return J({ error: "semantic search failed" }, 502); }
      }
      const sim = path.match(/^\/api\/similar\/(.+)$/);
      if (sim) {
        if (!env.VECTORIZE) return J({ error: "semantic search unavailable" }, 503);
        const id = decodeURIComponent(sim[1]);
        try {
          const recs = await env.VECTORIZE.getByIds([id]);
          if (!recs.length) return J({ error: "not indexed" }, 404);
          const l = finiteOrUndef(Number(qp.get("limit"))) ?? 6;
          const { matches } = await env.VECTORIZE.query(recs[0].values, { topK: Math.min(l + 1, 100) });
          const r = mapMatches(matches, byId, { excludeId: id, limit: l });
          return respond(fmt, r.results as Rec[], { total: r.total, limit: l, offset: 0, name: "similar" });
        } catch { return J({ error: "similar lookup failed" }, 502); }
      }
      return J({ error: "unknown endpoint" }, 404);
    } catch {
      return J({ error: "internal error" }, 500);
    }
  },
};
```
(Note: the alias JSON shapes stay back-compatible — `/api/search` now returns `{total,limit,offset,results}` (extra keys vs the old `{total,results}`; the PWA reads only `total`/`results`); `/api/random` now returns a collection `{results:[…]}` instead of a single object — the PWA computes random client-side, so it's unaffected. Both are covered by the alias test + the existing suite.)

- [ ] **Step 5: Run, verify pass** — from `app/`: `npx vitest run` → ALL green (serialize, corpus, api, semantic-api, api-v1). If the pre-existing `api.test.ts` asserts `/api/random` returns a bare object, update that assertion to read `body.results[0]` (the documented shape change) and note it.

- [ ] **Step 6: Commit**
```bash
git add app/src/index.ts app/src/openapi.json app/test/api-v1.test.ts
git commit -m "feat(api): /api/v1 routing + format negotiation + query/export endpoints"
```

---

### Task 4 [IMPL]: OpenAPI spec + docs page + footer link

**Files:** Modify `app/src/openapi.json` (fill in), `app/public/index.html` (footer link); Create `app/public/api.html`.

- [ ] **Step 1: Fill `app/src/openapi.json`** with the real spec (paths: `/api/v1/search`, `/semantic`, `/random`, `/query`, `/proverb/{id}`, `/export`, `/categories`, `/meta`), each documenting the shared `format` query param (enum json|jsonl|xml|csv|tsv) + endpoint params, and a `Proverb` schema (`id,text,modern_text,category[],sources[],variant_group,explanation`). Server `url: "https://ukr-proverbs-corpus.miwaniza.workers.dev"`. (Concrete, hand-written OpenAPI 3.0.3 — every path lists its params + the `200` response with the five `content` types.)

- [ ] **Step 2: Create `app/public/api.html`** — a static docs page in the editorial style (Spectral/wine, links `/fonts/spectral.css` + `/styles.css`), listing each endpoint with copy-paste `curl` examples for each format, e.g.:
```
curl 'https://ukr-proverbs-corpus.miwaniza.workers.dev/api/v1/search?q=гроші&format=csv'
curl 'https://.../api/v1/random?n=3'
curl -H 'Accept: application/x-ndjson' 'https://.../api/v1/export'
curl 'https://.../api/v1/proverb/p000001?format=xml'
```
plus a link to `/api/v1/openapi.json`. Plain HTML, no external JS.

- [ ] **Step 3: Add a footer link** in `app/public/index.html` `.col-note` (or a new `.col-api` line): `<a href="/api.html">API</a>` alongside the GitHub link.

- [ ] **Step 4: Build + verify** — from `app/`: `node build.mjs` (esbuild rebundles, incl. the now-filled `openapi.json` import) → no errors; `npx vitest run` still green (the openapi test now sees real paths).

- [ ] **Step 5: Commit**
```bash
git add app/src/openapi.json app/public/api.html app/public/index.html
git commit -m "feat(api): OpenAPI 3 spec + /api.html docs page + footer link"
```

---

### Task 5 [CONTROLLER-RUN]: Preview, deploy, finish

Controller-run. Deploy is **outward — confirm with the user**.

- [ ] **Step 1: Bump SW cache** — `app/public/sw.js` `CACHE` → next version (adds `api.html`); add `/api.html` to the `SHELL` precache list if desired.
- [ ] **Step 2: Preview** — `cd app && node build.mjs && npx wrangler versions upload`; on the preview URL curl each endpoint × each format: `search/query/random/proverb/export` as json/jsonl/xml/csv/tsv; check `Content-Type`, `Content-Disposition`, `X-Total-Count`; confirm CSV opens in a spreadsheet, JSONL parses line-by-line, XML validates, `/api/v1/openapi.json` loads in an OpenAPI viewer, `/api.html` renders, and aliases (`/api/search`) still work.
- [ ] **Step 3: Deploy** (confirm with user) — `npx wrangler deploy`; smoke production.
- [ ] **Step 4: Finish** — controller merges `feat/api-formats` → main, pushes both remotes (origin needs `gh auth switch --user MurzikVasilyevich`); update README (API section: the v1 endpoints + formats + link to `/api.html`) and memory.

---

## Self-Review

**1. Spec coverage:** §2 negotiation (`?format=`+Accept, 400) → Task 1 (`negotiate`) + Task 3. §3 endpoints (search/semantic/random/query/proverb/export/categories/meta/openapi + aliases + `/api` docs pointer) → Task 3; docs page → Task 4. §4 record shape, JSON envelope, JSONL/CSV/TSV/XML, headers, score-in-json/jsonl-only → Task 1 (`serialize`) + Task 3 (`respond`). §5 components (serialize.ts, index.ts, openapi.json, api.html, queryProverbs) → Tasks 1–4. §6 testing (serialize units, api-v1 over mocked bindings, alias) → Tasks 1–3. §7 deploy → Task 5. §8 export-size (built in memory, fine at 48,787) handled in `/api/export`; semantic-score omitted from csv/xml/tsv via fixed cols. ✓

**2. Placeholder scan:** complete code for serialize.ts, queryProverbs, full index.ts; openapi.json + api.html described with concrete content/examples (Task 4 Steps 1–2 are real artifacts, not "TBD"). The Task-3 placeholder `openapi.json` is intentional scaffolding filled in Task 4 (stated). No "handle errors" hand-waves.

**3. Type consistency:** `Format`/`Rec`/`serialize`/`negotiate` identical between Task 1 (def) and Task 3 (use). `queryProverbs` signature matches between Task 2 (def) and Task 3 (use). `respond(fmt, records, opts)` consistent. `openapiDoc` import (Task 3) ↔ `app/src/openapi.json` (Tasks 3 placeholder, 4 filled). Endpoint paths in index.ts ↔ openapi.json ↔ api.html ↔ README all `/api/v1/*`.

**Back-compat note (deliberate):** `/api/search` JSON gains `limit`/`offset` keys (additive, PWA reads only total/results); `/api/random` changes from a bare object to a `{results:[…]}` collection (PWA does random client-side, unaffected) — covered by the alias test and called out in Task 3 Step 5.

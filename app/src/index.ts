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

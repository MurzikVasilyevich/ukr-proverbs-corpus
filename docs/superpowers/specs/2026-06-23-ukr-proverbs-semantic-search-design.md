# Ukrainian Proverbs Corpus — Semantic Search (SP5)

**Date:** 2026-06-23
**Status:** Approved (design)
**Sub-project:** 5 — semantic search via embeddings + Cloudflare Vectorize
**Repo:** `ukr-proverbs-corpus` (existing); new `embed/` dir + additions to `app/`
**Depends on:** SP1–SP4 — done (corpus = 40,444, live Worker app at ukr-proverbs-corpus.miwaniza.workers.dev).
**Pattern:** extends the existing Cloudflare Worker app; managed Vectorize chosen over a static vector blob because the corpus will keep growing.

---

## 1. Scope

Add **meaning-based ("semantic") search** over the 40,444-proverb corpus as an **opt-in** layer on top of the existing lexical MiniSearch. Two user-facing capabilities:
- **Search by meaning / situation** — a «за змістом» toggle on the search bar.
- **Find similar proverbs** — a «Схожі прислів'я» section on the detail view.

Implemented with Workers AI embeddings (`@cf/baai/bge-m3`) + Cloudflare **Vectorize** as the vector index, served by the existing Worker.

**Out of scope:** replacing or fusing with lexical search (lexical stays the default, untouched); cross-lingual/translation features; offline semantic search; re-ranking models; the Telegram bot (still SP4c).

## 2. Embeddings

- **Model:** `@cf/baai/bge-m3` — multilingual (strong Ukrainian), 1024 dimensions, cosine similarity.
- **Embed text composition** (per proverb, uniform): join with newlines —
  1. `text` (always),
  2. `modern_text` (only if it differs from `text`),
  3. `explanation` (only if present, truncated to the first 1000 characters to bound tokens).
  Entries without an explanation (~26%) simply embed `text` (+`modern_text`). bge-m3's 8192-token context comfortably fits this.
- **Query embedding:** the user's query string is embedded with the same model at request time.

## 3. Index build pipeline (`embed/`, incremental)

A small Python package, run manually after corpus changes (matches the enrichment workflow):

- `embed/compose.py` — `compose_embed_text(row) -> str` (the §2 composition) and `content_hash(text) -> str` (stable hash of the embed-text).
- `embed/manifest.py` — read/write `embed/manifest.json` mapping `id → content_hash`; diff a fresh corpus against the manifest to produce `{to_upsert: [ids], to_delete: [ids]}` (new + changed are upserted; ids absent from the new corpus are deleted). Idempotent: an unchanged corpus yields empty sets.
- `embed/run.py` — orchestrator: load `corpus.csv`, diff vs manifest, embed `to_upsert` in batches via the **Workers AI REST API** (`POST /accounts/{acct}/ai/run/@cf/baai/bge-m3`), **upsert** vectors (id + the 1024-dim values) to the Vectorize index via the **Vectorize REST API**, delete `to_delete`, then rewrite the manifest. Uses `CLOUDFLARE_API_TOKEN` + account id from env. Logs counts (embedded / upserted / deleted / skipped) and the spend estimate.
- Vector **metadata**: store only `{id}`. Category/source filtering happens in the Worker against the in-memory `proverbs.json` (§4), avoiding dependence on Vectorize array-metadata filter semantics and reusing data the Worker already holds.
- Documented run command in the README (e.g. `python -m embed.run`). Re-running after the corpus grows embeds only the delta.

## 4. Worker API (additions to `app/src/index.ts` + `app/src/shared/`)

Bindings added to `wrangler.jsonc`: `AI` (Workers AI) and `VECTORIZE` (the index, binding name `VECTORIZE`).

New endpoints (JSON, same permissive CORS + error handling as existing routes):
- `GET /api/semantic?q=&category=&source=&limit=` →
  1. embed `q` via `env.AI.run("@cf/baai/bge-m3", {text:[q]})`;
  2. `env.VECTORIZE.query(vector, {topK: 200})` → `[{id, score}]`;
  3. map ids → full proverbs from the in-memory corpus (already loaded from ASSETS);
  4. apply `category`/`source` filters and a **score cutoff** (default min score, tunable) in the Worker;
  5. return `{total, results:[{...proverb, score}]}`, limit default 50 / max 200.
  Missing/empty `q` → 400 JSON. If `AI`/`VECTORIZE` unavailable → 503 JSON `{error}`.
- `GET /api/similar/:id?limit=` →
  1. `env.VECTORIZE.getByIds([id])` with values → the proverb's stored vector (404 if the id isn't indexed);
  2. `env.VECTORIZE.query(vector, {topK: limit+1})`;
  3. drop the query id itself; map to proverbs; return `{results:[{...proverb, score}]}`.

A shared helper module (`app/src/shared/semantic.ts`) holds the pure pieces (id→proverb mapping, score-cutoff + filter + pagination over a `[{id,score}]` list) so they're unit-testable without the live bindings.

## 5. Client UX (`app/public` + `app/src/client/main.ts`)

- **Search bar** gains a small **«за змістом»** toggle next to the input. Off (default) = current lexical MiniSearch (offline). On = queries `/api/semantic` (debounced), renders the same result cards plus a faint similarity indicator; a short "потрібен інтернет" hint shows while on.
- **Detail view** gains a **«Схожі прислів'я»** section that lazy-calls `/api/similar/:id` when a proverb is opened and lists the neighbours (clickable to their own detail).
- **Offline/degradation:** when `navigator.onLine` is false, the «за змістом» toggle is disabled (reverts to lexical) and the similar section is hidden — the app stays fully usable offline on lexical search.
- Editorial styling consistent with the current design (wine accent, Spectral, catalog-№); the similarity score shown discreetly in mono.

## 6. Offline / PWA

No change to offline behaviour for lexical search or the shell. Semantic endpoints are network-only by design and are **not** precached. The service worker continues to bypass `/api/*` (network) and precache the shell + data.

## 7. Ops / account setup

- Requires the **Workers Paid plan** (~$5/mo; corpus's ~41M stored dimensions exceed the 5M free Vectorize tier). **The user enables billing in the Cloudflare dashboard** — an account/billing action not performed by the agent.
- Once paid is active: create the index (`wrangler vectorize create proverbs-bge-m3 --dimensions=1024 --metric=cosine`), add the `AI` + `VECTORIZE` bindings to `wrangler.jsonc`, run the embed pipeline, deploy. Deploy + index creation are confirmed with the user at execution time (consistent with prior sub-projects).

## 8. Testing

- **pytest** (`embed/`): `compose_embed_text` (all field-presence combinations, explanation truncation), `content_hash` stability, and the manifest diff (`to_upsert`/`to_delete` for added/changed/removed/unchanged rows). The REST calls in `run.py` are exercised against a stubbed HTTP client (no live API in tests).
- **vitest** (`app/`): `shared/semantic.ts` pure functions (id→proverb mapping, score cutoff, filter, pagination, self-exclusion) over fixtures; `/api/semantic` + `/api/similar` over **mocked** `AI` + `VECTORIZE` bindings (correct shape/status, filter application, missing-query 400, unknown-id 404, binding-unavailable 503).
- **Manual:** a preview deploy (`wrangler versions upload`) with the real index for end-to-end smoke (query relevance, similar, offline degradation) before promoting — Vectorize has limited local-dev support, so real verification is on preview.

## 9. Cost

- One-time embedding of the full corpus: ~$0.04 (≈3,700 Neurons; within the 10,000 Neurons/day free allowance).
- Ongoing: query embeddings + Vectorize queries negligible (well within free/included tiers); Vectorize storage ~$0.016/mo over the 10M included. **Dominant cost = the $5/mo Workers Paid base**, which also lifts the whole app's limits.

## 10. Open items / risks

- **Relevance on short figurative text** is noisier than on prose → mitigated by the tunable score cutoff and by showing scores; the cutoff default is set during the build smoke test.
- **Selective filters + post-retrieval filtering**: if a category/source filter is very narrow, topK=200 may under-fill; acceptable for v1, revisit topK if needed (logged, not silent).
- **Vectorize local-dev**: limited → tests mock bindings; correctness confirmed on preview.
- **`getByIds` returning values**: relies on Vectorize returning stored vectors for similar-search; if unavailable, fall back to re-embedding the proverb's text at request time (documented alternative).

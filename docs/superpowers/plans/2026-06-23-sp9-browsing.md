# verba — SP9: Browsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users browse past the 80-result cap (load-more) and discover proverbs one-at-a-time in a Tinder-style swipe overlay with a saved collection and basic sharing.

**Architecture:** Pure, environment-agnostic helpers go in `app/src/shared/browse.ts` (unit-tested in the existing Workers vitest pool). All DOM/gesture/`localStorage` glue lives in `app/src/client/main.ts` (verified on preview). Markup additions in `index.html`, styles in `styles.css`. No Worker/API changes.

**Tech Stack:** TypeScript + esbuild + vitest (`@cloudflare/vitest-pool-workers`) + the existing vanilla-TS PWA. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-23-sp9-browsing-design.md`

## Global Constraints

- No new npm dependencies; no Worker/API changes. Client-only.
- Pure logic (`isPresentable`, `deckFor`, `toggleSaved`, `nextShown`) lives in `app/src/shared/browse.ts` and is unit-tested; impure glue stays in `main.ts`.
- `localStorage` key for saved ids: **`verba:saved`** = JSON `string[]`, newest-first. All storage access wrapped in try/catch (private mode degrades gracefully, never throws).
- Load-more step = **80**; reset to 80 on every new query/filter; head shows **«показано N з M»**; button text **«Показати ще»**, hidden when `shown ≥ M`.
- Swipe: right/`→`/♥ = save, left/`←`/✕ = skip (skips not remembered). Touch (Pointer Events) + keyboard + buttons. Deck = current results if filtering else the presentable pool, shuffled, endless (reshuffle near the end). `Esc` closes; focus trapped; body scroll locked while open; animations gated behind `prefers-reduced-motion: no-preference`.
- Saved surfaced as a **«♥ Збережені (N)»** control that renders saved proverbs (newest-first) as the list, with remove. Count updates live.
- Share: `navigator.share({title:"Українське прислів'я", text:p.text, url: location.origin})`; else clipboard `p.text + " — " + location.origin` with "скопійовано ✓"; final fallback opens the homepage.
- All UI uses theme CSS vars (light + dark), visible keyboard focus, Ukrainian copy. Commit identity `MurzikVasilyevich`; session footer. Branch `feat/browsing`. Push: origin via `gh auth switch --user MurzikVasilyevich`; dmytro via SSH. Deploy is **outward — confirm with user**.
- **Task types:** `[IMPL]` TDD · `[CONTROLLER-RUN]` controller (preview, deploy).

---

### Task 1 [IMPL]: `shared/browse.ts` — pure browsing helpers

**Files:** Create `app/src/shared/browse.ts`, `app/test/browse.test.ts`.

**Interfaces — Produces:**
- `isPresentable(text: string): boolean`
- `deckFor(proverbs: Proverb[], opts: { category?: string; source?: string; presentableOnly?: boolean }): Proverb[]`
- `toggleSaved(ids: string[], id: string): string[]` — newest-first; removes if present, else prepends. Returns a NEW array.
- `nextShown(shown: number, step: number, total: number): number`

- [ ] **Step 1: Write the failing test** — `app/test/browse.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { isPresentable, deckFor, toggleSaved, nextShown } from "../src/shared/browse";
import { type Proverb } from "../src/shared/corpus";

const mk = (id: string, over: Partial<Proverb> = {}): Proverb => ({
  id, text: "Без труда нема плода", modern_text: "Без труда нема плода",
  category: ["work_labor"], sources: ["Franko1901"], variant_group: "", ...over,
});

describe("isPresentable", () => {
  it("accepts a clean proverb", () => expect(isPresentable("Без труда нема плода")).toBe(true));
  it("rejects too short", () => expect(isPresentable("Ні.")).toBe(false));
  it("rejects lowercase initial", () => expect(isPresentable("без труда нема плода")).toBe(false));
  it("rejects under 4 words", () => expect(isPresentable("Тут добре жить")).toBe(false));
});
describe("deckFor", () => {
  const ps = [mk("p1", { category: ["animals"] }), mk("p2", { sources: ["Nomis1864"] }), mk("p3", { text: "ой" })];
  it("filters by category", () => expect(deckFor(ps, { category: "animals" }).map((p) => p.id)).toEqual(["p1"]));
  it("filters by source", () => expect(deckFor(ps, { source: "Nomis1864" }).map((p) => p.id)).toEqual(["p2"]));
  it("presentableOnly drops fragments", () => expect(deckFor(ps, { presentableOnly: true }).some((p) => p.id === "p3")).toBe(false));
  it("returns all with no opts and does not mutate", () => { const r = deckFor(ps, {}); expect(r.length).toBe(3); expect(ps.length).toBe(3); });
});
describe("toggleSaved", () => {
  it("prepends when absent", () => expect(toggleSaved(["a"], "b")).toEqual(["b", "a"]));
  it("removes when present", () => expect(toggleSaved(["b", "a"], "b")).toEqual(["a"]));
  it("does not mutate input", () => { const i = ["a"]; toggleSaved(i, "b"); expect(i).toEqual(["a"]); });
});
describe("nextShown", () => {
  it("increments by step", () => expect(nextShown(80, 80, 500)).toBe(160));
  it("clamps at total", () => expect(nextShown(80, 80, 100)).toBe(100));
});
```

- [ ] **Step 2: Run, verify fail** — from `app/`: `npx vitest run test/browse.test.ts` → FAIL.

- [ ] **Step 3: Implement** — `app/src/shared/browse.ts`:
```typescript
import { type Proverb } from "./corpus";

export function isPresentable(text: string): boolean {
  const t = text.trim();
  return t.length >= 18 && t.length <= 90 && t.split(/\s+/).length >= 4 && /^[А-ЯІЇЄҐ]/.test(t);
}

export function deckFor(
  proverbs: Proverb[],
  opts: { category?: string; source?: string; presentableOnly?: boolean },
): Proverb[] {
  return proverbs.filter((p) =>
    (!opts.category || p.category.includes(opts.category)) &&
    (!opts.source || p.sources.includes(opts.source)) &&
    (!opts.presentableOnly || isPresentable(p.text)));
}

export function toggleSaved(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [id, ...ids];
}

export function nextShown(shown: number, step: number, total: number): number {
  return Math.min(shown + step, total);
}
```

- [ ] **Step 4: Run, verify pass** — `npx vitest run test/browse.test.ts` → PASS.

- [ ] **Step 5: Commit**
```bash
git add app/src/shared/browse.ts app/test/browse.test.ts
git commit -m "feat(browse): pure helpers — isPresentable, deckFor, toggleSaved, nextShown"
```

---

### Task 2 [IMPL]: Load-more for the result list

**Files:** Modify `app/src/client/main.ts`, `app/public/index.html`, `app/public/styles.css`.

**Interfaces:** Consumes `isPresentable`, `nextShown` (Task 1). Introduces module helper `showResults(results, head, showScore)` and `renderPage()` used by Task 3/4.

- [ ] **Step 1: Import from browse.ts + add a byId map + remove the local duplicate** — in `main.ts`:
  - Change the corpus import line to also pull browse helpers:
```typescript
import { searchProverbs, type Proverb } from "../shared/corpus";
import { isPresentable, deckFor, toggleSaved, nextShown } from "../shared/browse";
```
  - DELETE the local `function isPresentable(p: Proverb)` (lines ~42–46) — calls now pass `p.text`. Update its two call sites: `all.filter(isPresentable)` → `all.filter((p) => isPresentable(p.text))` (in `boot`), and the hero `sample(presentable.length ? presentable : all, 1)` is unaffected.
  - In `boot`, after `all = proverbs;` add a lookup map: `byId = new Map(all.map((p) => [p.id, p]));` and declare it with the other state: `let byId = new Map<string, Proverb>();`. Replace the three `all.find((x) => x.id === …)` lookups (in the entry click, similar-li click, and saved — added later) with `byId.get(…)`.

- [ ] **Step 2: Add load-more state + `showResults`/`renderPage`, and route `renderResults` through them** — replace `paintEntries` (lines ~174–199) with:
```typescript
let pageResults: Array<Proverb & { score?: number }> = [];
let pageHead = "";
let pageShowScore = false;
let shown = 80;
const STEP = 80;

function showResults(results: Array<Proverb & { score?: number }>, head: string, showScore: boolean) {
  pageResults = results; pageHead = head; pageShowScore = showScore; shown = Math.min(STEP, results.length || STEP);
  renderPage();
}

function renderPage() {
  if (!pageResults.length) {
    $("results").innerHTML = `<p class="empty">Нічого не знайдено. Спробуйте інше слово або зніміть фільтри.</p>`;
    return;
  }
  const page = pageResults.slice(0, shown);
  const more = shown < pageResults.length;
  $("results").innerHTML =
    `<p class="results-head">${esc(pageHead)} · показано ${fmt(page.length)} з ${fmt(pageResults.length)}</p>` +
    page.map((p) =>
      `<article class="entry" data-id="${esc(p.id)}">
        <div class="entry-cat">№&nbsp;${esc(p.id.replace(/^p0*/, ""))}${pageShowScore && p.score !== undefined ? `<br><span class="entry-score">${p.score.toFixed(2)}</span>` : ""}</div>
        <div>
          <div class="entry-text">${esc(p.text)}</div>
          ${differs(p) ? `<div class="entry-modern">${esc(p.modern_text)}</div>` : ""}
          <div class="entry-tags">
            ${p.category.map((c) => `<span class="tag">${esc(catLabel(c))}</span>`).join("")}
            <span class="tag-src">${esc(p.sources.map(srcLabel).join(" · "))}</span>
          </div>
        </div>
      </article>`).join("") +
    (more ? `<button id="moreBtn" class="more-btn" type="button">Показати ще</button>` : "");
  for (const el of Array.from(document.querySelectorAll<HTMLElement>(".entry"))) {
    el.addEventListener("click", () => { const p = byId.get(el.dataset.id!); if (p) openDetail(p); });
  }
  const moreBtn = $("moreBtn") as HTMLButtonElement | null;
  if (moreBtn) moreBtn.addEventListener("click", () => { shown = nextShown(shown, STEP, pageResults.length); renderPage(); });
}
```

- [ ] **Step 3: Make `renderResults` build the FULL result set (no 80 cap) and call `showResults`** — in `renderResults`:
  - Semantic branch: change `&limit=80` → `&limit=100`, and replace `paintEntries(data.results, "За змістом", true);` → `showResults(data.results, "За змістом", true);`
  - Landing (`!filtering`): replace `paintEntries(results, head, false)` path — set `showResults(landingSample, "Навмання з корпусу", false)` and `$("count").textContent = `${fmt(meta.count)} всього`;` then `return`.
  - Filtering branch: replace the `searchProverbs(..., limit: 80)` block with a direct, unbounded filter so load-more can page through everything:
```typescript
    let resultsAll = pool;
    if (activeCat) resultsAll = resultsAll.filter((p) => p.category.includes(activeCat));
    if (activeSource) resultsAll = resultsAll.filter((p) => p.sources.includes(activeSource));
    $("count").textContent = `Знайдено ${fmt(resultsAll.length)}`;
    showResults(resultsAll, "Результати", false);
```
  (The `searchProverbs` import may now be unused — if TypeScript/esbuild flags it, remove it from the import. Keep `Proverb`.)

- [ ] **Step 4: Styles** — append to `app/public/styles.css`:
```css
.more-btn { display: block; margin: 1.4rem auto 0; font-family: var(--sans); font-size: .82rem; letter-spacing: .02em;
  cursor: pointer; background: none; border: 1px solid var(--rule); color: var(--ink); border-radius: 999px; padding: .55rem 1.4rem;
  transition: background .15s, color .15s, border-color .15s; }
.more-btn:hover { background: var(--willow); color: #fff; border-color: var(--willow); }
```

- [ ] **Step 5: Fix the eyebrow plural in `index.html`** — line ~37: change `записи</p>` to `записів</p>` (48 787 takes the genitive plural; matches the colophon's `plural()` output).

- [ ] **Step 6: Build + verify** — from `app/`: `node build.mjs` → `Built public/app.js`, no errors. (`npx vitest run` stays green — no test touches this glue.)

- [ ] **Step 7: Commit**
```bash
git add app/src/client/main.ts app/public/styles.css app/public/index.html
git commit -m "feat(browse): «Показати ще» load-more past the 80-cap + N з M count"
```

---

### Task 3 [IMPL]: Saved store + «♥ Збережені» view

**Files:** Modify `app/src/client/main.ts`, `app/public/index.html`, `app/public/styles.css`.

**Interfaces:** Consumes `toggleSaved` (Task 1), `showResults`/`byId` (Task 2). Produces `setSaved(id)`, `isSavedId(id)`, `updateSavedCount()` used by Task 4.

- [ ] **Step 1: Saved store + view state** — in `main.ts`, add state near the other `let`s:
```typescript
let saved: string[] = loadSaved();
let savedView = false;
```
  and helpers (near `boot`):
```typescript
function loadSaved(): string[] {
  try { const v = JSON.parse(localStorage.getItem("verba:saved") || "[]"); return Array.isArray(v) ? v : []; } catch { return []; }
}
function persistSaved() { try { localStorage.setItem("verba:saved", JSON.stringify(saved)); } catch {} }
function isSavedId(id: string): boolean { return saved.includes(id); }
function setSaved(id: string) {
  saved = toggleSaved(saved, id); persistSaved(); updateSavedCount();
  if (savedView) renderSavedView();
}
function updateSavedCount() {
  const b = $("savedBtn"); if (b) b.textContent = `♥ Збережені (${saved.length})`;
}
function renderSavedView() {
  const items = saved.map((id) => byId.get(id)).filter(Boolean) as Proverb[];
  $("count").textContent = `Збережено ${fmt(items.length)}`;
  showResults(items, "Збережені", false);
}
```

- [ ] **Step 2: Wire the «♥ Збережені» control** — in `boot`, after the semantic-toggle wiring, add:
```typescript
  updateSavedCount();
  $("savedBtn").addEventListener("click", () => {
    savedView = !savedView;
    $("savedBtn").classList.toggle("active", savedView);
    if (savedView) renderSavedView(); else renderResults();
  });
```
  Add to `renderResults` (very top, after `const seq`): `if (savedView) { renderSavedView(); return; }` — but the SEARCH input/filter clicks should exit saved view. Simpler: in the `q` input listener and each chip click, set `savedView = false; $("savedBtn").classList.remove("active");` before `renderResults()`. Add that line to: the `#q` input debounced handler (wrap: `() => { savedView = false; $("savedBtn").classList.remove("active"); renderResults(); }`), and inside `renderFilters`'s chip click handler before `renderResults()`.

- [ ] **Step 3: Add remove-in-place from the saved view** — in `renderPage`, after building entries, when `savedView` is active each entry shows a remove control. Add (inside `renderPage`, only when `savedView`): append to each entry a button is heavier; instead, make a click in saved view remove. Simplest: add a small ♥ toggle to every entry's tags row. In `renderPage`, change the `.entry-tags` line to include a save toggle:
```typescript
            <button class="entry-save${isSavedId(p.id) ? " on" : ""}" type="button" data-save="${esc(p.id)}" aria-label="Зберегти" aria-pressed="${isSavedId(p.id)}">♥</button>
```
  and after wiring `.entry` clicks in `renderPage`, wire the save buttons (and stop propagation so saving doesn't open the detail):
```typescript
  for (const b of Array.from(document.querySelectorAll<HTMLElement>(".entry-save"))) {
    b.addEventListener("click", (e) => { e.stopPropagation(); setSaved(b.dataset.save!); b.classList.toggle("on"); b.setAttribute("aria-pressed", String(isSavedId(b.dataset.save!))); if (savedView) renderSavedView(); });
  }
```

- [ ] **Step 4: Markup** — in `index.html`, add the control inside `.search-wrap` after the `semToggle` button:
```html
      <button id="savedBtn" class="saved-btn" type="button">♥ Збережені (0)</button>
```

- [ ] **Step 5: Styles** — append to `styles.css`:
```css
.saved-btn { font-family: var(--sans); font-size: .76rem; letter-spacing: .02em; cursor: pointer; background: none;
  border: 1px solid var(--rule); color: var(--muted); border-radius: 999px; padding: .25rem .7rem; white-space: nowrap;
  transition: background .12s, color .12s, border-color .12s; }
.saved-btn.active, .saved-btn:hover { border-color: var(--willow); color: var(--willow); }
.entry-save { background: none; border: none; cursor: pointer; color: var(--faint); font-size: .95rem; line-height: 1; padding: 0 .2rem; transition: color .12s; }
.entry-save:hover { color: var(--willow); }
.entry-save.on { color: var(--willow); }
```

- [ ] **Step 6: Build + verify** — `node build.mjs` → clean. Manual note: saving an entry, reload, «♥ Збережені» lists it.

- [ ] **Step 7: Commit**
```bash
git add app/src/client/main.ts app/public/index.html app/public/styles.css
git commit -m "feat(browse): saved collection (localStorage) + «♥ Збережені» view + per-entry ♥"
```

---

### Task 4 [IMPL]: Swipe discovery overlay + share

**Files:** Modify `app/src/client/main.ts`, `app/public/index.html`, `app/public/styles.css`.

**Interfaces:** Consumes `deckFor`, `isPresentable` (Task 1), `setSaved`/`isSavedId` (Task 3), `openDetail`, `presentable`, `byId`. Produces `share(p)`, `openSwipe()`.

- [ ] **Step 1: `share` helper** — in `main.ts`:
```typescript
async function share(p: Proverb) {
  const url = location.origin;
  if (navigator.share) { try { await navigator.share({ title: "Українське прислів'я", text: p.text, url }); } catch {} return; }
  try { await navigator.clipboard.writeText(`${p.text} — ${url}`); flash("Скопійовано ✓"); }
  catch { window.open(url, "_blank"); }
}
let flashT: number;
function flash(msg: string) {
  let el = $("flash"); if (!el) { el = document.createElement("div"); el.id = "flash"; el.className = "flash"; document.body.appendChild(el); }
  el.textContent = msg; el.classList.add("show"); clearTimeout(flashT);
  flashT = setTimeout(() => el!.classList.remove("show"), 1400) as unknown as number;
}
```

- [ ] **Step 2: Swipe overlay logic** — in `main.ts`:
```typescript
let deck: Proverb[] = [];
let deckI = 0;
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

function buildDeck(): Proverb[] {
  const q = ($("q") as HTMLInputElement).value.trim();
  const filtering = !!(q || activeCat || activeSource) && !savedView;
  const base = savedView ? (saved.map((id) => byId.get(id)).filter(Boolean) as Proverb[])
    : filtering ? pageResults : presentable;
  const pool = base.length ? base : presentable;
  return sample(pool, pool.length); // shuffle all
}

function openSwipe() {
  deck = buildDeck(); deckI = 0;
  if (!deck.length) return;
  document.body.classList.add("swipe-open");
  const ov = $("swipe"); ov.hidden = false;
  renderSwipeCard();
  $("swipeClose").focus();
}
function closeSwipe() {
  $("swipe").hidden = true; document.body.classList.remove("swipe-open");
}
function advance(dir: 1 | -1) {
  const card = $("swipeCard");
  const done = () => { deckI++; if (deck.length - deckI < 5) { deck = deck.concat(buildDeck()); } renderSwipeCard(); };
  if (reduceMotion) { done(); return; }
  card.style.transition = "transform .28s ease, opacity .28s ease";
  card.style.transform = `translateX(${dir * 120}%) rotate(${dir * 12}deg)`;
  card.style.opacity = "0";
  setTimeout(() => { card.style.transition = "none"; card.style.transform = ""; card.style.opacity = "1"; done(); }, 280);
}
function saveCurrent() { const p = deck[deckI]; if (p && !isSavedId(p.id)) setSaved(p.id); }

function renderSwipeCard() {
  const p = deck[deckI]; if (!p) { closeSwipe(); return; }
  const inner = $("swipeCard");
  inner.innerHTML =
    `<div class="sw-cat">№&nbsp;${esc(p.id.replace(/^p0*/, ""))}</div>
     <p class="sw-text">${esc(p.text)}</p>
     ${differs(p) ? `<p class="sw-modern">${esc(p.modern_text)}</p>` : ""}
     <div class="sw-tags">${p.category.map((c) => `<span class="tag">${esc(catLabel(c))}</span>`).join("")}<span class="tag-src">${esc(p.sources.map(srcLabel).join(" · "))}</span></div>`;
  inner.onclick = (e) => { if ((e.target as HTMLElement).closest(".sw-actions")) return; openDetail(p); };
  $("swSave").setAttribute("aria-pressed", String(isSavedId(p.id)));
  $("swSave").classList.toggle("on", isSavedId(p.id));
}
```

- [ ] **Step 3: Pointer drag + buttons + keyboard wiring** — in `boot`, add (after the saved wiring):
```typescript
  $("swipeBtn").addEventListener("click", openSwipe);
  $("swipeClose").addEventListener("click", closeSwipe);
  $("swSkip").addEventListener("click", () => advance(-1));
  $("swSave").addEventListener("click", () => { saveCurrent(); renderSwipeCard(); advance(1); });
  $("swShare").addEventListener("click", () => { const p = deck[deckI]; if (p) share(p); });
  document.addEventListener("keydown", (e) => {
    if ($("swipe").hidden) return;
    if (e.key === "Escape") closeSwipe();
    else if (e.key === "ArrowRight") { saveCurrent(); advance(1); }
    else if (e.key === "ArrowLeft") advance(-1);
  });
  // touch / pointer drag
  const card = $("swipeCard");
  let sx = 0, dx = 0, dragging = false;
  card.addEventListener("pointerdown", (e) => { dragging = true; sx = e.clientX; dx = 0; card.style.transition = "none"; card.setPointerCapture(e.pointerId); });
  card.addEventListener("pointermove", (e) => { if (!dragging) return; dx = e.clientX - sx; card.style.transform = `translateX(${dx}px) rotate(${dx / 28}deg)`; });
  card.addEventListener("pointerup", () => {
    if (!dragging) return; dragging = false;
    const threshold = card.offsetWidth * 0.25;
    if (dx > threshold) { saveCurrent(); advance(1); }
    else if (dx < -threshold) advance(-1);
    else { card.style.transition = "transform .2s ease"; card.style.transform = ""; }
  });
```

- [ ] **Step 4: Add «Поділитися» to the detail dialog** — in `openDetail`, change the close-button line of the form template to include a share button before it:
```typescript
      <div class="detail-share"><button class="detail-sharebtn" type="button">Поділитися</button></div>
      <button class="detail-close" type="submit" value="close">Закрити</button>
```
  and after `dlg.showModal();` (or right before it), wire it:
```typescript
  const sb = dlg.querySelector<HTMLButtonElement>(".detail-sharebtn");
  if (sb) sb.addEventListener("click", () => share(p));
```

- [ ] **Step 5: Markup** — in `index.html`:
  - Add the «Гортати» button inside `.search-wrap`, after `savedBtn`:
```html
      <button id="swipeBtn" class="swipe-btn" type="button">Гортати ⇆</button>
```
  - Add the overlay before the `<dialog id="detail" …>` line:
```html
  <div id="swipe" class="swipe" role="dialog" aria-modal="true" aria-label="Гортати прислів'я" hidden>
    <button id="swipeClose" class="sw-close" type="button" aria-label="Закрити">✕</button>
    <div id="swipeCard" class="sw-card"></div>
    <div class="sw-actions">
      <button id="swSkip" class="sw-act sw-skip" type="button" aria-label="Пропустити">✕</button>
      <button id="swShare" class="sw-act sw-share" type="button" aria-label="Поділитися">↗</button>
      <button id="swSave" class="sw-act sw-savebtn" type="button" aria-label="Зберегти" aria-pressed="false">♥</button>
    </div>
    <p class="sw-hint">Гортайте, або ← пропустити · зберегти →</p>
  </div>
```

- [ ] **Step 6: Styles** — append to `styles.css`:
```css
.swipe-btn { font-family: var(--sans); font-size: .76rem; letter-spacing: .02em; cursor: pointer; background: var(--willow);
  color: #fff; border: 1px solid var(--willow); border-radius: 999px; padding: .25rem .8rem; white-space: nowrap; }
.swipe-btn:hover { background: var(--willow-deep); border-color: var(--willow-deep); }
body.swipe-open { overflow: hidden; }
.swipe[hidden] { display: none; }
.swipe { position: fixed; inset: 0; z-index: 50; background: var(--paper); display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 1.5rem; padding: 1.5rem; }
.sw-close { position: absolute; top: 1rem; right: 1rem; width: 40px; height: 40px; border-radius: 999px;
  border: 1px solid var(--rule); background: var(--paper-2); color: var(--muted); cursor: pointer; font-size: 1rem; }
.sw-card { max-width: 600px; width: 100%; background: var(--paper-2); border: 1px solid var(--rule); border-radius: 12px;
  padding: clamp(1.8rem, 6vw, 3rem); cursor: pointer; touch-action: pan-y; box-shadow: 0 18px 50px rgba(0,0,0,.12); }
.sw-cat { font-family: var(--mono); font-size: .72rem; color: var(--faint); }
.sw-text { font-family: var(--serif); font-weight: 500; font-size: clamp(1.5rem, 5vw, 2.3rem); line-height: 1.2; margin: .6rem 0 0; }
.sw-modern { font-family: var(--serif); font-style: italic; color: var(--muted); margin: .7rem 0 0; }
.sw-tags { margin-top: 1rem; display: flex; flex-wrap: wrap; gap: .35rem .8rem; align-items: center; }
.sw-actions { display: flex; gap: 1.1rem; }
.sw-act { width: 56px; height: 56px; border-radius: 999px; border: 1px solid var(--rule); background: var(--paper-2);
  cursor: pointer; font-size: 1.3rem; line-height: 1; color: var(--muted); transition: transform .12s, color .12s, border-color .12s; }
.sw-act:hover { transform: translateY(-2px); }
.sw-save { color: #b4543f; } .sw-savebtn.on { color: #fff; background: var(--willow); border-color: var(--willow); }
.sw-share { color: var(--willow); }
.sw-hint { font-family: var(--sans); font-size: .74rem; color: var(--faint); margin: 0; }
.detail-share { margin-top: 1.2rem; }
.detail-sharebtn { font-family: var(--sans); font-size: .82rem; cursor: pointer; background: none; border: 1px solid var(--willow);
  color: var(--willow); border-radius: 999px; padding: .45rem 1.1rem; }
.detail-sharebtn:hover { background: var(--willow); color: #fff; }
.flash { position: fixed; bottom: 1.4rem; left: 50%; transform: translateX(-50%) translateY(1rem); z-index: 60;
  background: var(--ink); color: var(--paper); font-family: var(--sans); font-size: .82rem; padding: .55rem 1.1rem;
  border-radius: 999px; opacity: 0; pointer-events: none; transition: opacity .2s, transform .2s; }
.flash.show { opacity: 1; transform: translateX(-50%) translateY(0); }
```

- [ ] **Step 7: Build + verify** — `node build.mjs` → clean. `npx vitest run` → green.

- [ ] **Step 8: Commit**
```bash
git add app/src/client/main.ts app/public/index.html app/public/styles.css
git commit -m "feat(browse): Tinder-style swipe overlay (save/skip/share) + detail share"
```

---

### Task 5 [CONTROLLER-RUN]: SW bump, preview, smoke, deploy, finish

Controller-run. Deploy is **outward — confirm with user**.

- [ ] **Step 1:** Bump `app/public/sw.js` `CACHE` (v7 → v8).
- [ ] **Step 2:** `cd app && node build.mjs && npx vitest run` (all green) `&& npx wrangler versions upload`.
- [ ] **Step 3: Smoke on the preview URL** (desktop + mobile, light + dark):
  - Load-more: a broad search/filter → «Показати ще» pages to the end; head shows «N з M»; button hides at the end; semantic search caps at 100.
  - Swipe: «Гортати» opens; drag right saves (♥ count rises), drag left skips; ← → / ✕ / ♥ buttons work; ↗ shares (sheet or "Скопійовано ✓"); tapping the card opens the detail; `Esc` closes; deck keeps going (reshuffle).
  - Saved: ♥ on an entry + in swipe; reload → «♥ Збережені (N)» lists them newest-first; remove works.
  - Detail: «Поділитися» works. Reduced-motion: cards advance without fly-off.
- [ ] **Step 4: Deploy** (confirm with user) — `npx wrangler deploy`; smoke the same on verbacorpus.org.
- [ ] **Step 5: Finish** — controller merges `feat/browsing` → main, pushes both remotes; updates memory. (README's "Web app" line already covers browsing implicitly; add a one-line note if warranted.)

---

## Self-Review

**1. Spec coverage:** §2 load-more → Task 2 (shown/STEP, «показано N з M», semantic cap 100, hidden at end). §3 swipe (entry, deck respects filters else presentable + shuffle + endless, card, save/skip via touch+keyboard+buttons, tap→detail) → Task 4 (+ `deckFor`/`sample` from Tasks 1/2). §4 saved (localStorage `verba:saved`, `toggleSaved`, «♥ Збережені (N)» view + remove, live count) → Task 3. §5 share → Task 4 (`share()` on swipe card + detail). §6 components (`shared/browse.ts`, main.ts glue, index.html, styles.css, sw bump) → Tasks 1–5. §7 testing (pure units; manual preview) → Tasks 1, 5. §8 a11y/theming (role=dialog, Esc, focus, keyboard-complete, theme vars, reduced-motion) → Task 4 + global constraints. §9 deploy → Task 5. §10 risks (touch vs scroll → `touch-action: pan-y` + horizontal-dominant drag + body lock; localStorage try/catch; semantic ceiling) → Tasks 3/4. ✓ Bonus: eyebrow «записи»→«записів» (Task 2 Step 5).

**2. Placeholder scan:** complete code for browse.ts + tests, the load-more refactor, saved store, swipe overlay, share, and all markup/styles. No TBD / vague error handling — storage is try/caught, empty states specified.

**3. Type consistency:** `isPresentable(text:string)`, `deckFor(...)`, `toggleSaved(ids:string[],id)`, `nextShown(...)` identical between Task 1 (def) and Tasks 2–4 (use). `showResults`/`renderPage`/`pageResults`/`byId` defined in Task 2 and used by Tasks 3–4. `setSaved`/`isSavedId`/`updateSavedCount`/`renderSavedView` defined in Task 3, used in Task 4. `share(p)`/`openSwipe`/`buildDeck`/`advance`/`saveCurrent`/`renderSwipeCard` all defined and wired in Task 4. Element ids (`savedBtn`, `swipeBtn`, `swipe`, `swipeCard`, `swipeClose`, `swSkip`, `swSave`, `swShare`) match between `index.html` (Task 3/4 markup) and the `main.ts` wiring.

**Note for the implementer (Task 2):** removing the local `isPresentable(p: Proverb)` changes its signature to `isPresentable(p.text)` at call sites — there are two (`boot`'s `all.filter`, and confirm the hero/landing path). Update both; do not leave the old function.

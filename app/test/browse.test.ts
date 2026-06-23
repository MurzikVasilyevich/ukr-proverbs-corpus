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

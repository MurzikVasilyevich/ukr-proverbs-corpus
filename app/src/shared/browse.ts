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

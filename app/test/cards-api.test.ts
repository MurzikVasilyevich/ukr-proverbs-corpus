import { env, createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { describe, it, expect } from "vitest";
import worker from "../src/index";

async function call(path: string) {
  const ctx = createExecutionContext();
  const res = await worker.fetch(new Request("https://example.com" + path), env as any, ctx);
  await waitOnExecutionContext(ctx);
  return res;
}

describe("/p/:id", () => {
  it("serves HTML with per-proverb OG image", async () => {
    const res = await call("/p/p1");
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/html");
    const html = await res.text();
    expect(html).toContain('property="og:image"');
    expect(html).toContain("/card/p1.png");
    expect(html).toContain('name="twitter:card"');
  });
  it("404 for unknown id", async () => {
    expect((await call("/p/zzz")).status).toBe(404);
  });
});

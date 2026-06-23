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

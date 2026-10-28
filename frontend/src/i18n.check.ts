// Every t("…") in the source has an English entry with the same {params}, and en.ts has no dead entries.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { EN } from "./en.ts";

const root = new URL("./", import.meta.url);
const files = readdirSync(root, { recursive: true, encoding: "utf8" }).filter((f) => /\.tsx?$/.test(f) && !/\.check\.ts$|^en\.ts$/.test(f));
const used = new Set<string>();
for (const f of files) {
  for (const m of readFileSync(new URL(f, root), "utf8").matchAll(/\bt\(\s*"((?:[^"\\]|\\.)*)"/g)) used.add(JSON.parse(`"${m[1]}"`));
}
const params = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
assert.ok(used.size > 250, `the scan found only ${used.size} texts`);
assert.deepEqual([...used].filter((k) => !(k in EN)), [], "texts without English");
assert.deepEqual([...used].filter((k) => k in EN && params(k) !== params(EN[k])), [], "different {params}");
assert.deepEqual(Object.keys(EN).filter((k) => !used.has(k)), [], "dead English entries");
console.log(`i18n.check: OK (${used.size} texts)`);

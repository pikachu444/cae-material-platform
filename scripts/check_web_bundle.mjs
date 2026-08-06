import { readdir, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repository = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const assets = join(repository, "apps", "web", "dist", "assets");
const entryBudget = Number(process.env.CMP_WEB_ENTRY_BUDGET_BYTES ?? 300_000);
const lazyChunkBudget = Number(process.env.CMP_WEB_LAZY_CHUNK_BUDGET_BYTES ?? 130_000);
const files = (await readdir(assets)).filter((name) => name.endsWith(".js"));

if (files.length === 0) {
  throw new Error(`No production JavaScript assets found below ${assets}`);
}

const results = await Promise.all(
  files.map(async (name) => {
    const sizeBytes = (await stat(join(assets, name))).size;
    const entry = /^index-[A-Za-z0-9_-]+\.js$/.test(name);
    const budgetBytes = entry ? entryBudget : lazyChunkBudget;
    return { budgetBytes, entry, name, passed: sizeBytes <= budgetBytes, sizeBytes };
  }),
);
const violations = results.filter((result) => !result.passed);
console.log(
  JSON.stringify({
    entryBudgetBytes: entryBudget,
    largestChunkBytes: Math.max(...results.map((result) => result.sizeBytes)),
    lazyChunkBudgetBytes: lazyChunkBudget,
    passed: violations.length === 0,
    violations,
  }),
);
if (violations.length > 0) {
  process.exitCode = 1;
}

import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const FIXTURE_PATH = "scripts/fixtures/issue-261-m6-zero-consumer-audit.json";
const OUTPUT_PATH = "docs/17-evidence/issue-261-m6-production-bundle.json";
const DIST_PATH = "apps/web/dist";
const fixture = JSON.parse(readFileSync(resolve(ROOT, FIXTURE_PATH), "utf8"));

function posix(path) { return path.split(sep).join("/"); }
function sha256(value) { return createHash("sha256").update(value).digest("hex"); }
function digest(value) { return sha256(JSON.stringify(value)); }
function collectFiles(directory) {
  return readdirSync(directory).sort().flatMap((name) => {
    const path = join(directory, name);
    return statSync(path).isDirectory() ? collectFiles(path) : [path];
  });
}
function escapeRegex(value) { return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
function countToken(source, token) {
  const pattern = new RegExp(`(^|[^A-Za-z0-9_-])${escapeRegex(token)}(?=$|[^A-Za-z0-9_-])`, "g");
  return [...source.matchAll(pattern)].length;
}

if (!existsSync(resolve(ROOT, DIST_PATH))) {
  throw new Error("production bundle is missing; run npm run build first");
}
const files = collectFiles(resolve(ROOT, DIST_PATH));
const nonCssSources = files
  .filter((path) => [".js", ".html"].includes(extname(path)))
  .map((absolute) => ({
    absolute,
    path: posix(relative(ROOT, absolute)),
    source: readFileSync(absolute, "utf8"),
  }));
const bundleFiles = files.map((absolute) => {
  const bytes = readFileSync(absolute);
  return {
    path: posix(relative(ROOT, absolute)),
    bytes: bytes.length,
    sha256: sha256(bytes),
  };
});
const evidenceCache = new Map();
function evidence(token) {
  if (!evidenceCache.has(token)) {
    evidenceCache.set(token, nonCssSources.flatMap((file) => {
      const occurrences = countToken(file.source, token);
      return occurrences ? [{ path: file.path, occurrences }] : [];
    }));
  }
  return evidenceCache.get(token);
}

const rows = fixture.auditRows.map((row) => ({
  handoffId: row.handoffId,
  selector: row.selector,
  subjectToken: row.staticEvidence.subjectToken,
  disposition: row.disposition,
  bundleBefore: row.bundleEvidence,
  bundleAfter: row.staticEvidence.subjectToken ? evidence(row.staticEvidence.subjectToken) : [],
}));
const errors = [];
for (const row of rows) {
  if (row.disposition === "REMOVE" && row.bundleAfter.length) {
    errors.push(`${row.handoffId} REMOVE acquired production-bundle evidence`);
  }
  if (row.disposition === "HOLD" && row.bundleBefore.length && !row.bundleAfter.length) {
    errors.push(`${row.handoffId} HOLD lost its production-bundle evidence and requires reclassification`);
  }
}
const output = {
  schemaVersion: "cmp.issue-261.m6.production-bundle.v1",
  unit: fixture.unit,
  baseSha: fixture.baseSha,
  handoff: fixture.handoff,
  method: fixture.method.bundle,
  bundleBefore: {
    files: fixture.bundleBefore.files.length,
    treeSha256: fixture.bundleBefore.treeSha256,
  },
  bundleAfter: {
    path: DIST_PATH,
    files: bundleFiles,
    treeSha256: digest(bundleFiles.map((file) => [file.path, file.sha256])),
    nonCssFilesAudited: nonCssSources.length,
  },
  coverage: {
    rows: rows.length,
    removeRows: rows.filter((row) => row.disposition === "REMOVE").length,
    holdRows: rows.filter((row) => row.disposition === "HOLD").length,
    removeRowsWithAfterEvidence: rows.filter((row) => row.disposition === "REMOVE" && row.bundleAfter.length).length,
    holdRowsWithPreservedBundleEvidence: rows.filter((row) => row.disposition === "HOLD" && row.bundleBefore.length && row.bundleAfter.length).length,
  },
  rows,
  result: errors.length ? "FAIL" : "PASS",
  errors,
};
const rendered = `${JSON.stringify(output, null, 2)}\n`;
if (errors.length) throw new Error(`M6 production-bundle audit failed: ${errors.join("; ")}`);
if (process.argv.includes("--write")) {
  writeFileSync(resolve(ROOT, OUTPUT_PATH), rendered, "utf8");
  console.log(`WROTE ${OUTPUT_PATH}`);
} else if (!existsSync(resolve(ROOT, OUTPUT_PATH))
    || readFileSync(resolve(ROOT, OUTPUT_PATH), "utf8") !== rendered) {
  throw new Error(`STALE ${OUTPUT_PATH}; rerun with --write after npm run build`);
}
console.log(JSON.stringify({ result: output.result, coverage: output.coverage }, null, 2));

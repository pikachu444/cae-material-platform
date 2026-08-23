import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { scanProject, validateBaseline } from "./check_frontend_guard.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const BASELINE_PATH = "apps/web/frontend-guard-baseline.json";
const FIXTURE_PATH = "scripts/fixtures/issue-261-m6-zero-consumer-audit.json";
const fixture = JSON.parse(readFileSync(resolve(ROOT, FIXTURE_PATH), "utf8"));
const baseline = JSON.parse(readFileSync(resolve(ROOT, BASELINE_PATH), "utf8"));
const touchedPaths = new Set(fixture.legacySources.map(({ path }) => path));
const exceptionRuleIds = new Set(baseline.exceptions.map(({ ruleId }) => ruleId));
const oldExceptionByKey = new Map(baseline.exceptions.map((entry) => [
  `${entry.ruleId}\0${entry.path}\0${entry.fingerprint}`,
  entry,
]));
const findings = await scanProject({ projectRoot: ROOT, baseline });
const scopeContains = (scope, path) => path === scope || path.startsWith(`${scope}/`);
const retainedExceptions = baseline.exceptions.filter((entry) => !touchedPaths.has(entry.path));
const synchronized = new Map();

for (const finding of findings) {
  if (!touchedPaths.has(finding.path) || !exceptionRuleIds.has(finding.ruleId)) continue;
  const key = `${finding.ruleId}\0${finding.path}\0${finding.fingerprint}`;
  if (!synchronized.has(key)) synchronized.set(key, []);
  synchronized.get(key).push(finding);
}

const synchronizedExceptions = [...synchronized.entries()].map(([key, group]) => {
  const previous = oldExceptionByKey.get(key);
  if (previous) return { ...previous, maxOccurrences: group.length };
  return {
    ruleId: group[0].ruleId,
    path: group[0].path,
    fingerprint: group[0].fingerprint,
    maxOccurrences: group.length,
    reason: "M6 preserves this exact audited HOLD declaration or selector in its truthful legacy owner without semantic, visual, or responsive normalization.",
    ownerIssue: "#261",
    removalCondition: "Remove only after the row-specific M6 HOLD condition resolves every static, production-bundle, and live-DOM signal to zero.",
  };
});

baseline.exceptions = [...retainedExceptions, ...synchronizedExceptions]
  .sort((left, right) => left.path.localeCompare(right.path)
    || left.ruleId.localeCompare(right.ruleId)
    || left.fingerprint.localeCompare(right.fingerprint));
for (const debt of baseline.debt) {
  debt.count = findings.filter((finding) => finding.ruleId === debt.ruleId
    && scopeContains(debt.scope, finding.path)).length;
}
baseline.sourceSha = fixture.baseSha;
for (const hotspot of baseline.hotspots) {
  if (!touchedPaths.has(hotspot.path)) continue;
  const source = readFileSync(resolve(ROOT, hotspot.path), "utf8");
  hotspot.baselineLines = Math.max(0, source.split(/\r?\n/).length - 1);
}

const errors = validateBaseline(baseline);
if (errors.length) throw new Error(`synchronized baseline is invalid: ${errors.join("; ")}`);
const rendered = `${JSON.stringify(baseline, null, 2)}\n`;
console.log(JSON.stringify({
  sourceSha: baseline.sourceSha,
  touchedPaths: touchedPaths.size,
  retainedExceptions: retainedExceptions.length,
  synchronizedExceptions: synchronizedExceptions.length,
  totalExceptions: baseline.exceptions.length,
  debt: Object.fromEntries(baseline.debt.map((entry) => [`${entry.ruleId}:${entry.scope}`, entry.count])),
  hotspots: Object.fromEntries(baseline.hotspots
    .filter((entry) => touchedPaths.has(entry.path))
    .map((entry) => [entry.path, entry.baselineLines])),
}, null, 2));
if (process.argv.includes("--write")) {
  writeFileSync(resolve(ROOT, BASELINE_PATH), rendered, "utf8");
  console.log(`WROTE ${BASELINE_PATH}`);
} else if (readFileSync(resolve(ROOT, BASELINE_PATH), "utf8") !== rendered) {
  throw new Error(`STALE ${BASELINE_PATH}; rerun this M6 synchronizer with --write`);
} else {
  console.log(`PASS ${BASELINE_PATH}`);
}

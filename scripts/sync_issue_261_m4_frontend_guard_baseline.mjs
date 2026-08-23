import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { scanProject, validateBaseline } from "./check_frontend_guard.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const BASELINE_PATH = "apps/web/frontend-guard-baseline.json";
const FIXTURE_PATH = "scripts/fixtures/issue-261-m4-shared-css-ownership.json";
const fixture = JSON.parse(readFileSync(resolve(ROOT, FIXTURE_PATH), "utf8"));
const baselineText = readFileSync(resolve(ROOT, BASELINE_PATH), "utf8");
const baseline = JSON.parse(baselineText);
const touchedPaths = new Set([
  ...fixture.legacySources.map(({ path }) => path),
  ...Object.values(fixture.owners).map(({ path }) => path),
  ...Object.values(fixture.ownerCompanions ?? {}),
]);
const exceptionRuleIds = new Set(baseline.exceptions.map(({ ruleId }) => ruleId));
const findings = await scanProject({ projectRoot: ROOT, baseline });

function scopeContains(scope, path) {
  return path === scope || path.startsWith(`${scope}/`);
}

const oldExceptionByKey = new Map(baseline.exceptions.map((entry) => [
  `${entry.ruleId}\0${entry.path}\0${entry.fingerprint}`,
  entry,
]));
const retainedExceptions = baseline.exceptions.filter((entry) => !touchedPaths.has(entry.path));
const movedFindingGroups = new Map();
for (const finding of findings) {
  if (!touchedPaths.has(finding.path) || !exceptionRuleIds.has(finding.ruleId)) continue;
  const key = `${finding.ruleId}\0${finding.path}\0${finding.fingerprint}`;
  if (!movedFindingGroups.has(key)) movedFindingGroups.set(key, []);
  movedFindingGroups.get(key).push(finding);
}
const synchronizedExceptions = [...movedFindingGroups.entries()].map(([key, group]) => {
  const prior = oldExceptionByKey.get(key);
  if (prior) return { ...prior, maxOccurrences: group.length };
  return {
    ruleId: group[0].ruleId,
    path: group[0].path,
    fingerprint: group[0].fingerprint,
    maxOccurrences: group.length,
    reason: "FE-06 M4 moves this exact declaration or selector into its truthful owner without semantic, visual, or responsive normalization.",
    ownerIssue: "#261",
    removalCondition: "Remove when a separately approved semantic-token or legacy-selector retirement unit eliminates this preserved finding.",
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
  if (hotspot.path === "apps/web/src/styles.css") hotspot.baselineLines = 3922;
  if (hotspot.path === "apps/web/src/design/layout.css") hotspot.baselineLines = 3767;
}

const errors = validateBaseline(baseline);
if (errors.length) throw new Error(`synchronized baseline is invalid: ${errors.join("; ")}`);
const baseBaseline = JSON.parse(execFileSync(
  "git",
  ["show", `${fixture.baseSha}:${BASELINE_PATH}`],
  { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
));
const exceptionKey = (entry) => `${entry.ruleId}\0${entry.path}\0${entry.fingerprint}`;
const currentKeys = new Set(baseline.exceptions.map(exceptionKey));
const baseKeys = new Set(baseBaseline.exceptions.map(exceptionKey));
const removed = [...baseKeys].filter((key) => !currentKeys.has(key)).sort();
const added = [...currentKeys].filter((key) => !baseKeys.has(key)).sort();
const digest = (values) => createHash("sha256").update(JSON.stringify(values)).digest("hex");
const guardDelta = {
  removedCount: removed.length,
  addedCount: added.length,
  removedSha256: digest(removed),
  addedSha256: digest(added),
};
if (JSON.stringify(guardDelta) !== JSON.stringify(fixture.frontendGuardDelta)) {
  throw new Error(`frontend guard delta changed: ${JSON.stringify(guardDelta)}`);
}
const rendered = `${JSON.stringify(baseline, null, 2)}\n`;
console.log(JSON.stringify({
  sourceSha: baseline.sourceSha,
  touchedPaths: touchedPaths.size,
  retainedExceptions: retainedExceptions.length,
  synchronizedExceptions: synchronizedExceptions.length,
  totalExceptions: baseline.exceptions.length,
  guardDelta,
  debt: Object.fromEntries(baseline.debt.map((entry) => [`${entry.ruleId}:${entry.scope}`, entry.count])),
}, null, 2));

if (process.argv.includes("--write")) {
  writeFileSync(resolve(ROOT, BASELINE_PATH), rendered, "utf8");
  console.log(`WROTE ${BASELINE_PATH}`);
} else if (baselineText !== rendered) {
  throw new Error(`STALE ${BASELINE_PATH}; rerun this exact M4 synchronizer with --write`);
} else {
  console.log(`PASS ${BASELINE_PATH}`);
}

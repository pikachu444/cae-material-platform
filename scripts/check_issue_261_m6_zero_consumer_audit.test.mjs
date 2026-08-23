import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const readJson = (path) => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));
const fixture = readJson("scripts/fixtures/issue-261-m6-zero-consumer-audit.json");
const inventory = readJson("docs/17-evidence/issue-261-css-selector-inventory.json");
const bundle = readJson("docs/17-evidence/issue-261-m6-production-bundle.json");
const visualRoot = "docs/17-evidence/images/issue-261-m6-zero-consumer-audit-and-removal/live";
const beforeRuntime = readJson(`${visualRoot}/selector-runtime-before.json`);
const afterRuntime = readJson(`${visualRoot}/selector-runtime-after.json`);
const manifest = readJson(`${visualRoot}/manifest.json`);

function digest(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

test("M6 freezes and completely partitions the PR #318 556-row / 495-group handoff", () => {
  assert.equal(fixture.schemaVersion, "cmp.issue-261.m6.zero-consumer-audit.v1");
  assert.equal(fixture.baseSha, "593dfd3dab3a22ec93bc9d9a078c05b6f1f1c329");
  assert.deepEqual(fixture.handoff, {
    rows: 556,
    groups: 495,
    tupleSha256: "41a6cda0826c330fbf430462e8dbfc0de8041f2cd9344baf9ce1c08c66ffc900",
  });
  assert.equal(fixture.auditRows.length, fixture.handoff.rows);
  assert.equal(new Set(fixture.auditRows.map((row) => row.handoffId)).size, fixture.handoff.rows);
  assert.equal(digest(fixture.auditRows.map((row) => row.handoffId)), digest([
    ...fixture.remove.handoffIds,
    ...fixture.hold.handoffIds,
  ].sort((left, right) => Number(left.slice(4)) - Number(right.slice(4)))));
  assert.equal(fixture.remove.rows, 511);
  assert.equal(fixture.remove.touchedGroups, 462);
  assert.equal(fixture.remove.fullyRemovedGroups, 452);
  assert.equal(fixture.remove.partiallyShrunkGroups, 10);
  assert.equal(fixture.hold.rows, 45);
  assert.equal(fixture.hold.groups, 43);
  assert.equal(fixture.remove.rows + fixture.hold.rows, fixture.handoff.rows);
});

test("M6 REMOVE rows have all three proof axes and every false positive has an explicit HOLD owner", () => {
  const remove = fixture.auditRows.filter((row) => row.disposition === "REMOVE");
  const hold = fixture.auditRows.filter((row) => row.disposition === "HOLD");
  assert.equal(remove.length, fixture.remove.rows);
  assert.equal(hold.length, fixture.hold.rows);
  assert.equal(remove.every((row) => row.proof.staticZero && row.proof.bundleZero && row.proof.runtimeZero), true);
  for (const row of hold) {
    assert.ok(row.hold.reasonCodes.length, `${row.handoffId} has a reason`);
    assert.equal(row.hold.currentOwner, row.source.path);
    assert.ok(row.hold.candidateOwner);
    assert.match(row.hold.removalCondition, /static\/bundle\/live signal to zero/);
    assert.equal(row.proof.staticZero && row.proof.bundleZero && row.proof.runtimeZero, false);
  }
});

test("production build and both live audits cover the frozen selector set without query errors", () => {
  assert.equal(bundle.result, "PASS");
  assert.deepEqual(bundle.coverage, {
    rows: 556,
    removeRows: 511,
    holdRows: 45,
    removeRowsWithAfterEvidence: 0,
    holdRowsWithPreservedBundleEvidence: 27,
  });
  for (const runtime of [beforeRuntime, afterRuntime]) {
    assert.equal(runtime.handoff.tupleSha256, fixture.handoff.tupleSha256);
    assert.equal(runtime.coverage.topologies.length, 13);
    assert.equal(runtime.coverage.viewports.includes("1440x900"), true);
    assert.equal(runtime.coverage.snapshots,
      runtime.coverage.topologies.length * runtime.coverage.viewports.length);
    assert.equal(runtime.coverage.selectorRows, 556);
    assert.equal(runtime.coverage.uniqueSelectors, 465);
    assert.equal(runtime.summary.selectorsWithQueryErrors, 0);
  }
  const removeSelectors = new Set(fixture.auditRows
    .filter((row) => row.disposition === "REMOVE")
    .map((row) => row.selector));
  const liveAfter = afterRuntime.selectors.filter((row) => row.matchingSnapshots.length);
  assert.equal(liveAfter.some((row) => removeSelectors.has(row.selector)), false);
});

test("M6 five-viewport evidence preserves geometry and limits differences to generated identities", () => {
  assert.equal(manifest.schemaVersion, "cmp.issue-261.m6.visual-and-selector-evidence.v1");
  assert.equal(manifest.status, "ACCEPTED_MAIN_VISUAL_AND_RUNTIME");
  assert.equal(manifest.baseSha, fixture.baseSha);
  assert.deepEqual(manifest.ownership, {
    handoffSelectorRows: 556,
    handoffGroups: 495,
    removedSelectorRows: 511,
    touchedGroups: 462,
    fullyRemovedGroups: 452,
    partiallyShrunkGroups: 10,
    holdRows: 45,
    holdGroups: 43,
    remainingSelectorRows: 67,
    remainingGroups: 65,
    tupleSha256: fixture.handoff.tupleSha256,
  });
  assert.equal(manifest.physicalWindows4K, "DEFERRED_TO_223");
  assert.equal(manifest.comparison.artifactPairs, 305);
  assert.equal(manifest.comparison.originalPairs, 65);
  assert.equal(manifest.comparison.maximumChangedRatio < 0.016, true);
  const changed = manifest.comparison.records.filter((row) => !row.pixelIdentical);
  assert.deepEqual([...new Set(changed.map((row) => row.topology))].sort(), [
    "materials-curves",
    "materials-search",
    "modeling-distribution",
    "modeling-export",
  ]);
  assert.equal(changed.every((row) => (
    row.differenceBounds[3] - row.differenceBounds[1] <= 32
    || (row.changedPixels <= 20 && row.maximumChannelDelta <= 5)
  )), true);
});

test("M6 exact transform, inventory, bundle audit, and frontend guard stay green", () => {
  const options = { cwd: ROOT, encoding: "utf8", stdio: "pipe", maxBuffer: 64 * 1024 * 1024 };
  execFileSync("node", ["scripts/apply_issue_261_m6_zero_consumer_removal.mjs", "--check", "--exact"], options);
  execFileSync("node", ["scripts/check_issue_261_css_inventory.mjs"], options);
  execFileSync("node", ["scripts/check_issue_261_m6_production_bundle.mjs"], options);
  execFileSync("node", ["scripts/sync_issue_261_m6_frontend_guard_baseline.mjs"], options);
  execFileSync("node", ["scripts/check_frontend_guard.mjs"], options);
  assert.deepEqual(inventory.summary.byMigrationBatch, {
    "ACCEPTED-shared-layout-in-place": 22,
    "HOLD-m6-zero-consumer-false-positive": 45,
  });
  assert.equal(inventory.summary.selectorRows, 67);
  assert.equal(inventory.summary.cssRuleGroups, 65);
  assert.equal(inventory.summary.flags.deadCandidate, 0);
});

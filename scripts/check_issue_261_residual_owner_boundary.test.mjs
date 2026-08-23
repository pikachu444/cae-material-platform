import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const BASE_SHA = "599278067ab5f69d46ea59559344499399b51fed";
const fixture = JSON.parse(readFileSync(resolve(ROOT, "scripts/fixtures/issue-261-residual-owner-boundary.json"), "utf8"));
const inventory = JSON.parse(readFileSync(resolve(ROOT, "docs/17-evidence/issue-261-css-selector-inventory.json"), "utf8"));

function digest(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function groupKey(tuple) { return `${tuple[1]}#${tuple[3]}`; }

test("FE-06 freezes the full non-M6 residual with an owner and source-order oracle", () => {
  assert.equal(fixture.baseSha, BASE_SHA);
  assert.equal(fixture.targetRows.rows, 525);
  assert.equal(fixture.targetRows.groups, 438);
  assert.equal(fixture.targetTuples.length, 525);
  assert.equal(new Set(fixture.targetIds).size, 525);
  assert.equal(digest(fixture.targetTuples), fixture.targetRows.tupleSha256);
  assert.equal(new Set(fixture.targetTuples.map(groupKey)).size, fixture.targetRows.groups);
  const routed = Object.values(fixture.owners).flatMap((owner) => owner.ids);
  assert.equal(routed.length, 525);
  assert.equal(new Set(routed).size, 525);
  assert.deepEqual(new Set(routed), new Set(fixture.targetIds));
  const ownerById = new Map(Object.values(fixture.owners).flatMap((owner) => owner.ids.map((id) => [id, owner.path])));
  for (const owner of Object.values(fixture.owners)) {
    assert.equal(owner.ids.length, owner.sourceGroups.reduce((count, key) => count + fixture.targetTuples.filter((tuple) => groupKey(tuple) === key && ownerById.get(tuple[0]) === owner.path).length, 0));
    assert.equal(owner.ids.every((id) => fixture.targetIds.includes(id)), true);
  }
  for (let index = 1; index < fixture.expected.sourceOrder.length; index += 1) {
    const previous = fixture.expected.sourceOrder[index - 1];
    const current = fixture.expected.sourceOrder[index];
    assert.equal(previous[0] <= current[0], true);
    if (previous[0] === current[0]) {
      assert.equal(previous[1] < current[1] || (previous[1] === current[1] && previous[2] < current[2]), true);
    }
  }
});

test("FE-06 preserves the original M6 oracle and adds audited zero-consumer handoff rows", () => {
  assert.equal(fixture.originalM6Handoff.rows, 529);
  assert.equal(fixture.originalM6Handoff.groups, 475);
  assert.equal(digest(fixture.originalM6Handoff.tuples), fixture.originalM6Handoff.tupleSha256);
  assert.equal(fixture.m6Handoff.rows, 556);
  assert.equal(fixture.m6Handoff.groups, 495);
  assert.equal(fixture.m6Handoff.tuples.length, 556);
  assert.equal(digest(fixture.m6Handoff.tuples), fixture.m6Handoff.tupleSha256);
  assert.equal(inventory.summary.selectorRows, 578);
  assert.equal(inventory.summary.cssRuleGroups, 517);
  assert.deepEqual(inventory.summary.byMigrationBatch, {
    "ACCEPTED-shared-layout-in-place": 22,
    "M6-zero-consumer-removal-candidate": 556,
  });
  const checkpoint = inventory.migrationPlan.checkpoints.find(
    (entry) => entry.unit === "FE-06-residual-owner-boundary-consolidation",
  );
  assert.equal(checkpoint.current.residualTargetRows, 0);
  assert.equal(checkpoint.m6Handoff.tupleSha256, fixture.m6Handoff.tupleSha256);
  assert.equal(inventory.migrationPlan.nextBoundedUnit.id, "M6-zero-consumer-audit-and-removal");
  assert.match(inventory.migrationPlan.nextBoundedUnit.scope, /556/);
});

test("FE-06 pins cold-route owners and the missing direct load edges", () => {
  const ownerById = new Map(Object.values(fixture.owners).flatMap((owner) => owner.ids.map((id) => [id, owner.path])));
  assert.equal(ownerById.get("CSS-0153"), "apps/web/src/features/modeling/ui/modeling-stage-normalization.css");
  assert.equal(ownerById.get("CSS-0511"), "apps/web/src/design/typography.css");
  assert.equal(ownerById.get("CSS-0494"), "apps/web/src/design/primitives.css");
  assert.equal(ownerById.get("CSS-1053"), "apps/web/src/domain-workflow-links.css");
  assert.equal(ownerById.get("CSS-0722"), "apps/web/src/features/administration/ui/administration.css");
  const imports = new Map([
    ["apps/web/src/bulk-export-center.tsx", ["modeling-export-stage.css", "modeling-export-delivery-workbenches.css"]],
    ["apps/web/src/reference-replicate-statistics-workbench.tsx", ["modeling-calibration-workbenches.css"]],
    ["apps/web/src/polymer-temperature-shift-inspector.tsx", ["modeling-viscoelastic-workbenches.css"]],
    ["apps/web/src/reference-elastoplastic-workbench.tsx", ["modeling-export-delivery-workbenches.css"]],
    ["apps/web/src/test-context-workbench.tsx", ["canonical-test-data-workbench.css"]],
    ["apps/web/src/domain-workflow-links.tsx", ["domain-workflow-links.css"]],
  ]);
  for (const [path, expected] of imports) {
    const source = readFileSync(resolve(ROOT, path), "utf8");
    for (const stylesheet of expected) assert.match(source, new RegExp(stylesheet.replaceAll(".", "\\.")));
  }
});

test("FE-06 exact transform, inventory regeneration, and guard are green", () => {
  const options = { cwd: ROOT, encoding: "utf8", stdio: "pipe", maxBuffer: 64 * 1024 * 1024 };
  execFileSync("node", ["scripts/apply_issue_261_residual_owner_boundary.mjs", "--check", "--exact"], options);
  execFileSync("node", ["scripts/check_issue_261_css_inventory.mjs"], options);
  execFileSync("node", ["scripts/check_frontend_guard.mjs"], options);
});

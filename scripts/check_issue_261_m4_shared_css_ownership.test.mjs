import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const FIXTURE_PATH = "scripts/fixtures/issue-261-m4-shared-css-ownership.json";
const fixture = JSON.parse(readFileSync(resolve(ROOT, FIXTURE_PATH), "utf8"));

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function groupCount(tuples) {
  return new Set(tuples.map((tuple) => `${tuple[1]}#${tuple[3]}`)).size;
}

function gitJson(sha, path) {
  return JSON.parse(execFileSync("git", ["show", `${sha}:${path}`], {
    cwd: ROOT,
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  }));
}

test("M4 fixture freezes the 314-row packet, four cascade corrections, and a complete partition", () => {
  const tuples = fixture.targetTuples;
  const tupleById = new Map(tuples.map((tuple) => [tuple[0], tuple]));
  const approved = new Set(fixture.approvedIds);
  const accepted = new Set(fixture.acceptedInPlace.ids);
  const hold = new Set(fixture.hold.ids);
  const corrections = new Set(fixture.cascadeCorrections.ids);
  const candidateTuples = tuples.filter((tuple) => !corrections.has(tuple[0]));

  assert.equal(tuples.length, 318);
  assert.equal(tupleById.size, 318);
  assert.equal(groupCount(tuples), 266);
  assert.equal(candidateTuples.length, 314);
  assert.equal(groupCount(candidateTuples), 262);
  assert.equal(sha256(JSON.stringify(candidateTuples)), fixture.candidate.tupleSha256);
  assert.equal(corrections.size, 4);
  assert.equal(approved.size, 288);
  assert.equal(accepted.size, 11);
  assert.equal(hold.size, 19);
  assert.equal(groupCount(tuples.filter((tuple) => approved.has(tuple[0]))), 243);
  assert.equal(groupCount(tuples.filter((tuple) => accepted.has(tuple[0]))), 11);
  assert.equal(groupCount(tuples.filter((tuple) => hold.has(tuple[0]))), 12);
  assert.equal(new Set([...approved, ...accepted, ...hold]).size, 318);
  assert.deepEqual([...approved].filter((id) => accepted.has(id) || hold.has(id)), []);
  assert.equal(fixture.targetInsertion, "prepend");

  const routed = Object.values(fixture.owners).flatMap((owner) => owner.ids);
  assert.equal(routed.length, 288);
  assert.equal(new Set(routed).size, 288);
  assert.deepEqual(new Set(routed), approved);
});

test("M4 routes Materials candidates to Materials and retains every mixed source group", () => {
  const base = gitJson(fixture.baseSha, "docs/17-evidence/issue-261-css-selector-inventory.json");
  const baseById = new Map(base.selectors.map((row) => [row.id, row]));
  const materialsOwner = Object.values(fixture.owners).find(
    (owner) => owner.path === "apps/web/src/features/materials/ui/materials.css",
  );
  const materialsIds = new Set(materialsOwner.ids);
  const materialSpecificIds = fixture.targetTuples
    .map((tuple) => tuple[0])
    .filter((id) => baseById.get(id)?.owner.category === "materials-specific");
  assert.equal(materialSpecificIds.length, 13);
  assert.equal(materialSpecificIds.every((id) => materialsIds.has(id)), true);

  const candidateIds = new Set(fixture.targetTuples.map((tuple) => tuple[0]));
  const holdIds = new Set(fixture.hold.ids);
  const groups = Object.groupBy(base.selectors, (row) => `${row.source.path}#${row.source.ruleIndex}`);
  for (const rows of Object.values(groups)) {
    const candidatePeers = rows.filter((row) => candidateIds.has(row.id));
    if (!candidatePeers.length || candidatePeers.length === rows.length) continue;
    assert.equal(candidatePeers.every((row) => holdIds.has(row.id)), true,
      `mixed group ${rows[0].source.path}#${rows[0].source.ruleIndex} escaped HOLD`);
  }
});

test("M4 exact transform, owner import, and regenerated residual inventory pass", () => {
  const currentBefore = JSON.parse(readFileSync(
    resolve(ROOT, "docs/17-evidence/issue-261-css-selector-inventory.json"),
    "utf8",
  ));
  const postM6 = currentBefore.migrationPlan.checkpoints.some(
    (checkpoint) => checkpoint.unit === "M6-zero-consumer-audit-and-removal",
  );
  if (postM6) {
    execFileSync("node", [
      "scripts/apply_issue_261_m6_zero_consumer_removal.mjs",
      "--check",
      "--exact",
    ], { cwd: ROOT, stdio: "pipe", encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  } else if (currentBefore.migrationPlan.checkpoints.some(
    (checkpoint) => checkpoint.unit === "FE-06-residual-owner-boundary-consolidation",
  )) {
    execFileSync("node", [
      "scripts/apply_issue_261_residual_owner_boundary.mjs",
      "--check",
      "--exact",
    ], { cwd: ROOT, stdio: "pipe", encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  } else {
    execFileSync("node", [
      "scripts/apply_issue_261_m1e5_producer_routed_residual.mjs",
      "--fixture",
      FIXTURE_PATH,
      "--check",
    ], { cwd: ROOT, stdio: "pipe", encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  }
  execFileSync("node", ["scripts/check_issue_261_css_inventory.mjs"], {
    cwd: ROOT,
    stdio: "pipe",
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });

  const source = readFileSync(resolve(ROOT, fixture.importAddition.importer), "utf8");
  assert.match(source, new RegExp(`import ["']${fixture.importAddition.value.replaceAll(".", "\\.")}["'];`));
  const current = JSON.parse(readFileSync(
    resolve(ROOT, "docs/17-evidence/issue-261-css-selector-inventory.json"),
    "utf8",
  ));
  const postResidualOwnerBoundary = current.migrationPlan.checkpoints.some(
    (checkpoint) => checkpoint.unit === "FE-06-residual-owner-boundary-consolidation",
  );
  assert.equal(current.summary.selectorRows, postM6 ? 67 : postResidualOwnerBoundary ? 578 : 1103);
  assert.equal(current.summary.cssRuleGroups, postM6 ? 65 : postResidualOwnerBoundary ? 517 : 941);
  assert.equal(current.summary.byMigrationBatch["M4-shared-cleanup"] ?? 0, 0);
  assert.equal(current.summary.byMigrationBatch["ACCEPTED-shared-layout-in-place"], postResidualOwnerBoundary ? 22 : 11);
  assert.equal(
    current.summary.byMigrationBatch["HOLD-owner-or-cross-feature-split"] ?? 0,
    postResidualOwnerBoundary ? 0 : 525,
  );
  assert.equal(current.summary.byMigrationBatch["M6-zero-consumer-removal-candidate"] ?? 0, postM6 ? 0 : postResidualOwnerBoundary ? 556 : 529);
  if (postM6) assert.equal(current.summary.byMigrationBatch["HOLD-m6-zero-consumer-false-positive"], 45);
});

test("M4 Fit producer imports preserve the reviewed cascade order", () => {
  const { importer, values } = fixture.m4SideEffectImportOrder;
  const source = readFileSync(resolve(ROOT, importer), "utf8");
  const lines = source.split(/\r?\n/).map((line) => line.trim());
  const positions = values.map((value) => lines.indexOf(`import "${value}";`));
  assert.equal(positions.every((position) => position >= 0), true);
  assert.equal(new Set(positions).size, values.length);
  assert.equal(positions.every((position, index) => index === 0 || position > positions[index - 1]), true);
});

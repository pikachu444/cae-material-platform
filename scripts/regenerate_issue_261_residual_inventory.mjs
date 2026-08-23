import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { makeInventory } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const BASE_SHA = "599278067ab5f69d46ea59559344499399b51fed";
const INVENTORY_PATH = "docs/17-evidence/issue-261-css-selector-inventory.json";
const FIXTURE_PATH = "scripts/fixtures/issue-261-residual-owner-boundary.json";
const OUTPUT = resolve(ROOT, INVENTORY_PATH);
const fixture = JSON.parse(readFileSync(resolve(ROOT, FIXTURE_PATH), "utf8"));

function digest(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

const inventory = makeInventory();
if (inventory.sourceSha !== BASE_SHA || inventory.mergeBaseSha !== BASE_SHA) {
  throw new Error(`inventory source drift: ${inventory.sourceSha}/${inventory.mergeBaseSha}`);
}
const m6 = inventory.selectors.filter((row) => row.owner.migrationBatch === "M6-zero-consumer-removal-candidate");
const accepted = inventory.selectors.filter((row) => row.owner.migrationBatch === "ACCEPTED-shared-layout-in-place");
if (inventory.summary.selectorRows !== fixture.acceptedInPlace.rows + fixture.m6Handoff.rows
    || m6.length !== fixture.m6Handoff.rows
    || accepted.length !== fixture.acceptedInPlace.rows) {
  throw new Error(`unexpected post-FE-06 inventory: ${JSON.stringify(inventory.summary)}`);
}
const residualCheckpoint = {
  unit: "FE-06-residual-owner-boundary-consolidation",
  sourceCommit: BASE_SHA,
  frozenBase: BASE_SHA,
  evidence: "docs/17-evidence/issue-261-fe06-residual-owner-boundary-consolidation.md",
  disposition: "ACCEPTED",
  frozen: {
    selectorRows: fixture.targetRows.rows,
    cssRuleGroups: fixture.targetRows.groups,
    tupleSha256: fixture.targetRows.tupleSha256,
    ownerRows: fixture.expected.ownerRows,
  },
  current: {
    selectorRows: inventory.summary.selectorRows,
    cssRuleGroups: inventory.summary.cssRuleGroups,
    acceptedInPlaceRows: accepted.length,
    m6Rows: m6.length,
    m6Groups: fixture.m6Handoff.groups,
    residualTargetRows: 0,
    crossCssDuplicateRows: inventory.summary.flags.crossCssDuplicate,
  },
  m6Handoff: {
    rows: fixture.m6Handoff.rows,
    groups: fixture.m6Handoff.groups,
    tupleSha256: fixture.m6Handoff.tupleSha256,
    rule: fixture.m6Handoff.rule,
  },
  ownerBoundaries: Object.values(fixture.owners).map((owner) => ({
    path: owner.path,
    rows: owner.ids.length,
    sourceGroups: owner.sourceGroups.length,
    categoryCounts: owner.categoryCounts,
  })),
  status: "ACCEPTED_MAIN_VISUAL_AND_RUNTIME",
  liveAcceptance: "PASS — Main live/browser/original-resolution acceptance",
};
inventory.migrationPlan.checkpoints = [
  ...inventory.migrationPlan.checkpoints.filter((checkpoint) => checkpoint.unit !== residualCheckpoint.unit),
  residualCheckpoint,
];
inventory.migrationPlan.nextBoundedUnit = {
  id: "M6-zero-consumer-audit-and-removal",
  status: "owner-packet-required",
  scope: `Audit the ${fixture.m6Handoff.rows} zero-consumer candidate rows as one evidence-led packet; preserve false positives in HOLD and remove only selectors with complete producer/reference/runtime proof after FE-06 live zero-consumer proof.`,
};
if (digest(fixture.m6Handoff.tuples) !== fixture.m6Handoff.tupleSha256) {
  throw new Error("M6 handoff tuple digest drifted");
}
writeFileSync(OUTPUT, `${JSON.stringify(inventory, null, 2)}\n`, "utf8");
console.log(JSON.stringify({
  output: INVENTORY_PATH,
  sourceSha: inventory.sourceSha,
  summary: inventory.summary,
  residualCheckpoint: residualCheckpoint.current,
  nextBoundedUnit: inventory.migrationPlan.nextBoundedUnit,
}, null, 2));

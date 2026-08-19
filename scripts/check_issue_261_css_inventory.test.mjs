import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  isZeroProductionConsumerCandidate,
  sourceClassEvidence,
} from "./check_issue_261_css_inventory.mjs";

function sorted(values) {
  return [...values].sort();
}

test("extracts static, template, and conditional className producers", () => {
  const source = [
    '<aside className="modeling-support-drawer" />',
    '<main className={`processing-workbench-page stage-${workflowTask}`} />',
    '<section className={`native-preview${ok ? " has-linked-response" : ""}`} />',
    '<button className={active ? "active choice" : "choice"} />',
  ].join("\n");

  const evidence = sourceClassEvidence(source);
  assert.deepEqual(sorted(evidence.producerTokens), [
    "active",
    "choice",
    "has-linked-response",
    "modeling-support-drawer",
    "native-preview",
    "processing-workbench-page",
  ]);
  assert.equal(evidence.producerTokens.has("stage-"), false);
});

test("keeps selector API strings as references rather than class producers", () => {
  const evidence = sourceClassEvidence(`
    const selected = root.querySelector(".materials-selection");
    selected?.closest('.engineering-pane');
  `);

  assert.deepEqual(sorted(evidence.producerTokens), []);
  assert.deepEqual(sorted(evidence.referenceTokens), [
    "engineering-pane",
    "materials-selection",
  ]);
  assert.equal(isZeroProductionConsumerCandidate("materials-selection", {
    productionProducers: [],
    productionReferences: ["apps/web/src/example.tsx"],
  }), false);
  assert.equal(isZeroProductionConsumerCandidate("unobserved-class", {
    productionProducers: [],
    productionReferences: [],
  }), true);
});

test("recognizes the production examples that invalidated the first audit", () => {
  const processing = sourceClassEvidence(readFileSync(
    new URL("../apps/web/src/common-processing-workbench.tsx", import.meta.url),
    "utf8",
  ));
  const materials = sourceClassEvidence(readFileSync(
    new URL("../apps/web/src/material-library.tsx", import.meta.url),
    "utf8",
  ));

  assert.equal(processing.producerTokens.has("processing-workbench-page"), true);
  assert.equal(processing.producerTokens.has("modeling-support-drawer"), true);
  assert.equal(materials.producerTokens.has("has-linked-response"), true);
});

test("keeps the audit regression selectors out of the generated dead batch", () => {
  const inventory = JSON.parse(readFileSync(
    new URL("../docs/17-evidence/issue-261-css-selector-inventory.json", import.meta.url),
    "utf8",
  ));
  const byId = new Map(inventory.selectors.map((row) => [row.id, row]));
  for (const id of ["CSS-0410", "CSS-0515", "CSS-1469"]) {
    const row = byId.get(id);
    assert.ok(row, `${id} is present`);
    assert.equal(row.flags.deadCandidate, false, `${id} is not a dead candidate`);
    assert.equal(
      row.consumers.status,
      "production-subject-class-producer-observed",
      `${id} has production producer evidence`,
    );
    assert.ok(row.consumers.productionProducerFiles.length > 0, `${id} records its producer file`);
  }
  const completed = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A0-modeling-data-same-selector-overlap",
  );
  assert.ok(completed);
  assert.deepEqual(completed.actualAfter, {
    cssRuleGroups: 2826,
    selectorRows: 3573,
    crossCssDuplicateRows: 13,
  });
  assert.equal(completed.selectorRowsRemoved, 12);
  assert.equal(completed.touchedRuleGroups, 11);
  assert.equal(completed.fullyRemovedRuleGroups, 8);
  assert.equal(completed.partiallyShrunkRuleGroups, 3);
  assert.deepEqual(completed.residualExactSelectorRows, []);
  for (const selector of completed.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  assert.deepEqual(inventory.migrationPlan.nextBoundedUnit, {
    id: "M1A1-modeling-data-component-region",
    status: "owner-packet-required",
    scope: "Select one remaining M1A Data component region from the regenerated inventory; do not migrate all remaining M1A rows together.",
  });
});

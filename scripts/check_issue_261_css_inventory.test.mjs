import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  inventoryMatchesRendered,
  isZeroProductionConsumerCandidate,
  reconcileInventorySourceSha,
  sourceClassEvidence,
} from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function sorted(values) {
  return [...values].sort();
}

function gitHead(revision) {
  return execFileSync("git", ["rev-parse", revision], { cwd: ROOT, encoding: "utf8" }).trim();
}

test("accepts a committed inventory whose sourceSha is a historical ancestor", () => {
  const committed = readFileSync(
    new URL("../docs/17-evidence/issue-261-css-selector-inventory.json", import.meta.url),
    "utf8",
  );
  const currentHead = gitHead("HEAD");
  const rendered = committed.replace(
    /("sourceSha"\s*:\s*")[0-9a-f]{40}(")/,
    `$1${currentHead}$2`,
  );

  assert.equal(reconcileInventorySourceSha(committed, rendered), rendered);
});

test("rejects malformed or non-ancestor sourceSha values", () => {
  const currentHead = gitHead("HEAD");
  const rendered = JSON.stringify({ sourceSha: currentHead, selectors: [] }, null, 2) + "\n";
  const malformed = rendered.replace(currentHead, "not-a-git-sha");
  const unknown = rendered.replace(currentHead, "f".repeat(40));

  assert.equal(inventoryMatchesRendered(malformed, rendered), false);
  assert.equal(inventoryMatchesRendered(unknown, rendered), false);
});

test("still rejects substantive stale inventory content", () => {
  const currentHead = gitHead("HEAD");
  const rendered = JSON.stringify({ sourceSha: currentHead, selectors: [] }, null, 2) + "\n";
  const stale = JSON.stringify({ sourceSha: gitHead("HEAD~1"), selectors: [{ id: "stale" }] }, null, 2) + "\n";

  assert.equal(inventoryMatchesRendered(stale, rendered), false);
});

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

test("preserves the exact M1A7 mapping-heading declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  );
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  );
  const expected = `.data-mapping-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  min-width: 0;
  min-height: 22px;
  padding-bottom: 3px;
  border-bottom: 1px solid var(--ux-border);
  gap: 8px;
}

.data-mapping-heading strong {
  color: var(--ux-text);
  font-size: 13px;
  font-weight: 650;
}

.data-mapping-heading span {
  overflow: hidden;
  color: var(--ux-danger);
  font-size: 11.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.data-mapping-heading span {
  font-size: var(--ux-metadata-font-size);
}`;

  assert.equal(legacy.includes(".data-mapping-heading"), false);
  assert.equal(owner.replace(/\r\n/g, "\n").endsWith(`${expected}\n`), true);
  assert.equal(owner.match(/\.data-mapping-heading span \{/g)?.length, 2);
  assert.ok(
    legacy.replace(/\r\n/g, "\n").includes(`.data-mapping-consequence,
.data-source-evidence :is(header, p),`),
  );
});

test("preserves the exact M1A8 optional-channel declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  );
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  );
  const expected = `.data-mapping-decision .data-intake-attention > label.data-optional-channel {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: var(--ux-interactive-min-block-size);
  color: var(--ux-text-muted);
  font-size: 11.5px;
  font-weight: 600;
}

.data-mapping-decision .data-intake-attention > label.data-optional-channel > input {
  grid-column: auto;
  width: 16px;
  min-height: 16px;
  height: 16px;
  margin: 0;
}

.modeling-main-surface:has(.data-source-decision-grid) .data-source-decision-grid .data-mapping-decision .data-intake-attention > label.data-optional-channel {
  display: flex;
  grid-template-columns: none;
}

.modeling-main-surface:has(.data-source-decision-grid) .data-source-decision-grid .data-mapping-decision .data-intake-attention > label.data-optional-channel > input {
  grid-column: auto;
  width: 16px;
  min-height: 16px;
  height: 16px;
  padding: 0;
}`;
  const laterGenericLabelRule = `.modeling-data-workspace .modeling-data-intake :is(
  .data-intake-row label,`;

  assert.equal(legacy.includes(".data-optional-channel"), false);
  assert.equal(owner.includes(expected), true);
  assert.equal(owner.match(/data-optional-channel/g)?.length, 4);
  assert.ok(owner.indexOf(expected) < owner.indexOf(laterGenericLabelRule));
});

test("preserves the exact M1A9 mapping-table declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  );
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const expected = `.data-mapping-table {
  min-width: 0;
  border-top: 1px solid var(--ux-border);
  padding-top: 6px;
}

.data-mapping-table {
  overflow-x: auto;
}

.data-mapping-table table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
}

.data-mapping-table th,
.data-mapping-table td {
  border-bottom: 1px solid var(--ux-border);
  padding: 4px 5px;
  text-align: left;
  line-height: 1.2;
  overflow-wrap: anywhere;
  white-space: normal;
}

.data-mapping-table th {
  color: var(--ux-text-muted);
  font-size: 11.5px;
  font-weight: 650;
}

.data-mapping-table td {
  color: var(--ux-text);
  font-size: 13px;
}

.data-mapping-table select {
  width: 100%;
  min-height: 30px;
  max-width: none;
  font-size: 13px;
}

.data-mapping-decision .data-mapping-table select {
  width: 100%;
  max-width: none;
}

.data-mapping-table td:last-child {
  max-width: 180px;
  overflow-wrap: anywhere;
  white-space: normal;
}

.modeling-main-surface.has-data-split .data-mapping-decision .data-mapping-table select {
  box-sizing: border-box;
  height: var(--ux-input-min-block-size);
  min-height: var(--ux-input-min-block-size);
  padding-block: 0;
  padding-inline: var(--ux-space-2);
  font-size: var(--ux-data-font-size);
  line-height: normal;
  appearance: auto;
}

.modeling-main-surface.has-data-split .data-mapping-decision .data-mapping-table th,
.modeling-main-surface.has-data-split .data-mapping-decision .data-mapping-table td {
  padding-block: var(--ux-table-cell-padding-block);
}

.data-mapping-table table,
.data-mapping-table td {
  font-size: var(--ux-data-font-size);
}

.data-mapping-table th {
  font-size: var(--ux-metadata-font-size);
}

.data-mapping-table th,
.data-mapping-table td {
  padding: var(--ux-cell-padding-block) var(--ux-cell-padding-inline);
}

.data-mapping-table select {
  min-height: var(--ux-input-min-block-size);
  height: auto;
  font-size: var(--ux-data-font-size);
}`;
  const optionalChannelRule = ".data-mapping-decision .data-intake-attention > label.data-optional-channel";
  const laterGenericControlRule = `.modeling-data-workspace .modeling-data-intake :is(
  select,`;

  assert.equal(legacy.includes(".data-mapping-table"), false);
  assert.equal(owner.includes(expected), true);
  assert.ok(owner.indexOf(optionalChannelRule) < owner.indexOf(expected));
  assert.ok(owner.indexOf(expected) < owner.indexOf(laterGenericControlRule));
});

const M1A13_LOCAL_SCROLLPORT_RULES = `.modeling-task-ribbon:has(.data-intake-local) {
  min-height: 0;
  max-height: none;
  overflow: visible;
}

.modeling-task-ribbon:has(.data-intake-local) .modeling-data-intake,
.modeling-task-ribbon:has(.data-intake-local) .data-intake-local {
  max-height: none;
  overflow: visible;
}

.data-intake-local {
  min-width: 0;
}

.data-intake-local {
  display: grid;
  gap: 6px;
  max-height: none;
  overflow: visible;
}

.data-intake-local {
  max-height: none;
  overflow: visible;
}`;

const M1A14_MAPPING_BLOCKER_BASE_RULES = `.data-mapping-decision .data-mapping-blockers {
  max-width: none;
  gap: 3px;
  padding: 6px 8px;
  border-left: 3px solid var(--ux-danger);
  background: color-mix(in srgb, var(--ux-danger-soft, #fce8e8) 58%, transparent);
}

.data-mapping-blockers {
  display: grid;
  gap: 2px;
  min-width: 180px;
  max-width: 360px;
  color: var(--ux-danger);
  font-size: 13px;
}

.data-mapping-blockers strong {
  color: var(--ux-text);
}`;

const M1A14_MAPPING_BLOCKER_DENSITY_RULE = `.data-mapping-blockers {
  font-size: var(--ux-data-font-size);
}`;

const M1A15_DATA_INTAKE_SURFACE_RULES = `.modeling-data-intake {
  display: grid;
  gap: 6px;
  min-height: 76px;
  padding: 7px 12px 9px;
}

.modeling-data-intake {
  color: var(--ux-text);
  font-size: 13px;
}

.modeling-main-surface.has-data-split .modeling-data-intake {
  padding-block: var(--ux-space-1);
  padding-inline: var(--ux-pane-padding);
}

.modeling-data-intake {
  font-size: var(--ux-data-font-size);
}`;

const M1A16_LOCAL_IMPORT_CONTROL_RULES = `.modeling-main-surface:has(.data-source-decision-grid) .data-intake-local > .data-intake-row > label {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  align-items: center;
  gap: var(--ux-space-1) var(--ux-space-2);
  min-width: 0;
}

.modeling-main-surface:has(.data-source-decision-grid) .data-intake-local > .data-intake-row > label > :is(input, select) {
  grid-column: 2;
  box-sizing: border-box;
  min-height: var(--ux-input-min-block-size);
  height: var(--ux-input-min-block-size);
  padding: var(--ux-space-1) var(--ux-space-2);
  font-size: var(--ux-data-font-size);
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row select[name="local-test-run"] {
  box-sizing: border-box;
  height: var(--ux-input-min-block-size);
  min-height: var(--ux-input-min-block-size);
  padding-block: 0;
  padding-inline: var(--ux-space-2);
  font-size: var(--ux-data-font-size);
  line-height: normal;
}

/* Data-only native controls consume the same density contract as the rest of
   the workbench. The file selector remains native inside the shared input. */
.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > label,
.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > button {
  align-self: end;
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row select[name="local-test-run"],
.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row input[type="file"] {
  box-sizing: border-box;
  height: var(--ux-input-min-block-size);
  min-height: var(--ux-input-min-block-size);
  margin: 0;
  padding-block: 0;
  border-radius: 0;
  box-shadow: none;
  font-size: var(--ux-data-font-size);
  line-height: normal;
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > button {
  box-sizing: border-box;
  height: var(--ux-control-min-block-size);
  min-height: var(--ux-control-min-block-size);
  margin: 0;
  padding-block: 0;
  border-radius: 0;
  box-shadow: none;
  font-size: var(--ux-data-font-size);
  line-height: normal;
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row input[type="file"] {
  padding-inline: 0;
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row input[type="file"]::file-selector-button {
  box-sizing: border-box;
  height: calc(var(--ux-input-min-block-size) - 2px);
  min-height: calc(var(--ux-input-min-block-size) - 2px);
  margin: 0;
  padding: 0 var(--ux-space-2);
  border: 0;
  border-right: 1px solid var(--ux-border);
  border-radius: 0;
  background: var(--ux-surface-subtle);
  color: var(--ux-text);
  font: inherit;
  line-height: normal;
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > button {
  border-radius: 0;
  box-shadow: none;
  cursor: pointer;
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > button:disabled {
  border-color: var(--ux-border-strong);
  background: var(--ux-surface-subtle);
  color: var(--ux-text-muted);
  cursor: not-allowed;
  opacity: 1;
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row select[name="local-test-run"],
.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row input[type="file"] {
  height: var(--ux-input-min-block-size);
  min-height: var(--ux-input-min-block-size);
  font-size: var(--ux-data-font-size);
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > button {
  height: var(--ux-control-min-block-size);
  min-height: var(--ux-control-min-block-size);
  font-size: var(--ux-data-font-size);
}

.modeling-main-surface.has-data-split .data-intake-local > .data-intake-row input[type="file"]::file-selector-button {
  height: calc(var(--ux-input-min-block-size) - 2px);
  min-height: calc(var(--ux-input-min-block-size) - 2px);
  padding-inline: var(--ux-space-2);
}`;

const M1A17_MAPPING_ATTENTION_RULES = `.data-intake-attention {
  min-width: 0;
}

.data-intake-attention label {
  display: grid;
  gap: 2px;
  min-width: 150px;
  color: var(--ux-text-muted);
  font-size: 11.5px;
  font-weight: 650;
}

.data-intake-attention input,
.data-intake-attention select {
  min-height: 30px;
  font-size: 13px;
}

.data-intake-attention {
  display: flex;
  align-items: end;
  gap: 8px;
  padding-left: 8px;
  border-left: 3px solid var(--ux-warning);
}

.data-intake-attention > strong {
  align-self: center;
  min-width: 145px;
  font-size: 12px;
}

.data-intake-attention label {
  grid-template-columns: minmax(130px, 1fr) minmax(72px, .45fr);
}

.data-intake-attention label select:first-of-type {
  grid-column: 1;
}

.data-intake-attention > p {
  margin: 4px 0;
  color: var(--ux-text-muted);
  font-size: 11.5px;
  line-height: 1.25;
}

.data-mapping-decision .data-intake-attention {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: 5px;
  min-width: 0;
  padding: 0 0 0 8px;
  border-left: 3px solid var(--ux-warning);
}

.data-mapping-decision .data-intake-attention > strong {
  min-width: 0;
}

.data-mapping-decision .data-intake-attention > label {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
}

/* The content-fit Data ribbon keeps source decisions readable without
   spending a full control row on each field.  Scope this to the real mapping
   decision surface so the compact grammar is not applied to Library rows or
   other stages merely because a blocker class happens to be present. */
.modeling-main-surface:has(.data-source-decision-grid) .data-source-decision-grid .data-mapping-decision .data-intake-attention > label {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  align-items: center;
  gap: var(--ux-space-1) var(--ux-space-2);
  min-width: 0;
}

.modeling-main-surface:has(.data-source-decision-grid) .data-source-decision-grid .data-mapping-decision .data-intake-attention > label > :is(input, select) {
  grid-column: 2;
  box-sizing: border-box;
  min-height: var(--ux-input-min-block-size);
  height: var(--ux-input-min-block-size);
  padding: var(--ux-space-1) var(--ux-space-2);
  font-size: var(--ux-data-font-size);
}

.modeling-main-surface.has-data-split .data-source-decision-grid .data-mapping-decision .data-intake-attention > label > select[name="local-data-schema"] {
  box-sizing: border-box;
  height: var(--ux-input-min-block-size);
  min-height: var(--ux-input-min-block-size);
  padding-block: 0;
  padding-inline: var(--ux-space-2);
  font-size: var(--ux-data-font-size);
  line-height: normal;
}

.data-intake-attention label {
  font-size: var(--ux-metadata-font-size);
}

.data-intake-attention :is(input, select) {
  min-height: var(--ux-input-min-block-size);
  height: auto;
  font-size: var(--ux-data-font-size);
}`;

const M1A18_MAPPING_RESOLVED_RULES = `.data-mapping-resolved label {
  display: grid;
  gap: 2px;
  min-width: 150px;
  color: var(--ux-text-muted);
  font-size: 11.5px;
  font-weight: 650;
}

.data-mapping-resolved input,
.data-mapping-resolved select {
  min-height: 30px;
  font-size: 13px;
}

.data-mapping-resolved > span {
  min-width: 0;
  overflow: hidden;
  color: var(--ux-text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.data-mapping-resolved > strong {
  align-self: center;
  min-width: 145px;
  font-size: 12px;
}

.data-mapping-resolved label {
  grid-template-columns: minmax(130px, 1fr) minmax(72px, .45fr);
}

.data-mapping-resolved label select:first-of-type {
  grid-column: 1;
}

.data-mapping-decision > .data-mapping-resolved {
  min-width: 0;
}

.data-mapping-resolved label {
  font-size: var(--ux-metadata-font-size);
}

.data-mapping-resolved :is(input, select) {
  min-height: var(--ux-input-min-block-size);
  height: auto;
  font-size: var(--ux-data-font-size);
}`;

const M1A19_DATA_INTAKE_FIELD_ROW_RULES = `.data-intake-row {
  min-width: 0;
}

.data-intake-row {
  display: flex;
  align-items: end;
  gap: 10px;
}

.data-intake-row label {
  display: grid;
  gap: 2px;
  min-width: 150px;
  color: var(--ux-text-muted);
  font-size: 11.5px;
  font-weight: 650;
}

.data-intake-row input,
.data-intake-row select {
  min-height: 30px;
  font-size: 13px;
}

.data-intake-row p {
  margin: 0 0 6px;
  color: var(--ux-text-muted);
  font-size: 11.5px;
}

.data-intake-message {
  margin: 0;
  color: var(--ux-success);
  font-size: 11px;
}

.data-intake-row label {
  font-size: var(--ux-metadata-font-size);
}

.data-intake-row :is(input, select) {
  min-height: var(--ux-input-min-block-size);
  height: auto;
  font-size: var(--ux-data-font-size);
}`;

const M1A20_MAPPING_DECISION_FRAME_RULES = `.data-mapping-decision {
  display: grid;
  align-content: start;
  gap: 5px;
  min-width: 0;
}

.data-mapping-decision .mapping-context-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr));
  align-items: end;
}

.modeling-main-surface:has(.data-intake-local) .data-source-decision-grid {
  grid-template-columns: 400px minmax(0, 1fr);
}

/* Task 1 mapping controls use the native compact control grammar.  These
   selectors intentionally outrank the page-wide workbench minimums without
   changing controls in Process, Fit, or Export. */
.modeling-main-surface.has-data-split .data-mapping-decision select[name="local-data-schema"] {
  box-sizing: border-box;
  height: var(--ux-input-min-block-size);
  min-height: var(--ux-input-min-block-size);
  padding-block: 0;
  padding-inline: var(--ux-space-2);
  font-size: var(--ux-data-font-size);
  line-height: normal;
}`;

test("preserves the exact M1A10 Data split-frame declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const expected = `.modeling-main-surface.has-data-split {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.modeling-data-split {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  width: 100%;
}

.modeling-data-ribbon-panel {
  min-width: 0;
  min-height: 0;
}

.modeling-data-ribbon-panel {
  min-height: 0;
  overflow: hidden;
}

.modeling-data-ribbon-panel > .modeling-task-ribbon {
  height: 100%;
  min-height: 0;
  max-height: none;
  overflow-x: hidden;
  overflow-y: hidden;
}

.modeling-data-ribbon-panel > .modeling-task-ribbon-scrollable {
  box-sizing: border-box;
  padding-block-end: var(--ux-space-2);
  overflow-y: auto;
  overscroll-behavior: contain;
  scroll-padding-block: var(--ux-space-2);
  scrollbar-gutter: stable;
}

.modeling-data-plot-panel > .persistent-modeling-plot {
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.modeling-data-divider {
  z-index: 2;
  min-height: var(--ux-workbench-splitter-size);
  border-block: 1px solid var(--ux-border-strong);
  background: var(--ux-surface-subtle);
  cursor: row-resize;
}

.modeling-data-divider:hover,
.modeling-data-divider:focus-visible,
.modeling-data-divider[data-separator="modeling-data-ribbon-plot-divider"]:active {
  background: var(--ux-accent-soft);
}

.modeling-data-divider:focus-visible {
  outline: 2px solid var(--ux-focus);
  outline-offset: -2px;
}`;

  for (const selector of [
    ".modeling-main-surface.has-data-split",
    ".modeling-data-split",
    ".modeling-data-ribbon-panel",
    ".modeling-data-plot-panel > .persistent-modeling-plot",
    ".modeling-data-divider",
  ]) {
    assert.equal(legacy.includes(`${selector} {`), false, `${selector} left layout.css`);
  }
  const ownerWithoutM1A13 = owner.replace(
    `\n\n${M1A13_LOCAL_SCROLLPORT_RULES}\n\n`,
    "\n\n",
  );
  assert.notEqual(ownerWithoutM1A13, owner);
  const ownerWithoutM1A15 = ownerWithoutM1A13.replace(
    `\n\n${M1A15_DATA_INTAKE_SURFACE_RULES}\n\n`,
    "\n\n",
  );
  assert.notEqual(ownerWithoutM1A15, ownerWithoutM1A13);
  const ownerWithoutM1A16 = ownerWithoutM1A15.replace(
    `\n\n${M1A16_LOCAL_IMPORT_CONTROL_RULES}\n\n`,
    "\n\n",
  );
  assert.notEqual(ownerWithoutM1A16, ownerWithoutM1A15);
  const ownerWithoutM1A17 = ownerWithoutM1A16.replace(
    `\n\n${M1A17_MAPPING_ATTENTION_RULES}\n\n`,
    "\n\n",
  );
  assert.notEqual(ownerWithoutM1A17, ownerWithoutM1A16);
  const ownerWithoutM1A20 = ownerWithoutM1A17.replace(
    `\n\n${M1A20_MAPPING_DECISION_FRAME_RULES}\n\n`,
    "\n\n",
  );
  assert.notEqual(ownerWithoutM1A20, ownerWithoutM1A17);
  const ownerWithoutM1A18 = ownerWithoutM1A20.replace(
    `\n\n${M1A18_MAPPING_RESOLVED_RULES}\n\n`,
    "\n\n",
  );
  assert.notEqual(ownerWithoutM1A18, ownerWithoutM1A20);
  const ownerWithoutLaterUnits = ownerWithoutM1A18.replace(
    `\n\n${M1A19_DATA_INTAKE_FIELD_ROW_RULES}\n\n`,
    "\n\n",
  );
  assert.notEqual(ownerWithoutLaterUnits, ownerWithoutM1A18);
  assert.equal(ownerWithoutLaterUnits.includes(expected), true);
  assert.ok(ownerWithoutLaterUnits.indexOf(expected) < ownerWithoutLaterUnits.indexOf(".modeling-data-workspace {"));
});

test("preserves the exact M1A13 local-scrollport declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const expected = M1A13_LOCAL_SCROLLPORT_RULES;

  assert.equal(legacy.includes(".modeling-task-ribbon:has(.data-intake-local) {"), false);
  assert.equal(/(^|\n)\.data-intake-local\s*\{/m.test(legacy), false);
  assert.equal(owner.includes(expected), true);
  assert.ok(owner.indexOf(".modeling-data-ribbon-panel {\n  min-width: 0;") < owner.indexOf(expected));
  assert.ok(owner.indexOf(expected) < owner.indexOf(".modeling-data-ribbon-panel {\n  min-height: 0;\n  overflow: hidden;"));
});

test("preserves the exact M1A14 live mapping-blocker declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");

  assert.equal(legacy.includes(".data-mapping-decision .data-mapping-blockers {"), false);
  assert.equal(/(^|\n)\.data-mapping-blockers\s*\{/m.test(legacy), false);
  assert.equal(legacy.includes(".data-mapping-blockers strong {"), false);
  assert.equal(owner.includes(M1A14_MAPPING_BLOCKER_BASE_RULES), true);
  assert.equal(owner.includes(M1A14_MAPPING_BLOCKER_DENSITY_RULE), true);
  assert.ok(
    owner.indexOf(".data-mapping-table select {\n  min-height: var(--ux-input-min-block-size);")
      < owner.indexOf(M1A14_MAPPING_BLOCKER_BASE_RULES),
  );
  assert.ok(
    owner.indexOf(M1A14_MAPPING_BLOCKER_BASE_RULES)
      < owner.indexOf(".data-mapping-recovery-row {"),
  );
  assert.ok(
    owner.indexOf(".data-mapping-actions {\n  min-height: var(--ux-control-min-block-size);")
      < owner.indexOf(M1A14_MAPPING_BLOCKER_DENSITY_RULE),
  );
  assert.ok(
    owner.indexOf(M1A14_MAPPING_BLOCKER_DENSITY_RULE)
      < owner.indexOf(".modeling-data-workspace .modeling-data-intake :is("),
  );
});

test("preserves the exact M1A15 Data-intake surface declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");

  assert.equal(/(^|\n)\.modeling-data-intake\s*\{/m.test(legacy), false);
  assert.equal(
    legacy.includes(".modeling-main-surface.has-data-split .modeling-data-intake {"),
    false,
  );
  assert.equal(owner.includes(M1A15_DATA_INTAKE_SURFACE_RULES), true);
  assert.ok(
    owner.indexOf(".modeling-data-ribbon-panel {\n  min-width: 0;")
      < owner.indexOf(M1A15_DATA_INTAKE_SURFACE_RULES),
  );
  assert.ok(
    owner.indexOf(M1A15_DATA_INTAKE_SURFACE_RULES)
      < owner.indexOf(".modeling-task-ribbon:has(.data-intake-local) {"),
  );
});

test("preserves the exact M1A16 Local-file import-control declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");

  for (const selector of [
    ".modeling-main-surface:has(.data-source-decision-grid) .data-intake-local > .data-intake-row > label",
    ".modeling-main-surface:has(.data-source-decision-grid) .data-intake-local > .data-intake-row > label > :is(input, select)",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row select[name=\"local-test-run\"]",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > label",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > button",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row input[type=\"file\"]",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row input[type=\"file\"]::file-selector-button",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > button:disabled",
  ]) {
    assert.equal(legacy.includes(selector), false, `${selector} left layout.css`);
  }
  assert.equal(owner.includes(M1A16_LOCAL_IMPORT_CONTROL_RULES), true);
  assert.ok(
    owner.indexOf(M1A13_LOCAL_SCROLLPORT_RULES)
      < owner.indexOf(M1A16_LOCAL_IMPORT_CONTROL_RULES),
  );
  assert.ok(
    owner.indexOf(M1A16_LOCAL_IMPORT_CONTROL_RULES)
      < owner.indexOf(".modeling-data-ribbon-panel {\n  min-height: 0;\n  overflow: hidden;"),
  );
});

test("preserves the exact M1A17 mapping-attention declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");

  for (const selector of [
    ".data-intake-attention {",
    ".data-intake-attention label",
    ".data-intake-attention input",
    ".data-intake-attention select",
    ".data-intake-attention > strong",
    ".data-intake-attention label select:first-of-type",
    ".data-intake-attention > p",
    ".data-mapping-decision .data-intake-attention",
  ]) {
    assert.equal(legacy.includes(selector), false, `${selector} left layout.css`);
  }
  assert.equal(owner.includes(M1A17_MAPPING_ATTENTION_RULES), true);
  assert.ok(
    owner.indexOf(M1A16_LOCAL_IMPORT_CONTROL_RULES)
      < owner.indexOf(M1A17_MAPPING_ATTENTION_RULES),
  );
  assert.ok(
    owner.indexOf(M1A17_MAPPING_ATTENTION_RULES)
      < owner.indexOf(".modeling-data-ribbon-panel {\n  min-height: 0;\n  overflow: hidden;"),
  );
});

test("preserves the exact M1A18 mapping-resolved declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");

  for (const selector of [
    ".data-mapping-resolved label",
    ".data-mapping-resolved input",
    ".data-mapping-resolved select",
    ".data-mapping-resolved > span",
    ".data-mapping-resolved > strong",
    ".data-mapping-resolved label select:first-of-type",
    ".data-mapping-decision > .data-mapping-resolved",
    ".data-mapping-resolved :is(input, select)",
  ]) {
    assert.equal(legacy.includes(selector), false, `${selector} left layout.css`);
  }
  assert.equal(owner.includes(M1A18_MAPPING_RESOLVED_RULES), true);
  assert.ok(
    owner.indexOf(M1A17_MAPPING_ATTENTION_RULES)
      < owner.indexOf(M1A18_MAPPING_RESOLVED_RULES),
  );
  assert.ok(
    owner.indexOf(M1A18_MAPPING_RESOLVED_RULES)
      < owner.indexOf(".modeling-data-ribbon-panel {\n  min-height: 0;\n  overflow: hidden;"),
  );
});

test("preserves the exact M1A19 Data intake field-row declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");

  for (const selector of [
    ".data-intake-row {",
    ".data-intake-row label {",
    ".data-intake-row input,",
    ".data-intake-row select {",
    ".data-intake-row p {",
    ".data-intake-message {",
    ".data-intake-row :is(input, select) {",
  ]) {
    assert.equal(legacy.includes(selector), false, `${selector} left layout.css`);
  }
  assert.equal(legacy.includes(".data-intake-message.error {"), true);
  assert.equal(owner.includes(M1A19_DATA_INTAKE_FIELD_ROW_RULES), true);
  assert.ok(
    owner.indexOf(M1A16_LOCAL_IMPORT_CONTROL_RULES)
      < owner.indexOf(M1A19_DATA_INTAKE_FIELD_ROW_RULES),
  );
  assert.ok(
    owner.indexOf(M1A19_DATA_INTAKE_FIELD_ROW_RULES)
      < owner.indexOf(M1A17_MAPPING_ATTENTION_RULES),
  );
});

test("preserves the exact M1A20 mapping-decision frame declarations and cascade order", () => {
  const legacy = readFileSync(
    new URL("../apps/web/src/design/layout.css", import.meta.url),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const owner = readFileSync(
    new URL(
      "../apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\r\n/g, "\n");

  for (const selector of [
    ".data-mapping-decision {",
    ".data-mapping-decision .mapping-context-row {",
    ".modeling-main-surface:has(.data-intake-local) .data-source-decision-grid {",
    ".modeling-main-surface.has-data-split .data-mapping-decision select[name=\"local-data-schema\"] {",
  ]) {
    assert.equal(legacy.includes(selector), false, `${selector} left layout.css`);
  }
  assert.equal(owner.includes(M1A20_MAPPING_DECISION_FRAME_RULES), true);
  assert.ok(
    owner.indexOf(M1A17_MAPPING_ATTENTION_RULES)
      < owner.indexOf(M1A20_MAPPING_DECISION_FRAME_RULES),
  );
  assert.ok(
    owner.indexOf(M1A20_MAPPING_DECISION_FRAME_RULES)
      < owner.indexOf(M1A18_MAPPING_RESOLVED_RULES),
  );
});

test("keeps the audit regression selectors out of the generated dead batch", () => {
  const inventory = JSON.parse(readFileSync(
    new URL("../docs/17-evidence/issue-261-css-selector-inventory.json", import.meta.url),
    "utf8",
  ));
  for (const selector of [
    ".processing-workbench-page",
    ".modeling-support-drawer",
    ".card-preview-content",
  ]) {
    const row = inventory.selectors.find((candidate) => candidate.selector === selector);
    assert.ok(row, `${selector} is present`);
    assert.equal(row.flags.deadCandidate, false, `${selector} is not a dead candidate`);
    assert.equal(
      row.consumers.status,
      "production-subject-class-producer-observed",
      `${selector} has production producer evidence`,
    );
    assert.ok(
      row.consumers.productionProducerFiles.length > 0,
      `${selector} records its producer file`,
    );
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
  const completedM1A1 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A1-modeling-data-source-tabs",
  );
  assert.ok(completedM1A1);
  assert.deepEqual(completedM1A1.actualAfter, {
    cssRuleGroups: 2821,
    selectorRows: 3568,
    crossCssDuplicateRows: 13,
  });
  assert.equal(completedM1A1.selectorRowsRemoved, 5);
  assert.equal(completedM1A1.touchedRuleGroups, 5);
  assert.equal(completedM1A1.fullyRemovedRuleGroups, 5);
  assert.equal(completedM1A1.partiallyShrunkRuleGroups, 0);
  assert.deepEqual(completedM1A1.residualExactSelectorRows, []);
  for (const selector of completedM1A1.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A2 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A2-modeling-data-component-region",
  );
  assert.ok(completedM1A2);
  assert.deepEqual(completedM1A2.actualAfter, {
    cssRuleGroups: 2818,
    selectorRows: 3565,
    crossCssDuplicateRows: 13,
  });
  assert.equal(completedM1A2.selectorRowsRemoved, 3);
  assert.equal(completedM1A2.touchedRuleGroups, 3);
  assert.equal(completedM1A2.fullyRemovedRuleGroups, 3);
  assert.equal(completedM1A2.partiallyShrunkRuleGroups, 0);
  assert.deepEqual(completedM1A2.residualExactSelectorRows, []);
  for (const selector of completedM1A2.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A3 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A3-modeling-data-import-diagnostics",
  );
  assert.ok(completedM1A3);
  assert.deepEqual(completedM1A3.actualAfter, {
    cssRuleGroups: 2812,
    selectorRows: 3558,
    crossCssDuplicateRows: 13,
  });
  assert.equal(completedM1A3.selectorRowsRemoved, 7);
  assert.equal(completedM1A3.touchedRuleGroups, 6);
  assert.equal(completedM1A3.fullyRemovedRuleGroups, 6);
  assert.equal(completedM1A3.partiallyShrunkRuleGroups, 0);
  assert.deepEqual(completedM1A3.residualExactSelectorRows, []);
  for (const selector of completedM1A3.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A4 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A4-modeling-data-raw-source-preview",
  );
  assert.ok(completedM1A4);
  assert.deepEqual(completedM1A4.actualAfter, {
    cssRuleGroups: 2808,
    selectorRows: 3541,
    crossCssDuplicateRows: 13,
  });
  assert.equal(completedM1A4.selectorRowsRemoved, 17);
  assert.equal(completedM1A4.touchedRuleGroups, 12);
  assert.equal(completedM1A4.fullyRemovedRuleGroups, 4);
  assert.equal(completedM1A4.partiallyShrunkRuleGroups, 8);
  assert.deepEqual(completedM1A4.residualExactSelectorRows, []);
  for (const selector of completedM1A4.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A5 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A5-modeling-data-library-source-list",
  );
  assert.ok(completedM1A5);
  assert.deepEqual(completedM1A5.actualAfter, {
    cssRuleGroups: 2787,
    selectorRows: 3512,
    crossCssDuplicateRows: 13,
  });
  assert.equal(completedM1A5.historicalMemberIds.length, 29);
  assert.ok(completedM1A5.historicalMemberIds.includes("CSS-1020"));
  assert.equal(completedM1A5.selectorRowsRemoved, 29);
  assert.equal(completedM1A5.touchedRuleGroups, 21);
  assert.equal(completedM1A5.fullyRemovedRuleGroups, 21);
  assert.equal(completedM1A5.partiallyShrunkRuleGroups, 0);
  assert.deepEqual(completedM1A5.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A5.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A6 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A6-modeling-data-curve-row-label",
  );
  assert.ok(completedM1A6);
  assert.deepEqual(completedM1A6.actualAfter, {
    cssRuleGroups: 2784,
    selectorRows: 3509,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A6.historicalMemberIds, [
    "CSS-1497",
    "CSS-1498",
    "CSS-1499",
  ]);
  assert.equal(completedM1A6.selectorRowsRemoved, 3);
  assert.equal(completedM1A6.touchedRuleGroups, 3);
  assert.equal(completedM1A6.fullyRemovedRuleGroups, 3);
  assert.equal(completedM1A6.partiallyShrunkRuleGroups, 0);
  assert.deepEqual(completedM1A6.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A6.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A7 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A7-modeling-data-mapping-heading",
  );
  assert.ok(completedM1A7);
  assert.deepEqual(completedM1A7.actualAfter, {
    cssRuleGroups: 2781,
    selectorRows: 3505,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A7.historicalMemberIds, [
    "CSS-1019",
    "CSS-1020",
    "CSS-1021",
    "CSS-1579",
  ]);
  assert.equal(completedM1A7.selectorRowsRemoved, 4);
  assert.equal(completedM1A7.touchedRuleGroups, 4);
  assert.equal(completedM1A7.fullyRemovedRuleGroups, 3);
  assert.equal(completedM1A7.partiallyShrunkRuleGroups, 1);
  assert.deepEqual(completedM1A7.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A7.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A8 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A8-modeling-data-optional-channel",
  );
  assert.ok(completedM1A8);
  assert.deepEqual(completedM1A8.actualAfter, {
    cssRuleGroups: 2777,
    selectorRows: 3501,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A8.historicalMemberIds, [
    "CSS-1021",
    "CSS-1022",
    "CSS-1460",
    "CSS-1461",
  ]);
  assert.equal(completedM1A8.selectorRowsRemoved, 4);
  assert.equal(completedM1A8.touchedRuleGroups, 4);
  assert.equal(completedM1A8.fullyRemovedRuleGroups, 4);
  assert.equal(completedM1A8.partiallyShrunkRuleGroups, 0);
  assert.deepEqual(completedM1A8.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A8.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A9 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A9-modeling-data-mapping-table",
  );
  assert.ok(completedM1A9);
  assert.deepEqual(completedM1A9.actualAfter, {
    cssRuleGroups: 2767,
    selectorRows: 3482,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A9.historicalMemberIds, [
    "CSS-1001",
    "CSS-1008",
    "CSS-1009",
    "CSS-1010",
    "CSS-1011",
    "CSS-1012",
    "CSS-1013",
    "CSS-1014",
    "CSS-1021",
    "CSS-1036",
    "CSS-1461",
    "CSS-1474",
    "CSS-1475",
    "CSS-1564",
    "CSS-1565",
    "CSS-1571",
    "CSS-1577",
    "CSS-1578",
    "CSS-1584",
  ]);
  assert.equal(completedM1A9.selectorRowsRemoved, 19);
  assert.equal(completedM1A9.touchedRuleGroups, 15);
  assert.equal(completedM1A9.fullyRemovedRuleGroups, 10);
  assert.equal(completedM1A9.partiallyShrunkRuleGroups, 5);
  assert.deepEqual(completedM1A9.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A9.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A10 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A10-modeling-data-split-frame",
  );
  assert.ok(completedM1A10);
  assert.deepEqual(completedM1A10.actualAfter, {
    cssRuleGroups: 2757,
    selectorRows: 3470,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A10.historicalMemberIds, [
    "CSS-1431",
    "CSS-1432",
    "CSS-1433",
    "CSS-1434",
    "CSS-1435",
    "CSS-1436",
    "CSS-1437",
    "CSS-1438",
    "CSS-1439",
    "CSS-1440",
    "CSS-1441",
    "CSS-1442",
  ]);
  assert.equal(completedM1A10.selectorRowsRemoved, 12);
  assert.equal(completedM1A10.touchedRuleGroups, 10);
  assert.equal(completedM1A10.fullyRemovedRuleGroups, 10);
  assert.equal(completedM1A10.partiallyShrunkRuleGroups, 0);
  assert.deepEqual(completedM1A10.residualExactSelectorRows, []);
  for (const selector of completedM1A10.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A11 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A11-modeling-data-file-details",
  );
  assert.ok(completedM1A11);
  assert.deepEqual(completedM1A11.actualAfter, {
    cssRuleGroups: 2753,
    selectorRows: 3465,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A11.historicalMemberIds, [
    "CSS-1436",
    "CSS-1437",
    "CSS-1438",
    "CSS-1452",
    "CSS-1548",
  ]);
  assert.equal(completedM1A11.selectorRowsRemoved, 5);
  assert.equal(completedM1A11.touchedRuleGroups, 5);
  assert.equal(completedM1A11.fullyRemovedRuleGroups, 4);
  assert.equal(completedM1A11.partiallyShrunkRuleGroups, 1);
  assert.deepEqual(completedM1A11.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A11.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A12 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A12-modeling-data-mapping-change-actions",
  );
  assert.ok(completedM1A12);
  assert.deepEqual(completedM1A12.actualAfter, {
    cssRuleGroups: 2738,
    selectorRows: 3444,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A12.historicalMemberIds, [
    "CSS-1014",
    "CSS-1017",
    "CSS-1018",
    "CSS-1019",
    "CSS-1021",
    "CSS-1439",
    "CSS-1440",
    "CSS-1441",
    "CSS-1443",
    "CSS-1445",
    "CSS-1449",
    "CSS-1451",
    "CSS-1452",
    "CSS-1453",
    "CSS-1455",
    "CSS-1456",
    "CSS-1458",
    "CSS-1459",
    "CSS-1540",
    "CSS-1549",
    "CSS-1558",
  ]);
  assert.equal(completedM1A12.selectorRowsRemoved, 21);
  assert.equal(completedM1A12.touchedRuleGroups, 20);
  assert.equal(completedM1A12.fullyRemovedRuleGroups, 15);
  assert.equal(completedM1A12.partiallyShrunkRuleGroups, 5);
  assert.deepEqual(completedM1A12.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A12.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A13 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A13-modeling-data-local-scrollport",
  );
  assert.ok(completedM1A13);
  assert.deepEqual(completedM1A13.actualAfter, {
    cssRuleGroups: 2734,
    selectorRows: 3438,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A13.historicalMemberIds, [
    "CSS-0910",
    "CSS-0911",
    "CSS-0912",
    "CSS-0971",
    "CSS-0986",
    "CSS-1007",
  ]);
  assert.equal(completedM1A13.selectorRowsRemoved, 6);
  assert.equal(completedM1A13.touchedRuleGroups, 5);
  assert.equal(completedM1A13.fullyRemovedRuleGroups, 4);
  assert.equal(completedM1A13.partiallyShrunkRuleGroups, 1);
  assert.deepEqual(completedM1A13.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A13.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A14 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A14-modeling-data-mapping-blocker",
  );
  assert.ok(completedM1A14);
  assert.deepEqual(completedM1A14.actualAfter, {
    cssRuleGroups: 2731,
    selectorRows: 3434,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A14.historicalMemberIds, [
    "CSS-1007",
    "CSS-1014",
    "CSS-1015",
    "CSS-1511",
  ]);
  assert.equal(completedM1A14.selectorRowsRemoved, 4);
  assert.equal(completedM1A14.touchedRuleGroups, 4);
  assert.equal(completedM1A14.fullyRemovedRuleGroups, 3);
  assert.equal(completedM1A14.partiallyShrunkRuleGroups, 1);
  assert.deepEqual(completedM1A14.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A14.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A15 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A15-modeling-data-intake-surface",
  );
  assert.ok(completedM1A15);
  assert.deepEqual(completedM1A15.actualAfter, {
    cssRuleGroups: 2728,
    selectorRows: 3430,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A15.historicalMemberIds, [
    "CSS-0966",
    "CSS-0969",
    "CSS-1429",
    "CSS-1507",
  ]);
  assert.equal(completedM1A15.selectorRowsRemoved, 4);
  assert.equal(completedM1A15.touchedRuleGroups, 4);
  assert.equal(completedM1A15.fullyRemovedRuleGroups, 3);
  assert.equal(completedM1A15.partiallyShrunkRuleGroups, 1);
  assert.deepEqual(completedM1A15.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A15.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A16 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A16-modeling-data-local-import-controls",
  );
  assert.ok(completedM1A16);
  assert.deepEqual(completedM1A16.actualAfter, {
    cssRuleGroups: 2720,
    selectorRows: 3414,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A16.historicalMemberIds, [
    "CSS-1416",
    "CSS-1418",
    "CSS-1420",
    "CSS-1436",
    "CSS-1437",
    "CSS-1438",
    "CSS-1439",
    "CSS-1440",
    "CSS-1441",
    "CSS-1442",
    "CSS-1443",
    "CSS-1445",
    "CSS-1520",
    "CSS-1521",
    "CSS-1522",
    "CSS-1523",
  ]);
  assert.equal(completedM1A16.selectorRowsRemoved, 16);
  assert.equal(completedM1A16.touchedRuleGroups, 13);
  assert.equal(completedM1A16.fullyRemovedRuleGroups, 8);
  assert.equal(completedM1A16.partiallyShrunkRuleGroups, 5);
  assert.deepEqual(completedM1A16.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A16.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A17 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A17-modeling-data-mapping-attention",
  );
  assert.ok(completedM1A17);
  assert.deepEqual(completedM1A17.actualAfter, {
    cssRuleGroups: 2713,
    selectorRows: 3397,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A17.historicalMemberIds, [
    "CSS-0967",
    "CSS-0970",
    "CSS-0974",
    "CSS-0975",
    "CSS-0982",
    "CSS-0984",
    "CSS-0986",
    "CSS-0988",
    "CSS-0999",
    "CSS-1002",
    "CSS-1003",
    "CSS-1004",
    "CSS-1416",
    "CSS-1417",
    "CSS-1419",
    "CSS-1494",
    "CSS-1502",
  ]);
  assert.equal(completedM1A17.selectorRowsRemoved, 17);
  assert.equal(completedM1A17.touchedRuleGroups, 16);
  assert.equal(completedM1A17.fullyRemovedRuleGroups, 7);
  assert.equal(completedM1A17.partiallyShrunkRuleGroups, 9);
  assert.deepEqual(completedM1A17.residualExactSelectorRows, []);
  for (const selector of completedM1A17.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A18 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A18-modeling-data-mapping-resolved",
  );
  assert.ok(completedM1A18);
  assert.deepEqual(completedM1A18.actualAfter, {
    cssRuleGroups: 2709,
    selectorRows: 3387,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A18.historicalMemberIds, [
    "CSS-0969",
    "CSS-0972",
    "CSS-0973",
    "CSS-0978",
    "CSS-0979",
    "CSS-0980",
    "CSS-0981",
    "CSS-0998",
    "CSS-1479",
    "CSS-1486",
  ]);
  assert.equal(completedM1A18.selectorRowsRemoved, 10);
  assert.equal(completedM1A18.touchedRuleGroups, 9);
  assert.equal(completedM1A18.fullyRemovedRuleGroups, 4);
  assert.equal(completedM1A18.partiallyShrunkRuleGroups, 5);
  assert.deepEqual(completedM1A18.residualExactSelectorRows, []);
  for (const selector of completedM1A18.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A19 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A19-modeling-data-intake-field-rows",
  );
  assert.ok(completedM1A19);
  assert.deepEqual(completedM1A19.actualAfter, {
    cssRuleGroups: 2703,
    selectorRows: 3378,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A19.historicalMemberIds, [
    "CSS-0966",
    "CSS-0967",
    "CSS-0968",
    "CSS-0969",
    "CSS-0970",
    "CSS-0971",
    "CSS-0975",
    "CSS-1470",
    "CSS-1476",
  ]);
  assert.equal(completedM1A19.selectorRowsRemoved, 9);
  assert.equal(completedM1A19.touchedRuleGroups, 8);
  assert.equal(completedM1A19.fullyRemovedRuleGroups, 6);
  assert.equal(completedM1A19.partiallyShrunkRuleGroups, 2);
  assert.deepEqual(completedM1A19.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A19.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  const completedM1A20 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === "M1A20-modeling-data-mapping-decision-frame",
  );
  assert.ok(completedM1A20);
  assert.deepEqual(completedM1A20.actualAfter, {
    cssRuleGroups: 2699,
    selectorRows: 3374,
    crossCssDuplicateRows: 14,
  });
  assert.deepEqual(completedM1A20.historicalMemberIds, [
    "CSS-0977",
    "CSS-0978",
    "CSS-1388",
    "CSS-1389",
  ]);
  assert.equal(completedM1A20.selectorRowsRemoved, 4);
  assert.equal(completedM1A20.touchedRuleGroups, 4);
  assert.equal(completedM1A20.fullyRemovedRuleGroups, 4);
  assert.equal(completedM1A20.partiallyShrunkRuleGroups, 0);
  assert.deepEqual(completedM1A20.residualExactSelectorRows, []);
  assert.equal(inventory.summary.byMigrationBatch["M1A-modeling-data"], 23);
  for (const selector of completedM1A20.exactLegacySelectors) {
    assert.equal(
      inventory.selectors.some((row) => row.selector === selector),
      false,
      `${selector} no longer has exact legacy ownership`,
    );
  }
  assert.deepEqual(inventory.migrationPlan.nextBoundedUnit, {
    id: "M1A21-modeling-data-component-region",
    status: "owner-packet-required",
    scope: "Select one remaining M1A Data component region from the regenerated inventory after M1A20; do not migrate all remaining M1A rows together.",
  });
});

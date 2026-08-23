import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const FIXTURE_PATH = join(ROOT, "scripts/fixtures/issue-261-m1e5-producer-routed-residual.json");
const FIXTURE = JSON.parse(readFileSync(FIXTURE_PATH, "utf8"));
const MANIFEST_PATH = join(ROOT, "docs/17-evidence/images/issue-261-m1e5-producer-routed-residual/manifest.json");
const MANIFEST = JSON.parse(readFileSync(MANIFEST_PATH, "utf8"));
const INVENTORY_TEXT = execFileSync(
  "git",
  ["show", `${FIXTURE.baseSha}:${FIXTURE.frozenInventory.path}`],
  { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
);
const INVENTORY = JSON.parse(INVENTORY_TEXT);
const TARGET_IDS = new Set(FIXTURE.approvedIds);
const TARGET_ROWS = INVENTORY.selectors.filter((row) => TARGET_IDS.has(row.id));
const TARGET_BY_ID = new Map(TARGET_ROWS.map((row) => [row.id, row]));
const OWNER_BY_ID = new Map(
  Object.values(FIXTURE.owners)
    .flatMap((owner) => owner.ids.filter((id) => TARGET_IDS.has(id)).map((id) => [id, owner.path])),
);
const LEGACY_PATHS = FIXTURE.legacySources.map(({ path }) => path);
const OWNER_PATHS = [...new Set(Object.values(FIXTURE.owners).map(({ path }) => path))];
const LIVE_SELECTOR_IDS = [
  "CSS-0160", "CSS-0161", "CSS-0162", "CSS-0164", "CSS-0165", "CSS-0167", "CSS-0168", "CSS-0169", "CSS-0170", "CSS-0171", "CSS-0178", "CSS-0179", "CSS-0180", "CSS-0181", "CSS-0182", "CSS-0183", "CSS-0455", "CSS-0886", "CSS-0897", "CSS-0898", "CSS-0961", "CSS-1008", "CSS-1009", "CSS-1010", "CSS-1011", "CSS-1012", "CSS-1013", "CSS-1014", "CSS-1114", "CSS-1115", "CSS-1116", "CSS-1117", "CSS-1118", "CSS-1120", "CSS-1122", "CSS-1123", "CSS-1124", "CSS-1126",
];
const NA_SOURCE_TEST_SELECTOR_IDS = [
  "CSS-0158", "CSS-0163", "CSS-0166", "CSS-0172", "CSS-0173", "CSS-0174", "CSS-0175", "CSS-0176", "CSS-0887", "CSS-0984", "CSS-0985", "CSS-1019", "CSS-1020", "CSS-1057", "CSS-1058", "CSS-1059", "CSS-1121", "CSS-1125", "CSS-1157", "CSS-1158",
];
const LIVE_ROUTE_COUNTS = {
  "materials-curves": 16,
  "modeling-data-metal": 11,
  "governed-import": 7,
  exports: 2,
  "canonical-test-json": 1,
  "modeling-fit-elastomer": 1,
};
const CAPTURED_TARGET_TOPOLOGY_IDS = [
  "modeling-data-metal", "materials-curves", "governed-import", "canonical-test-json", "exports", "modeling-fit-elastomer",
];
const UNIQUE_TOPOLOGY_IDS = [
  "modeling-data-metal", "modeling-process-elastomer-hold", "materials-curves", "governed-import", "canonical-test-json", "exports", "modeling-fit-polymer", "modeling-export-polymer", "modeling-fit-elastomer", "modeling-export-elastomer",
];
const NO_SCREENSHOT_STATE_IDS = [
  "modeling-process-metal", "modeling-fit-metal", "modeling-export-metal", "modeling-fit-polymer", "modeling-export-polymer", "modeling-export-elastomer",
];
const NO_SCREENSHOT_BROWSER_ROUTE_IDS = ["modeling-fit-polymer", "modeling-export-polymer", "modeling-export-elastomer"];
const CONDITIONAL_CURVE_GROUP_IDS = ["CSS-0172", "CSS-0173", "CSS-0174", "CSS-0175", "CSS-0176"];
const CONDITIONAL_CURVE_GROUP_REASON = "The normal producer SVG five-viewport route does not materialize the conditional active/tooltip state; CSS-0172–CSS-0176 remain source/bundle/component-tested with no DOM/state fabrication.";
const GOVERNED_IMPORT_0887_REASON = "The normal governed-import producer does not materialize the conditional preview .curve-heading row; CSS-0887 remains source/component/bundle-tested and no live locator is claimed.";

function readBaseSource(path) {
  return execFileSync("git", ["show", `${FIXTURE.baseSha}:${path}`], {
    cwd: ROOT,
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
  });
}

function readCurrentSource(path) {
  return readFileSync(join(ROOT, path), "utf8");
}

function declarationSignature(declarations) {
  return createHash("sha256")
    .update(JSON.stringify(declarations.map(({ property, value, important }) => [property, value, important])))
    .digest("hex");
}

function normalizeSpace(value) {
  return value.replace(/\s+/g, " ").trim();
}

function rowIdentity(row) {
  return [
    normalizeSpace(row.selector),
    (row.source?.atContext ?? row.atContext ?? []).join(" | "),
    row.declarations?.signatureSha256 ?? declarationSignature(row.declarations),
  ].join("\0");
}

function countByIdentity(rows) {
  const counts = new Map();
  for (const row of rows) {
    const key = rowIdentity(row);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

function parseSources(paths, readSource) {
  return paths.flatMap((path) => parseCss(path, readSource(path), null));
}

const baseLegacyRows = parseSources(LEGACY_PATHS, readBaseSource);
const currentLegacyRows = parseSources(LEGACY_PATHS, readCurrentSource);
const currentOwnerRows = parseSources(OWNER_PATHS, readCurrentSource);
const baseCounts = countByIdentity(baseLegacyRows);
const currentCounts = countByIdentity(currentLegacyRows);

test("M1E5 fixture is pinned to the exact 58-row / 49-group approved move", () => {
  assert.equal(createHash("sha256").update(INVENTORY_TEXT).digest("hex"), FIXTURE.frozenInventory.sha256);
  assert.equal(TARGET_ROWS.length, FIXTURE.approvedMove.rows);
  assert.equal(new Set(TARGET_ROWS.map((row) => `${row.source.path}#${row.source.ruleIndex}`)).size, FIXTURE.approvedMove.groups);
  const tuples = [...TARGET_ROWS]
    .sort((left, right) => left.source.mainImportRank - right.source.mainImportRank
      || left.source.ruleIndex - right.source.ruleIndex
      || left.source.selectorIndex - right.source.selectorIndex)
    .map((row) => [
      row.id,
      row.source.path,
      row.source.mainImportRank,
      row.source.ruleIndex,
      row.source.selectorIndex,
      row.selector,
      row.source.atContext,
      row.specificity,
      row.declarations.properties,
      row.declarations.importantProperties,
      row.declarations.signatureSha256,
    ]);
  assert.equal(createHash("sha256").update(JSON.stringify(tuples)).digest("hex"), FIXTURE.approvedMove.tupleSha256);
});

test("selector application matrix covers every moved row without digest false-positives", () => {
  const application = MANIFEST.capture_plan.selector_application;
  assert.ok(application, "capture_plan.selector_application is required");
  assert.deepEqual(application.status_counts, { LIVE: 38, N_A_SOURCE_TEST: 20, RETAINED_HOLD: 2 });
  assert.deepEqual(application.live_ids, LIVE_SELECTOR_IDS);
  assert.deepEqual(application.na_source_test.map(({ id }) => id), NA_SOURCE_TEST_SELECTOR_IDS);
  const conditionalCurveGroup = application.na_source_test.filter(({ id }) => CONDITIONAL_CURVE_GROUP_IDS.includes(id));
  assert.deepEqual(conditionalCurveGroup.map(({ id }) => id), CONDITIONAL_CURVE_GROUP_IDS);
  for (const record of conditionalCurveGroup) {
    assert.equal(record.reason, CONDITIONAL_CURVE_GROUP_REASON, `${record.id}: conditional group reason drifted`);
    assert.match(record.source_evidence?.source ?? "", /curve-contract-chart\.tsx/);
    assert.match(record.source_evidence?.component ?? "", /curve-contract-chart\.test\.tsx/);
    assert.match(record.source_evidence?.bundle ?? "", /bundle/);
  }
  const governedImport0887 = application.na_source_test.find(({ id }) => id === "CSS-0887");
  assert.equal(governedImport0887?.reason, GOVERNED_IMPORT_0887_REASON);
  assert.match(governedImport0887?.source_evidence?.source ?? "", /design\/primitives\.css/);
  assert.match(governedImport0887?.source_evidence?.component ?? "", /governed-import-workbench\.tsx/);
  assert.match(governedImport0887?.source_evidence?.import_chain ?? "", /app\.tsx.*governed-import-workbench/);
  assert.match(governedImport0887?.source_evidence?.bundle ?? "", /bundle/);
  assert.deepEqual(application.retained_hold_ids, FIXTURE.retainedBoundary.ids);
  assert.deepEqual(application.live_route_counts, LIVE_ROUTE_COUNTS);
  const contracts = application.live_contracts;
  assert.equal(contracts.length, LIVE_SELECTOR_IDS.length);
  assert.deepEqual(contracts.map(({ id }) => id), LIVE_SELECTOR_IDS);
  for (const contract of contracts.filter(({ route_id }) => route_id === "modeling-data-metal")) {
    assert.match(contract.locator, /^\.modeling-workspace-stage-data /, `${contract.id}: Data locator must use the visible stage scope`);
    assert.equal(contract.locator.includes(".modeling-data-plot"), false, `${contract.id}: stale Data plot scope`);
  }
  assert.deepEqual(Object.keys(application.intended_properties), LIVE_SELECTOR_IDS);
  const observedRouteCounts = contracts.reduce((counts, contract) => ({
    ...counts,
    [contract.route_id]: (counts[contract.route_id] ?? 0) + 1,
  }), {});
  assert.deepEqual(observedRouteCounts, LIVE_ROUTE_COUNTS);
  const digestIds = FIXTURE.approvedIds.filter((id) => TARGET_BY_ID.get(id)?.selector.includes("digest-line"));
  assert.deepEqual(digestIds, ["CSS-1057", "CSS-1058", "CSS-1059"]);
  assert.equal(LIVE_SELECTOR_IDS.some((id) => digestIds.includes(id)), false, "digest selectors must never be LIVE");
  for (const contract of contracts) {
    const frozen = TARGET_BY_ID.get(contract.id);
    assert.ok(frozen, `${contract.id}: contract must point at a frozen target row`);
    assert.equal(typeof contract.locator, "string");
    assert.equal(typeof contract.base_selector, "string");
    assert.deepEqual(application.intended_properties[contract.id], frozen.declarations.properties, `${contract.id}: intended properties drifted`);
  }
  for (const record of application.na_source_test) {
    assert.ok(record.reason && record.reason.length > 20, `${record.id}: N/A reason is required`);
    assert.ok(record.source_evidence?.source && record.source_evidence?.component && record.source_evidence?.import_chain && record.source_evidence?.bundle, `${record.id}: exact source/component/import/bundle proof is required`);
    assert.equal(record.disposition, "N/A_SOURCE_TEST");
  }
});

test("direct-route equivalence groups are source-backed and aliases are not separate captures", () => {
  const topology = MANIFEST.capture_plan.topology_matrix;
  assert.deepEqual(topology?.unique_topologies, UNIQUE_TOPOLOGY_IDS);
  assert.deepEqual(topology?.captured_target_topologies, CAPTURED_TARGET_TOPOLOGY_IDS);
  assert.deepEqual(topology?.no_screenshot_states?.map(({ id }) => id), NO_SCREENSHOT_STATE_IDS);
  for (const state of topology?.no_screenshot_states ?? []) {
    assert.equal(state.disposition, "N/A_REDUNDANT_NO_LIVE_TARGETS", `${state.id}: no-screenshot disposition drifted`);
    assert.match(state.reason, /^The |^N\/A_REDUNDANT_NO_LIVE_TARGETS:/, `${state.id}: no-screenshot reason is required`);
  }
  const groups = topology?.equivalence_groups;
  assert.deepEqual(groups, [
    { id: "modeling-data-metal", canonical: "modeling-data-metal", aliases: ["modeling-alias-data"], source_routes: ["/modeling", "/datasets/processing"] },
    { id: "modeling-process-metal", canonical: "modeling-process-metal", aliases: ["modeling-alias-process"], source_routes: ["/modeling", "/datasets/processing"] },
  ]);
  const app = readCurrentSource("apps/web/src/app.tsx");
  assert.match(app, /path === "\/datasets\/processing"[\s\S]*MaterialModelingWorkspace/);
  assert.match(app, /path === "\/modeling"[\s\S]*MaterialModelingWorkspace/);
  for (const route of MANIFEST.capture_plan.route_matrix) {
    if (route.capture_disposition === "collapsed-equivalence") {
      assert.equal(route.required_viewports.length, 0, `${route.id}: alias must not duplicate five captures`);
      assert.equal(route.equivalent_to, route.equivalence_group);
    } else if (route.capture_disposition === "no-screenshot-technical") {
      assert.deepEqual(route.required_viewports, []);
      assert.deepEqual(route.required_crops, []);
      assert.match(route.reason, /^N\/A_REDUNDANT_NO_LIVE_TARGETS:/);
    } else {
      assert.deepEqual(route.required_viewports, FIXTURE.requiredViewports ?? ["1366x768", "1440x900", "1920x1080", "2560x1440", "3840x2160"]);
    }
  }
});

test("browser evidence materializes each viewport on a fresh page", () => {
  const spec = readCurrentSource("apps/web/e2e/issue-261-m1e5-producer-routed-residual.spec.ts");
  assert.equal(spec.match(/\bpage\.setViewportSize/g)?.length ?? 0, 0, "loaded-page viewport resize is forbidden");
  const helperStart = spec.indexOf("async function openFreshDemoPage");
  assert.ok(helperStart >= 0, "fresh-page viewport helper is required");
  const viewportSetup = spec.indexOf("freshPage.setViewportSize", helperStart);
  const sessionSetup = spec.indexOf("bootstrapDemoSession(freshPage, request)", helperStart);
  assert.ok(viewportSetup >= 0 && sessionSetup > viewportSetup, "viewport must be set before session/navigation materialization");
  assert.match(spec, /openFreshDemoPage\(context, request, viewport\)/, "five-viewport captures must use fresh pages");
  assert.match(spec, /openFreshDemoPage\(context, request, viewports\[1\]\)/, "1440 aliases/recovery must use a fresh page");
  assert.match(spec, /"CSS-1125"/, "CSS-1125 must remain represented in the source-test partition");
  assert.doesNotMatch(spec, /hide-series|restorePrimaryDataLegend|button\.hidden/, "hidden-series CSS-1125 must remain source-tested only");
  assert.match(spec, /"CSS-0158"[\s\S]*"CSS-0163"/, "CSS-0158 must remain in the N/A source-test partition");
  assert.doesNotMatch(spec, /id: "CSS-0158"[\s\S]*materials-curves/, "CSS-0158 must not have a live application contract");
  assert.doesNotMatch(spec, /chart\.focus|keyboard\.press|focus-visible|activeElement/, "CSS-0158 focus state must remain source-tested only");
  const materialsPreparationStart = spec.indexOf("async function prepareSelectorApplicationState");
  const materialsPreparationEnd = spec.indexOf("\n}\n\nasync function assertSelectorApplications", materialsPreparationStart);
  assert.ok(materialsPreparationStart >= 0 && materialsPreparationEnd > materialsPreparationStart, "materials preparation helper is required");
  const materialsPreparation = spec.slice(materialsPreparationStart, materialsPreparationEnd);
  assert.match(materialsPreparation, /details\.curve-evidence/, "materials curve disclosure remains available for other live contracts");
  assert.doesNotMatch(materialsPreparation, /focus|keyboard|activeElement/, "materials preparation must not materialize CSS-0158 focus state");
  const materialsRouteStart = spec.indexOf('id: "materials-curves"');
  const materialsRouteEnd = spec.indexOf("\n  },", materialsRouteStart);
  assert.ok(materialsRouteStart >= 0 && materialsRouteEnd > materialsRouteStart, "materials-curves route case is required");
  const materialsRoute = spec.slice(materialsRouteStart, materialsRouteEnd);
  assert.match(materialsRoute, /selectors: \["\.contract-curve-frame", "\.contract-curve-heading"\]/, "materials CSSOM membership must retain the rendered curve selectors");
  assert.doesNotMatch(materialsRoute, /selectors:[^\n]*"\.curve-evidence"/, "materials CSSOM membership must not include the non-target root .curve-evidence sentinel");
  for (const routeId of NO_SCREENSHOT_BROWSER_ROUTE_IDS) {
    const routeStart = spec.indexOf(`id: "${routeId}"`);
    const routeEnd = spec.indexOf("\n  },", routeStart);
    assert.ok(routeStart >= 0 && routeEnd > routeStart, `${routeId}: route case is required`);
    assert.match(spec.slice(routeStart, routeEnd), /captureDisposition: "no-screenshot-technical"/, `${routeId}: browser screenshot test must remain skipped`);
  }
  const primaryStart = spec.indexOf('test("authenticated Modeling Data surface renders the exact Test Data producer at five CSS viewports"');
  const primaryEnd = spec.indexOf('\n  });\n\n  test("authenticated elastomer Fit journey', primaryStart);
  assert.ok(primaryStart >= 0 && primaryEnd > primaryStart, "Data capture and handoff assertions are required");
  const primaryJourney = spec.slice(primaryStart, primaryEnd);
  assert.match(primaryJourney, /for \(const viewport of viewports\)/, "Data topology must capture all five viewports");
  assert.equal((primaryJourney.match(/capturePrimaryStage\(/g) ?? []).length, 1, "Data journey must have one capture call site");
  assert.doesNotMatch(primaryJourney, /previewProcess|saveProcessForFit|previewAndSaveFit|prepareMetalExport|modeling-fit-metal|modeling-export-metal/, "Data journey must not mutate or capture removed metal stages");
  assert.doesNotMatch(primaryJourney, /locator\("body"\)\.toContainText\("CMP-DEMO-DP780-TEST-JSON"\)/, "normal-surface evidence must not assert the hidden Test Data document key");
  assert.match(primaryJourney, /viewport\.name === "1440x900"/);
  assert.match(primaryJourney, /Continue to Process/);
  assert.match(primaryJourney, /modeling-work-title h1.*Process Test Data/s, "Process handoff must assert its visible heading");
  assert.match(primaryJourney, /modeling-work-title > span.*DP780 \/ Tensile test 0001/s, "Process handoff must assert the visible grade/test identity");
  assert.match(primaryJourney, /current-process-input/);
  assert.match(primaryJourney, /process-input-role/);
  assert.match(primaryJourney, /Blocked · choose Test Data in Data/);
  assert.match(primaryJourney, /Elastic range end/);
  assert.match(primaryJourney, /Preview changes/);
});

test("legacy CSS is an exact complement of the frozen producer source", () => {
  const targetIdentities = new Set(TARGET_ROWS.map(rowIdentity));
  for (const row of TARGET_ROWS) assert.equal(currentCounts.get(rowIdentity(row)) ?? 0, 0, `${row.id}: target remains in legacy CSS`);
  for (const [identity, count] of baseCounts) {
    if (targetIdentities.has(identity)) continue;
    assert.equal(currentCounts.get(identity) ?? 0, count, `non-target identity changed: ${identity}`);
  }
  assert.equal(currentLegacyRows.length, baseLegacyRows.length - FIXTURE.approvedMove.rows);
  assert.equal(new Set(currentLegacyRows.map((row) => `${row.path}#${row.ruleIndex}`)).size, FIXTURE.expectedAfter.cssRuleGroups);
  assert.equal(currentLegacyRows.length, FIXTURE.expectedAfter.selectorRows);
  for (const id of FIXTURE.retainedBoundary.ids) {
    const row = INVENTORY.selectors.find((candidate) => candidate.id === id);
    assert.ok(row, `${id}: retained boundary row missing`);
    assert.equal(currentCounts.get(rowIdentity(row)) ?? 0, 1, `${id}: hold row must remain in global producer`);
  }
});

test("owner stylesheets contain every approved target once with preserved declarations", () => {
  const ownerMatches = new Map();
  for (const row of currentOwnerRows) {
    const id = TARGET_ROWS.find((target) => rowIdentity(target) === rowIdentity(row))?.id;
    if (!id) continue;
    assert.equal(ownerMatches.has(id), false, `${id}: duplicate owner identity`);
    ownerMatches.set(id, row);
  }
  assert.equal(ownerMatches.size, FIXTURE.approvedMove.rows);
  for (const [id, row] of ownerMatches) {
    assert.equal(row.path, OWNER_BY_ID.get(id), `${id}: wrong truthful owner`);
    const frozen = TARGET_BY_ID.get(id);
    assert.deepEqual(row.atContext, frozen.source.atContext, `${id}: at-context changed`);
    assert.equal(declarationSignature(row.declarations), frozen.declarations.signatureSha256, `${id}: declaration signature changed`);
  }
});

test("mixed groups retain their named peers and imports keep feature CSS before layout", () => {
  for (const group of Object.values(FIXTURE.mixedGroups).flat()) {
    for (const id of group.retainedIds) {
      const row = INVENTORY.selectors.find((candidate) => candidate.id === id);
      assert.ok(row, `${id}: mixed retained peer missing`);
      assert.equal(currentCounts.get(rowIdentity(row)) ?? 0, 1, `${id}: mixed peer moved or changed`);
    }
  }
  const main = readCurrentSource("apps/web/src/main.tsx");
  const preview = readCurrentSource("apps/web/.storybook/preview.ts");
  for (const source of [main, preview]) {
    const feature = source.indexOf("governed-import-route.css");
    const layout = source.indexOf("layout.css");
    assert.ok(feature >= 0 && layout > feature, "governed import CSS must load before layout CSS");
  }
});

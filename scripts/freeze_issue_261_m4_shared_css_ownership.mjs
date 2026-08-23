import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { makeInventory } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const BASE_SHA = "01d2cb0a48551e2c02175d6969fb13aeac094438";
const FIXTURE_PATH = "scripts/fixtures/issue-261-m4-shared-css-ownership.json";
const EXPECTED_CANDIDATE_DIGEST = "33f059efa47e227d22e8a57f9922c054288a9d42816b62603340b58a9b2d7684";

function idSet(value) {
  return new Set(value.trim().split(/\s+/).filter(Boolean));
}

const ACCEPTED_IN_PLACE = idSet(`
  CSS-0001 CSS-0023 CSS-0027 CSS-0028 CSS-0029 CSS-0033 CSS-0034
  CSS-0060 CSS-0061 CSS-0062 CSS-0063
`);

const HOLD_MIXED_SOURCE_GROUP = idSet(`
  CSS-0302 CSS-0340 CSS-0341 CSS-0342 CSS-0343 CSS-0344 CSS-0351
  CSS-0500 CSS-0501 CSS-0502 CSS-0503 CSS-0509 CSS-0782 CSS-0950 CSS-0958
`);
const HOLD_MIXED_SELECTOR_FAMILY = idSet("CSS-0784 CSS-0810");
const HOLD_GLOBAL_TYPE_CASCADE = idSet("CSS-0755 CSS-0946");
const HOLD = new Set([
  ...HOLD_MIXED_SOURCE_GROUP,
  ...HOLD_MIXED_SELECTOR_FAMILY,
  ...HOLD_GLOBAL_TYPE_CASCADE,
]);

// These four Fit rules were misclassified as zero-consumer candidates because
// the inventory's subject-token heuristic cannot see producers nested in
// :is(...). They are one repeated selector family and live cascade peers of the
// M4 Fit move: splitting the family across layout.css and the owner CSS reverses
// its source order and clips the paired Fit controls at desktop widths.
const CASCADE_CORRECTIONS = idSet("CSS-0211 CSS-0360 CSS-0553 CSS-0554");

const ROUTES = {
  shell: idSet(`
    CSS-0007 CSS-0008 CSS-0009 CSS-0010 CSS-0011 CSS-0012 CSS-0013 CSS-0014
    CSS-0015 CSS-0016 CSS-0017 CSS-0018 CSS-0019 CSS-0125 CSS-0962 CSS-1146
  `),
  tokens: idSet("CSS-0716"),
  primitives: idSet(`
    CSS-0159 CSS-0717 CSS-0718 CSS-0719 CSS-0720 CSS-0731 CSS-0732 CSS-0733
    CSS-0734 CSS-0735 CSS-0736 CSS-0737 CSS-0773 CSS-0774 CSS-0775 CSS-0776
    CSS-0777 CSS-0801 CSS-0802 CSS-0803 CSS-0804 CSS-0805 CSS-0806 CSS-0807
    CSS-0808 CSS-0814 CSS-0819 CSS-0820 CSS-0821
  `),
  materials: idSet(`
    CSS-0024 CSS-0030 CSS-0031 CSS-0032 CSS-0070 CSS-0096 CSS-0099 CSS-0726
    CSS-0753 CSS-1156 CSS-1161
  `),
  administration: idSet("CSS-0175 CSS-0722 CSS-0723 CSS-0724 CSS-0725 CSS-0945 CSS-1000 CSS-1003"),
  scalar: idSet("CSS-0591 CSS-0660 CSS-0678 CSS-0679 CSS-0685"),
  governed: idSet("CSS-0968"),
  calibration: idSet("CSS-0982"),
  viscoelastic: idSet("CSS-1380 CSS-1383"),
  plot: idSet(`
    CSS-0187 CSS-0188 CSS-0267 CSS-0268 CSS-0269 CSS-0270 CSS-0271
    CSS-0533 CSS-0534 CSS-0535 CSS-0536 CSS-0537 CSS-1063
  `),
  process: idSet("CSS-0189"),
  data: idSet("CSS-0229 CSS-0476 CSS-0485 CSS-0486 CSS-0487 CSS-0521 CSS-0523"),
  export: idSet("CSS-0870 CSS-0891 CSS-0919 CSS-1356 CSS-1357 CSS-1358"),
  core: idSet(`
    CSS-0135 CSS-0231 CSS-0294 CSS-0298 CSS-0299 CSS-0300 CSS-0301
    CSS-0427 CSS-0428 CSS-0429 CSS-0522 CSS-0524
  `),
};

const OWNER_PATHS = {
  shell: "apps/web/src/design/shell.css",
  tokens: "apps/web/src/design/tokens.css",
  primitives: "apps/web/src/design/primitives.css",
  materials: "apps/web/src/features/materials/ui/materials.css",
  administration: "apps/web/src/features/administration/ui/administration.css",
  scalar: "apps/web/src/features/modeling/ui/modeling-scalar-distribution.css",
  governed: "apps/web/src/features/test-data/ui/governed-import-route.css",
  calibration: "apps/web/src/features/modeling/ui/modeling-calibration-workbenches.css",
  viscoelastic: "apps/web/src/features/modeling/ui/modeling-viscoelastic-workbenches.css",
  plot: "apps/web/src/features/modeling/ui/modeling-engineering-curve-plot.css",
  process: "apps/web/src/features/modeling/ui/stages/process/modeling-process-stage.css",
  data: "apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
  export: "apps/web/src/features/modeling/ui/stages/export/modeling-export-stage.css",
  fit: "apps/web/src/features/modeling/ui/stages/fit/modeling-fit-stage.css",
  core: "apps/web/src/features/modeling/ui/modeling-core-workbench.css",
};

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function gitShow(path) {
  return execFileSync("git", ["show", `${BASE_SHA}:${path}`], {
    cwd: ROOT,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
    stdio: ["ignore", "pipe", "ignore"],
  });
}

function tuple(row) {
  return [
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
  ];
}

function sourceGroupCount(rows) {
  return new Set(rows.map((row) => `${row.source.path}#${row.source.ruleIndex}`)).size;
}

function routeName(row) {
  for (const [name, ids] of Object.entries(ROUTES)) {
    if (ids.has(row.id)) return name;
  }
  if (row.owner.category === "materials-specific") return "materials";
  const selector = row.selector.toLowerCase();
  if (row.owner.category === "shared-application-shell") {
    if (selector.includes("stage-export") || selector.includes("export-workspace") || selector.includes("#modeling-output")) return "export";
    if (selector.includes("stage-process") || selector.includes("process-band") || selector.includes("process-stage")) return "process";
    if (selector.includes("fit") || selector.includes("candidate") || selector.includes("ghosh") || selector.includes("approved-fit")) return "fit";
    if (selector.includes("persistent-modeling-plot")) return "plot";
    return "core";
  }
  if (row.owner.category === "shared-pane-split-layout") return "core";
  if (row.owner.category === "shared-token-density-typography") return "materials";
  throw new Error(`${row.id}: no truthful M4 owner route for ${row.selector}`);
}

const inventory = makeInventory();
if (inventory.sourceSha !== BASE_SHA || inventory.mergeBaseSha !== BASE_SHA) {
  throw new Error(`M4 must be frozen at ${BASE_SHA}; got ${inventory.sourceSha}/${inventory.mergeBaseSha}`);
}
const candidates = inventory.selectors.filter((row) => row.owner.migrationBatch === "M4-shared-cleanup");
const candidateTuples = candidates.map(tuple);
const correctionRows = inventory.selectors.filter((row) => CASCADE_CORRECTIONS.has(row.id));
const targetRows = [...candidates, ...correctionRows];
const candidateDigest = sha256(JSON.stringify(candidateTuples));
const categoryCounts = Object.fromEntries(
  Object.entries(Object.groupBy(candidates, (row) => row.owner.category))
    .map(([category, rows]) => [category, rows.length]),
);
if (candidates.length !== 314 || sourceGroupCount(candidates) !== 262) {
  throw new Error(`M4 candidate boundary changed: ${candidates.length} rows / ${sourceGroupCount(candidates)} groups`);
}
if (candidateDigest !== EXPECTED_CANDIDATE_DIGEST) {
  throw new Error(`M4 candidate tuple digest changed: ${candidateDigest}`);
}
const expectedCategoryCounts = {
  "shared-pane-split-layout": 20,
  "shared-application-shell": 180,
  "shared-form-table-plot-primitive": 97,
  "materials-specific": 13,
  "shared-token-density-typography": 4,
};
if (Object.entries(expectedCategoryCounts).some(([category, count]) => categoryCounts[category] !== count)
    || Object.keys(categoryCounts).length !== Object.keys(expectedCategoryCounts).length) {
  throw new Error(`M4 category counts changed: ${JSON.stringify(categoryCounts)}`);
}

const acceptedInPlaceRows = candidates.filter((row) => ACCEPTED_IN_PLACE.has(row.id));
const holdRows = candidates.filter((row) => HOLD.has(row.id));
const approvedCandidateRows = candidates.filter((row) => !ACCEPTED_IN_PLACE.has(row.id) && !HOLD.has(row.id));
if (correctionRows.length !== 4 || sourceGroupCount(correctionRows) !== 4) {
  throw new Error(`M4 Fit cascade correction changed: ${correctionRows.length} rows / ${sourceGroupCount(correctionRows)} groups`);
}
const approvedRows = [...approvedCandidateRows, ...correctionRows];
if (acceptedInPlaceRows.length !== 11 || holdRows.length !== 19 || approvedCandidateRows.length !== 284 || approvedRows.length !== 288) {
  throw new Error(`M4 partition changed: ${acceptedInPlaceRows.length} in-place / ${holdRows.length} HOLD / ${approvedRows.length} move`);
}

const routedRows = Object.groupBy(approvedRows, routeName);
const expectedRouteCounts = {
  shell: 16,
  tokens: 1,
  primitives: 29,
  materials: 24,
  administration: 8,
  scalar: 5,
  governed: 1,
  calibration: 1,
  viscoelastic: 2,
  plot: 19,
  process: 19,
  data: 7,
  export: 13,
  fit: 114,
  core: 29,
};
for (const [name, expected] of Object.entries(expectedRouteCounts)) {
  if (routedRows[name]?.length !== expected) {
    throw new Error(`${name}: expected ${expected} rows, got ${routedRows[name]?.length ?? 0}`);
  }
}
const routedIds = Object.values(routedRows).flatMap((rows) => rows.map((row) => row.id));
if (new Set(routedIds).size !== approvedRows.length) throw new Error("M4 routing is not a one-to-one partition");

const legacyPaths = [...new Set(targetRows.map((row) => row.source.path))].sort();
const fixture = {
  schemaVersion: 1,
  unit: "M4-shared-css-ownership-consolidation",
  baseSha: BASE_SHA,
  generatedFromCleanBase: true,
  exactResult: true,
  targetInsertion: "prepend",
  candidate: {
    rows: candidates.length,
    groups: sourceGroupCount(candidates),
    tupleSha256: candidateDigest,
    categoryCounts,
  },
  approvedMove: {
    rows: approvedRows.length,
    groups: sourceGroupCount(approvedRows),
    tupleSha256: sha256(JSON.stringify(approvedRows.map(tuple))),
  },
  cascadeCorrections: {
    rows: correctionRows.length,
    groups: sourceGroupCount(correctionRows),
    ids: correctionRows.map((row) => row.id),
    tupleSha256: sha256(JSON.stringify(correctionRows.map(tuple))),
    reason: "Preserve the complete repeated Fit selector family and its live cascade after owner extraction; :is(...) hid the real producers from the zero-consumer heuristic.",
  },
  acceptedInPlace: {
    rows: acceptedInPlaceRows.length,
    groups: sourceGroupCount(acceptedInPlaceRows),
    ids: acceptedInPlaceRows.map((row) => row.id),
    tupleSha256: sha256(JSON.stringify(acceptedInPlaceRows.map(tuple))),
    reason: "The selector groups are already truthfully owned by the shared design/layout.css pane, splitter, or resize layer.",
  },
  hold: {
    rows: holdRows.length,
    groups: sourceGroupCount(holdRows),
    ids: holdRows.map((row) => row.id),
    tupleSha256: sha256(JSON.stringify(holdRows.map(tuple))),
    reasons: {
      mixedSourceGroup: [...HOLD_MIXED_SOURCE_GROUP],
      mixedSelectorFamily: [...HOLD_MIXED_SELECTOR_FAMILY],
      globalTypeCascade: [...HOLD_GLOBAL_TYPE_CASCADE],
    },
  },
  approvedIds: approvedRows.map((row) => row.id),
  targetTuples: targetRows.map(tuple),
  legacySources: legacyPaths.map((path) => ({ path, sha256: sha256(gitShow(path)) })),
  owners: Object.fromEntries(Object.entries(expectedRouteCounts).map(([name]) => [name, {
    path: OWNER_PATHS[name],
    ids: (routedRows[name] ?? []).map((row) => row.id),
  }])),
  importAddition: {
    importer: "apps/web/src/scalar-distribution-workbench.tsx",
    value: "./features/modeling/ui/modeling-scalar-distribution.css",
  },
  frontendGuardDelta: {
    removedCount: 2170,
    addedCount: 2028,
    removedSha256: "459f270aa9b1e762de84884b21db6262bd680b4b5580f92171e9e6eaf4ce3a8a",
    addedSha256: "98d9a10589dbfc920f725c42f9d2fd684a87a6c23b3e75b9b6723ef49b621586",
  },
};

console.log(JSON.stringify({
  fixture: FIXTURE_PATH,
  candidate: fixture.candidate,
  approvedMove: fixture.approvedMove,
  acceptedInPlace: { rows: fixture.acceptedInPlace.rows, groups: fixture.acceptedInPlace.groups },
  hold: { rows: fixture.hold.rows, groups: fixture.hold.groups },
  destinations: Object.fromEntries(Object.entries(fixture.owners).map(([name, owner]) => [name, owner.ids.length])),
}, null, 2));

if (process.argv.includes("--write-fixture")) {
  writeFileSync(resolve(ROOT, FIXTURE_PATH), `${JSON.stringify(fixture, null, 2)}\n`, "utf8");
  console.log(`WROTE ${FIXTURE_PATH}`);
}

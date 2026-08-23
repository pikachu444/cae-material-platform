import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const BASE_SHA = "599278067ab5f69d46ea59559344499399b51fed";
const INVENTORY_PATH = "docs/17-evidence/issue-261-css-selector-inventory.json";
const FIXTURE_PATH = "scripts/fixtures/issue-261-residual-owner-boundary.json";
const LEGACY_SOURCES = ["apps/web/src/styles.css", "apps/web/src/design/layout.css"];
const ACCEPTED = "ACCEPTED-shared-layout-in-place";
const M6 = "M6-zero-consumer-removal-candidate";

// Main's cold-route audit found these selectors have no current production DOM
// topology.  They stay byte-for-byte in their legacy source and join the M6
// handoff; FE-06 does not delete them or invent a feature owner.
const AUDITED_ZERO_CONSUMER_IDS = new Set([
  "CSS-0058", "CSS-0155", "CSS-0189", "CSS-0190", "CSS-0216", "CSS-0217",
  "CSS-0281", "CSS-0499", "CSS-0503", "CSS-0536", "CSS-0670", "CSS-0753",
  "CSS-0767", "CSS-0778", "CSS-0779", "CSS-0793", "CSS-0873", "CSS-0892",
  "CSS-0904", "CSS-0908", "CSS-0936", "CSS-0944", "CSS-0961", "CSS-0973",
  "CSS-0989", "CSS-1035", "CSS-1077",
]);

// These shared primitives already sit at the exact eager layout cascade rank.
// Moving them backward into primitives.css would change their order relative
// to the rest of layout.css, so FE-06 accepts their existing shared owner.
const AUDITED_ACCEPTED_IN_PLACE_IDS = new Set([
  "CSS-0067", "CSS-0073", "CSS-0074", "CSS-0075", "CSS-0076", "CSS-0077",
  "CSS-0078", "CSS-0079", "CSS-0080", "CSS-0081", "CSS-0212",
]);

// A grouped CSS rule is a cascade peer set.  These source groups intentionally
// stay together even when the inventory's subject-token heuristic reports more
// than one feature; the first semantic owner is the component that renders the
// whole grouped declaration family.
const GROUP_OWNER_OVERRIDES = {};

const OWNER = {
  primitives: "apps/web/src/design/primitives.css",
  typography: "apps/web/src/design/typography.css",
  shell: "apps/web/src/design/shell.css",
  materials: "apps/web/src/features/materials/ui/materials.css",
  curveContract: "apps/web/src/features/materials/ui/curve-contract-chart.css",
  administration: "apps/web/src/features/administration/ui/administration.css",
  database: "apps/web/src/features/administration/database-design/database-design.css",
  activity: "apps/web/src/features/activity/ui/activity.css",
  modelingCore: "apps/web/src/features/modeling/ui/modeling-core-workbench.css",
  modelingData: "apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css",
  modelingProcess: "apps/web/src/features/modeling/ui/stages/process/modeling-process-stage.css",
  modelingFit: "apps/web/src/features/modeling/ui/stages/fit/modeling-fit-stage.css",
  modelingCalibration: "apps/web/src/features/modeling/ui/modeling-calibration-workbenches.css",
  modelingViscoelastic: "apps/web/src/features/modeling/ui/modeling-viscoelastic-workbenches.css",
  modelingPlot: "apps/web/src/features/modeling/ui/modeling-engineering-curve-plot.css",
  modelingScalar: "apps/web/src/features/modeling/ui/modeling-scalar-distribution.css",
  modelingExport: "apps/web/src/features/modeling/ui/stages/export/modeling-export-stage.css",
  modelingDelivery: "apps/web/src/features/modeling/ui/modeling-export-delivery-workbenches.css",
  modelingNormalization: "apps/web/src/features/modeling/ui/modeling-stage-normalization.css",
  modelingValidation: "apps/web/src/features/modeling/ui/modeling-validation-stage.css",
  governedImport: "apps/web/src/features/test-data/ui/governed-import-route.css",
  canonicalTestData: "apps/web/src/features/test-data/ui/canonical-test-data-workbench.css",
  domainWorkflow: "apps/web/src/domain-workflow-links.css",
};

function audited(ids, owner) {
  return ids.trim().split(/\s+/).filter(Boolean).map((id) => [`CSS-${id}`, owner]);
}

// Exact selector-to-owner decisions from the Main cold-load/import-graph audit.
// These outrank the inventory's broad subject-token producer evidence.
const AUDITED_OWNER_BY_ID = new Map([
  ...audited("0003 0004 0041 0049 0069 0072 0116 0117 0118 0120", OWNER.materials),
  ...audited("0067 0073 0074 0075 0076 0077 0078 0079 0080 0081 0212 0494 0523 0526 0527 0529 0534 0540 0550 0555 0556 0557 0604 0605 0606 0609 0610 0611 0612 0613 0629 0633 0634 0655 0656 0657 0674 1073", OWNER.primitives),
  ...audited("0082 0083 0553", OWNER.activity),
  ...audited("0095 0096 0139 0146 0248 0325 0326 0339 0771 0860", OWNER.modelingProcess),
  ...audited("0106", OWNER.modelingValidation),
  ...audited("0125 0126 0722 0723", OWNER.administration),
  ...audited("0149 0157 0158 0160 0186 0263", OWNER.modelingFit),
  ...audited("0153 0154 0255 0256 0257 0258 0259 0331 0332 0333 0334 0335 0336", OWNER.modelingNormalization),
  ...audited("0169", OWNER.modelingData),
  ...audited("0206 0207 0208 0209 0241 0242 0243 0244 0249 0250 0251 0790", OWNER.modelingPlot),
  ...audited("0396", OWNER.modelingScalar),
  ...audited("0496 0866 0867 0868", OWNER.shell),
  ...audited("0511 0523 0534 0537", OWNER.typography),
  ...audited("0598 0599 0600 0601 0705 1099", OWNER.modelingCalibration),
  ...audited("0614 0637 0638 0641 0642 0643 0644 0645 0646 0650", OWNER.modelingExport),
  ...audited("0658 0710 0711 0712 0713 0714 0715 0716 0717 0718 0719 0720 0721 1070 1071 1072", OWNER.modelingDelivery),
  ...audited("0671", OWNER.canonicalTestData),
  ...audited("0707 1086 1087 1088 1089 1090 1091 1092 1093 1094 1095 1096 1103", OWNER.modelingViscoelastic),
  ...audited("1053 1054 1055 1056 1057 1058 1059 1060 1061 1062 1063", OWNER.domainWorkflow),
]);

// Kept separate from the map above so the declaration can document all peer
// decisions next to the owner paths without relying on selector copying.
Object.assign(GROUP_OWNER_OVERRIDES, {
  "apps/web/src/design/layout.css#62": OWNER.materials,
  "apps/web/src/design/layout.css#97": OWNER.modelingProcess,
  "apps/web/src/design/layout.css#114": OWNER.modelingProcess,
  "apps/web/src/design/layout.css#232": OWNER.modelingProcess,
  "apps/web/src/design/layout.css#235": OWNER.modelingProcess,
  "apps/web/src/design/layout.css#241": OWNER.modelingProcess,
  "apps/web/src/design/layout.css#306": OWNER.materials,
  "apps/web/src/design/layout.css#331": OWNER.shell,
  "apps/web/src/styles.css#34": OWNER.primitives,
  "apps/web/src/styles.css#56": OWNER.materials,
  "apps/web/src/styles.css#68": OWNER.materials,
  "apps/web/src/styles.css#115": OWNER.primitives,
  "apps/web/src/styles.css#168": OWNER.modelingExport,
  "apps/web/src/styles.css#189": OWNER.primitives,
  "apps/web/src/styles.css#572": OWNER.materials,
  "apps/web/src/styles.css#583": OWNER.modelingExport,
});

function lower(row) { return row.selector.toLowerCase(); }
function producerNames(row) {
  return [...new Set([
    ...row.consumers.productionProducerFiles,
    ...row.consumers.productionReferenceFiles,
  ])].map((path) => path.split("/").at(-1).toLowerCase());
}
function has(value, pattern) { return pattern.test(value); }

/**
 * Resolve a legacy row to an existing owner stylesheet.  This table is
 * intentionally semantic: a row's selector family and its observed producer
 * route determine the owner, never a copied selector or a global fallback.
 */
function ownerPathForRow(row) {
  const auditedOwner = AUDITED_OWNER_BY_ID.get(row.id);
  if (auditedOwner) return auditedOwner;
  const value = lower(row);
  const producerList = producerNames(row);
  const producers = producerList.join(" ");
  const category = row.owner.category;

  if (category === "shared-application-shell") return OWNER.shell;
  if (category === "shared-form-table-plot-primitive") {
    if (/^h[1-4]$|^p$|^dt$|^dd$/.test(value)) return OWNER.typography;
    return OWNER.primitives;
  }
  if (category === "shared-pane-split-layout") return "apps/web/src/design/layout.css";

  // The inventory's generic subject token (for example `.active`) can make a
  // producer list look cross-feature.  The component selector prefix is the
  // stronger ownership signal for these navigator and stage families.
  if (has(value, /administration-navigation|schema-|database-|folder-admin|record-(?:result|view|revision)|facet-row|connection-dot/)) return OWNER.administration;
  if (has(value, /materials-explorer|materials-navigator|materials-result|materials-tree|tree-subset|material-context|material-class-chip|material-list|workflow-node/)) return OWNER.materials;
  if (has(value, /fit-candidate|curve-tree|configured-step|stage-chip|workspace-inspector|option-choice|stage-item|modeling-stage-shell/)) return OWNER.modelingCore;
  if (has(value, /layout-projection|evidence-overview/)) return OWNER.modelingCore;
  if (has(value, /^(?:\.?(?:warning|error|success|approved|blocked|ready|complete|online|primary|selected|current)|.*\.(?:warning|error|success|approved|blocked|ready|complete))\b/)) return OWNER.primitives;

  // A specific component/feature family always outranks a generic status
  // token observed by several routes.
  if (has(value, /distribution|scalar-distribution/)) return OWNER.modelingScalar;
  if (has(value, /contract-curve/)) return OWNER.curveContract;
  if (has(value, /governed-import/)) return OWNER.governedImport;
  if (has(value, /test-json|tabular-adapter|saved-test-documents|channel-preview|json-source|file-picker|json-editor|import-controls|document-(?:list|row)/)
      || producers.includes("canonical-test-data-workbench")) return OWNER.canonicalTestData;
  if (has(value, /polymer|viscoelastic|prony|master-curve|scientific-profile|shear-relaxation/)
      || producers.includes("reference-linear-viscoelastic-workbench")
      || producers.includes("reference-ogden-prony-workbench")
      || producers.includes("polymer-temperature-shift-inspector")) return OWNER.modelingViscoelastic;
  if (has(value, /validation|replicate-statistics|reference-validation|tensile|calibration|ogden|voce|neo-hookean/)
      || producers.includes("reference-validation-workbench")
      || producers.includes("reference-replicate-statistics-workbench")) return OWNER.modelingCalibration;
  if (has(value, /reference-elastoplastic|elastoplastic|neutral-solver|solver-card|target-preview|export|delivery|mapping-status|mapping-note|workflow-step|domain-workflow/)
      || producers.includes("modeling-target-preview")
      || producers.includes("solver-card-delivery-ui")) return OWNER.modelingExport;
  if (has(value, /bulk-export|bundle-row|bundle-list|compact-field|classification-badge|export-control/)
      || producers.includes("bulk-export-center")) return OWNER.modelingDelivery;
  if (has(value, /processing-workbench|processing-|method-|guided-|extrapolation|hardening|plot-view-switch|rail-statistics|modeling-plot-toolbar|chart-axis|chart-tick|curve-line|persistent-modeling-plot/)
      || producers.includes("common-processing-workbench")
      || producers.includes("engineering-curve-plot")) {
    if (has(value, /chart-axis|chart-tick|plot-toolbar|hardening-analysis|curve-line|curve-plot|plot-view-switch/)) return OWNER.modelingPlot;
    if (has(value, /processing|method|guided|extrapolation|hardening|persistent-modeling-plot|rail-statistics/)) return OWNER.modelingProcess;
    return OWNER.modelingCore;
  }
  if (has(value, /data-|data\b|intake|channel/)) return OWNER.modelingData;
  if (has(value, /(?:^|[.\s>+~])activity(?:[-_.]|\b)|release-|review-request|reviewed-|operation-|job-|approval|governance/)
      || producerList.some((name) => /activity|review-request|release-workbench|governance-evidence|operations-dashboard/.test(name))) return OWNER.activity;
  if (has(value, /administration|admin-|catalog|schema-|database-|record-|folder-|permission|access-/)
      || producerList.some((name) => /administration|catalog|schema-definition|configurable-catalog/.test(name))) return OWNER.administration;
  if (has(value, /(?:^|[.\s>+~])materials?(?:[-_.]|\b)|material-(?!modeling)|datasheet|browse-|card-preview|module-material|exact-domain|materials-scroll|selection-delivery/)
      || producerList.some((name) => /material-library|materials-browse|material-datasheet|exact-domain|domain-workflow/.test(name))) return OWNER.materials;

  // Type selectors and app-wide semantic primitives belong to the shared
  // design layer.  This is the only permitted fallback for a non-feature row.
  if (/^(?:\*|html|body|button|input|select|textarea|table|thead|tbody|tr|th|td|label|form|main|details|summary|h[1-4]|p|dt|dd)$/.test(value)) {
    return /^(?:h[1-4]|p|dt|dd)$/.test(value) ? OWNER.typography : OWNER.primitives;
  }
  if (category === "activity-specific") return OWNER.activity;
  if (category === "administration-specific") return OWNER.administration;
  if (category === "materials-specific") return OWNER.materials;
  if (category === "modeling-specific") return OWNER.modelingCore;

  // Component evidence is still preferable to retaining a global selector.
  if (producerList.some((name) => /reference|validation/.test(name))) return OWNER.modelingCalibration;
  if (producerList.some((name) => /processing|modeling|fit|curve/.test(name))) return OWNER.modelingCore;
  if (producerList.some((name) => /material|catalog|domain/.test(name))) return OWNER.materials;
  return OWNER.primitives;
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
    row.targetKey,
    row.owner.category,
    row.declarations.signatureSha256,
  ];
}

function digest(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function sourceHash(path) {
  return createHash("sha256").update(readFileSync(resolve(ROOT, path))).digest("hex");
}

function frozenText(path) {
  return execFileSync("git", ["show", `${BASE_SHA}:${path}`], {
    cwd: ROOT,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
  });
}

function frozenHash(path) {
  return createHash("sha256").update(frozenText(path)).digest("hex");
}

function gitSha() {
  return execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
}

function freeze() {
  if (gitSha() !== BASE_SHA) throw new Error(`freeze must run at ${BASE_SHA}; got ${gitSha()}`);
  const live = JSON.parse(frozenText(INVENTORY_PATH));
  // The committed inventory intentionally retains the SHA of the unit that
  // generated it.  The authoritative freeze boundary is the Git blob at
  // BASE_SHA, not those historical provenance fields.
  const accepted = live.selectors.filter((row) => row.owner.migrationBatch === ACCEPTED || AUDITED_ACCEPTED_IN_PLACE_IDS.has(row.id));
  const targetRows = live.selectors.filter((row) => ![ACCEPTED, M6].includes(row.owner.migrationBatch) && !AUDITED_ZERO_CONSUMER_IDS.has(row.id) && !AUDITED_ACCEPTED_IN_PLACE_IDS.has(row.id));
  const originalM6Rows = live.selectors.filter((row) => row.owner.migrationBatch === M6);
  const m6Rows = live.selectors.filter((row) => row.owner.migrationBatch === M6 || AUDITED_ZERO_CONSUMER_IDS.has(row.id));
  if (targetRows.length + m6Rows.length + accepted.length !== 1103) {
    throw new Error(`unexpected residual partition ${targetRows.length}/${m6Rows.length}`);
  }
  const ownerById = new Map(targetRows.map((row) => [row.id, ownerPathForRow(row)]));
  const sourceGroups = new Map();
  for (const row of targetRows) {
    const key = `${row.source.path}#${row.source.ruleIndex}`;
    if (!sourceGroups.has(key)) sourceGroups.set(key, []);
    sourceGroups.get(key).push(row);
  }
  for (const [key, rows] of sourceGroups) {
    const override = GROUP_OWNER_OVERRIDES[key];
    if (override) for (const row of rows) {
      if (!AUDITED_OWNER_BY_ID.has(row.id)) ownerById.set(row.id, override);
    }
  }
  const owners = {};
  for (const [id, path] of ownerById) {
    if (!owners[path]) owners[path] = { path, ids: [], sourceGroups: [], categoryCounts: {} };
    const row = targetRows.find((item) => item.id === id);
    owners[path].ids.push(id);
    owners[path].categoryCounts[row.owner.category] = (owners[path].categoryCounts[row.owner.category] ?? 0) + 1;
  }
  for (const [key, rows] of sourceGroups) {
    for (const path of new Set(rows.map((row) => ownerById.get(row.id)))) {
      owners[path].sourceGroups.push(key);
    }
  }
  const targetTuples = targetRows.map(tuple);
  const originalM6Tuples = originalM6Rows.map(tuple);
  const m6Tuples = m6Rows.map(tuple);
  const fixture = {
    schemaVersion: "cmp.issue-261-residual-owner-boundary.v1",
    unit: "FE-06 residual owner-boundary consolidation",
    baseSha: BASE_SHA,
    frozenInventory: { path: INVENTORY_PATH, sourceSha: live.sourceSha, sha256: frozenHash(INVENTORY_PATH) },
    legacySources: LEGACY_SOURCES.map((path) => ({ path, sha256: frozenHash(path) })),
    targetRows: { rows: targetRows.length, groups: sourceGroups.size, tupleSha256: digest(targetTuples) },
    targetIds: targetRows.map((row) => row.id),
    targetTuples,
    owners,
    acceptedInPlace: { rows: accepted.length, ids: accepted.map((row) => row.id) },
    auditedZeroConsumerIds: [...AUDITED_ZERO_CONSUMER_IDS],
    auditedAcceptedInPlaceIds: [...AUDITED_ACCEPTED_IN_PLACE_IDS],
    touchedOwnerPaths: [...new Set(Object.values(OWNER))],
    originalM6Handoff: {
      rows: originalM6Rows.length,
      groups: new Set(originalM6Rows.map((row) => `${row.source.path}#${row.source.ruleIndex}`)).size,
      tupleSha256: digest(originalM6Tuples),
      tuples: originalM6Tuples,
    },
    m6Handoff: {
      rows: m6Rows.length,
      groups: new Set(m6Rows.map((row) => `${row.source.path}#${row.source.ruleIndex}`)).size,
      ids: m6Rows.map((row) => row.id),
      tupleSha256: digest(m6Tuples),
      tuples: m6Tuples,
      rule: "No M6 selector is moved or deleted in FE-06; audit/removal is the next bounded unit after live zero-consumer proof.",
    },
    expected: {
      ownerRows: Object.fromEntries(Object.values(owners).map((owner) => [owner.path, owner.ids.length])),
      sourceOrder: targetRows.map((row) => [row.source.path, row.source.ruleIndex, row.source.selectorIndex, row.id]),
    },
  };
  return fixture;
}

const fixture = freeze();
if (process.argv.includes("--write")) {
  writeFileSync(resolve(ROOT, FIXTURE_PATH), `${JSON.stringify(fixture, null, 2)}\n`, "utf8");
  console.log(`WROTE ${FIXTURE_PATH}`);
}
console.log(JSON.stringify({
  targetRows: fixture.targetRows,
  ownerRows: fixture.expected.ownerRows,
  acceptedInPlace: fixture.acceptedInPlace.rows,
  m6Handoff: { rows: fixture.m6Handoff.rows, groups: fixture.m6Handoff.groups, tupleSha256: fixture.m6Handoff.tupleSha256 },
}, null, 2));

export { ownerPathForRow };

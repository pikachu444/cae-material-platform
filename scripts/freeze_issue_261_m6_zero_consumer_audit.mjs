import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

import { makeInventory } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const BASE_SHA = "593dfd3dab3a22ec93bc9d9a078c05b6f1f1c329";
const HANDOFF_PATH = "scripts/fixtures/issue-261-residual-owner-boundary.json";
const RUNTIME_PATHS = [
  "docs/17-evidence/images/issue-261-m6-zero-consumer-audit-and-removal/live/selector-runtime-before.json",
  "docs/17-evidence/images/issue-261-m6-zero-consumer-audit-and-removal/live/selector-runtime-after.json",
];
const OUTPUT_PATH = "scripts/fixtures/issue-261-m6-zero-consumer-audit.json";
const DIST_PATH = "apps/web/dist";

function posix(path) { return path.split(sep).join("/"); }
function normalizeSpace(value) { return value.replace(/\s+/g, " ").trim(); }
function sha256(value) { return createHash("sha256").update(value).digest("hex"); }
function digest(value) { return sha256(JSON.stringify(value)); }
function descriptorParts(path, selector, atContext, signature) {
  return [path, normalizeSpace(selector), (atContext ?? []).join(" | "), signature].join("\0");
}
function rowDescriptor(row) {
  return descriptorParts(
    row.source.path,
    row.selector,
    row.source.atContext,
    row.declarations.signatureSha256,
  );
}
function tupleDescriptor(tuple) {
  return descriptorParts(tuple[1], tuple[5], tuple[6], tuple[10]);
}
function currentTuple(row) {
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
function collectFiles(directory) {
  const files = [];
  for (const name of readdirSync(directory)) {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) files.push(...collectFiles(path));
    else files.push(path);
  }
  return files;
}
function escapeRegex(value) { return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
function tokenPattern(token) {
  return new RegExp(`(^|[^A-Za-z0-9_-])${escapeRegex(token)}(?=$|[^A-Za-z0-9_-])`, "g");
}
function countToken(source, token) {
  return [...source.matchAll(tokenPattern(token))].length;
}

const head = execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
if (head !== BASE_SHA) throw new Error(`M6 freeze requires ${BASE_SHA}, got ${head}`);

const handoffFixture = JSON.parse(readFileSync(resolve(ROOT, HANDOFF_PATH), "utf8"));
const handoff = handoffFixture.m6Handoff;
if (handoff.rows !== 556 || handoff.groups !== 495 || digest(handoff.tuples) !== handoff.tupleSha256) {
  throw new Error("the PR #318 M6 handoff oracle drifted");
}

const inventory = makeInventory();
const m6Rows = inventory.selectors.filter(
  (row) => row.owner.migrationBatch === "M6-zero-consumer-removal-candidate",
);
if (inventory.summary.selectorRows !== 578 || inventory.summary.cssRuleGroups !== 517 || m6Rows.length !== 556) {
  throw new Error(`unexpected M6 base inventory: ${JSON.stringify(inventory.summary)}`);
}

const tupleQueues = new Map();
for (const tuple of handoff.tuples) {
  const key = tupleDescriptor(tuple);
  if (!tupleQueues.has(key)) tupleQueues.set(key, []);
  tupleQueues.get(key).push(tuple);
}
for (const queue of tupleQueues.values()) queue.sort((left, right) => left[3] - right[3] || left[4] - right[4]);

const runtimeAudits = RUNTIME_PATHS.map((path) => ({
  path,
  audit: JSON.parse(readFileSync(resolve(ROOT, path), "utf8")),
}));
for (const { path, audit } of runtimeAudits) {
  if (audit.handoff.tupleSha256 !== handoff.tupleSha256
      || audit.coverage.topologies.length !== 13
      || audit.coverage.snapshots < 13
      || audit.summary.selectorsWithQueryErrors !== 0) {
    throw new Error(`incomplete M6 runtime proof ${path}: ${JSON.stringify(audit.summary)}`);
  }
}
const runtimeBySelector = new Map();
for (const { audit } of runtimeAudits) {
  for (const entry of audit.selectors) {
    if (!runtimeBySelector.has(entry.selector)) {
      runtimeBySelector.set(entry.selector, {
        selector: entry.selector,
        matchingSnapshots: [],
        queryErrors: [],
      });
    }
    const target = runtimeBySelector.get(entry.selector);
    const seenSnapshots = new Set(target.matchingSnapshots.map((snapshot) => JSON.stringify(snapshot)));
    for (const snapshot of entry.matchingSnapshots) {
      const key = JSON.stringify(snapshot);
      if (!seenSnapshots.has(key)) {
        target.matchingSnapshots.push(snapshot);
        seenSnapshots.add(key);
      }
    }
    const seenErrors = new Set(target.queryErrors.map((error) => JSON.stringify(error)));
    for (const error of entry.queryErrors) {
      const key = JSON.stringify(error);
      if (!seenErrors.has(key)) {
        target.queryErrors.push(error);
        seenErrors.add(key);
      }
    }
  }
}
const runtimeSelectors = [...runtimeBySelector.values()];
const runtime = {
  method: "Union of exact document.querySelectorAll observations from the frozen before audit and final five-viewport after audit.",
  coverage: {
    topologies: runtimeAudits.at(-1).audit.coverage.topologies,
    viewports: runtimeAudits.at(-1).audit.coverage.viewports,
    snapshots: runtimeAudits.at(-1).audit.coverage.snapshots,
    selectorRows: handoff.rows,
    uniqueSelectors: runtimeBySelector.size,
  },
  summary: {
    selectorsWithMatches: runtimeSelectors.filter((entry) => entry.matchingSnapshots.length).length,
    selectorsWithQueryErrors: runtimeSelectors.filter((entry) => entry.queryErrors.length).length,
    zeroMatchSelectors: runtimeSelectors.filter((entry) => !entry.matchingSnapshots.length && !entry.queryErrors.length).length,
  },
};

const bundleFiles = collectFiles(resolve(ROOT, DIST_PATH))
  .filter((path) => [".js", ".html"].includes(extname(path)))
  .sort();
if (!bundleFiles.length) throw new Error("production bundle is missing; run npm run build first");
const bundleSources = bundleFiles.map((absolute) => ({
  absolute,
  path: posix(relative(ROOT, absolute)),
  source: readFileSync(absolute, "utf8"),
}));
const bundleEvidenceByToken = new Map();
function bundleEvidence(token) {
  if (!bundleEvidenceByToken.has(token)) {
    bundleEvidenceByToken.set(token, bundleSources.flatMap((file) => {
      const occurrences = countToken(file.source, token);
      return occurrences ? [{ path: file.path, occurrences }] : [];
    }));
  }
  return bundleEvidenceByToken.get(token);
}

const auditRows = [];
for (const row of m6Rows) {
  const queue = tupleQueues.get(rowDescriptor(row));
  const sourceTuple = queue?.shift();
  if (!sourceTuple) throw new Error(`cannot map current M6 row to handoff: ${row.id} ${row.selector}`);
  const staticFiles = [...new Set([
    ...row.consumers.productionProducerFiles,
    ...row.consumers.productionReferenceFiles,
    ...row.consumers.testProducerFiles,
    ...row.consumers.testReferenceFiles,
  ])].sort();
  const runtimeEntry = runtimeBySelector.get(row.selector);
  if (!runtimeEntry) throw new Error(`runtime proof is missing ${row.selector}`);
  const subjectToken = row.consumers.subjectToken;
  const bundle = subjectToken ? bundleEvidence(subjectToken) : [];
  const proof = {
    staticZero: Boolean(subjectToken) && staticFiles.length === 0,
    bundleZero: Boolean(subjectToken) && bundle.length === 0,
    runtimeZero: runtimeEntry.matchingSnapshots.length === 0 && runtimeEntry.queryErrors.length === 0,
  };
  const disposition = proof.staticZero && proof.bundleZero && proof.runtimeZero ? "REMOVE" : "HOLD";
  const reasonCodes = [];
  if (!proof.staticZero) reasonCodes.push("STATIC_SUBJECT_EVIDENCE_OR_NO_SUBJECT");
  if (!proof.bundleZero) reasonCodes.push("PRODUCTION_BUNDLE_SUBJECT_EVIDENCE_OR_NO_SUBJECT");
  if (!proof.runtimeZero) reasonCodes.push("LIVE_EXACT_SELECTOR_MATCH_OR_QUERY_ERROR");
  auditRows.push({
    handoffId: sourceTuple[0],
    currentId: row.id,
    source: row.source,
    selector: row.selector,
    specificity: row.specificity,
    targetKey: row.targetKey,
    declarationSignature: row.declarations.signatureSha256,
    disposition,
    proof,
    staticEvidence: {
      status: row.consumers.status,
      subjectToken,
      productionProducerFiles: row.consumers.productionProducerFiles,
      productionReferenceFiles: row.consumers.productionReferenceFiles,
      testProducerFiles: row.consumers.testProducerFiles,
      testReferenceFiles: row.consumers.testReferenceFiles,
    },
    bundleEvidence: bundle,
    runtimeEvidence: {
      matchingSnapshots: runtimeEntry.matchingSnapshots,
      queryErrors: runtimeEntry.queryErrors,
    },
    hold: disposition === "HOLD" ? {
      reasonCodes,
      currentOwner: row.source.path,
      candidateOwner: row.owner.proposedTarget,
      removalCondition: (
        "Resolve every recorded static/bundle/live signal to zero, identify or retire its exact producer "
        + "topology, then repeat the production build and the 13-topology live selector audit before removal."
      ),
    } : null,
  });
}
const unmatched = [...tupleQueues.entries()].flatMap(([key, queue]) => queue.map((tuple) => `${tuple[0]}:${key}`));
if (unmatched.length) throw new Error(`unmatched handoff rows: ${unmatched.join(", ")}`);

const removeRows = auditRows.filter((row) => row.disposition === "REMOVE");
const holdRows = auditRows.filter((row) => row.disposition === "HOLD");
const allByGroup = new Map();
for (const row of inventory.selectors) {
  const key = `${row.source.path}#${row.source.ruleIndex}`;
  if (!allByGroup.has(key)) allByGroup.set(key, []);
  allByGroup.get(key).push(row);
}
const removeKeys = new Set(removeRows.map((row) => `${row.source.path}#${row.source.ruleIndex}#${row.source.selectorIndex}`));
const touchedGroups = [...new Set(removeRows.map((row) => `${row.source.path}#${row.source.ruleIndex}`))];
const fullyRemovedGroups = touchedGroups.filter((key) => allByGroup.get(key).every(
  (row) => removeKeys.has(`${row.source.path}#${row.source.ruleIndex}#${row.source.selectorIndex}`),
));
const partiallyShrunkGroups = touchedGroups.filter((key) => !fullyRemovedGroups.includes(key));
const holdGroups = new Set(holdRows.map((row) => `${row.source.path}#${row.source.ruleIndex}`));

const legacySources = handoffFixture.legacySources.map(({ path }) => {
  const source = execFileSync("git", ["show", `${BASE_SHA}:${path}`], { cwd: ROOT });
  const rows = inventory.selectors.filter((row) => row.source.path === path);
  return {
    path,
    bytes: source.length,
    sha256: sha256(source),
    selectorRows: rows.length,
    cssRuleGroups: new Set(rows.map((row) => row.source.ruleIndex)).size,
  };
});
const bundleInventory = bundleSources.map(({ absolute, path }) => {
  const source = readFileSync(absolute);
  return { path, bytes: source.length, sha256: sha256(source) };
});
const fixture = {
  schemaVersion: "cmp.issue-261.m6.zero-consumer-audit.v1",
  unit: "M6-zero-consumer-audit-and-removal",
  baseSha: BASE_SHA,
  handoff: {
    rows: handoff.rows,
    groups: handoff.groups,
    tupleSha256: handoff.tupleSha256,
  },
  method: {
    static: inventory.scope.method,
    bundle: "Exact subject-token search over non-CSS Vite production assets after npm run build.",
    runtime: runtime.method,
    removalRule: "REMOVE only when staticZero && bundleZero && runtimeZero; otherwise preserve in HOLD.",
  },
  legacySources,
  bundleBefore: {
    path: DIST_PATH,
    files: bundleInventory,
    treeSha256: digest(bundleInventory.map((file) => [file.path, file.sha256])),
  },
  runtimeProof: {
    audits: RUNTIME_PATHS.map((path) => ({
      path,
      sha256: sha256(readFileSync(resolve(ROOT, path))),
    })),
    coverage: runtime.coverage,
    summary: runtime.summary,
  },
  auditRows,
  currentTupleSha256: digest(auditRows.map((row) => currentTuple({
    id: row.currentId,
    source: row.source,
    selector: row.selector,
    specificity: row.specificity,
    targetKey: row.targetKey,
    owner: { category: m6Rows.find((item) => item.id === row.currentId).owner.category },
    declarations: { signatureSha256: row.declarationSignature },
  }))),
  remove: {
    rows: removeRows.length,
    touchedGroups: touchedGroups.length,
    fullyRemovedGroups: fullyRemovedGroups.length,
    partiallyShrunkGroups: partiallyShrunkGroups.length,
    handoffIds: removeRows.map((row) => row.handoffId),
  },
  hold: {
    rows: holdRows.length,
    groups: holdGroups.size,
    handoffIds: holdRows.map((row) => row.handoffId),
    rule: "The legacy source remains the truthful owner until every row-specific removal condition is met.",
  },
  expectedAfter: {
    selectorRows: inventory.summary.selectorRows - removeRows.length,
    cssRuleGroups: inventory.summary.cssRuleGroups - fullyRemovedGroups.length,
    acceptedInPlaceRows: handoffFixture.acceptedInPlace.rows,
    holdRows: holdRows.length,
    m6CandidateRows: 0,
  },
};

writeFileSync(resolve(ROOT, OUTPUT_PATH), `${JSON.stringify(fixture, null, 2)}\n`, "utf8");
console.log(JSON.stringify({
  output: OUTPUT_PATH,
  handoff: fixture.handoff,
  remove: fixture.remove,
  hold: { rows: fixture.hold.rows, groups: fixture.hold.groups },
  expectedAfter: fixture.expectedAfter,
}, null, 2));

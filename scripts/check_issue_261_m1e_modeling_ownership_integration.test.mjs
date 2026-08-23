import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const FIXTURE = JSON.parse(readFileSync(
  new URL("./fixtures/issue-261-m1e-modeling-ownership-integration.json", import.meta.url),
  "utf8",
));
const M4_FIXTURE = JSON.parse(readFileSync(
  new URL("./fixtures/issue-261-m4-shared-css-ownership.json", import.meta.url),
  "utf8",
));
const M4_IMPORT_ALLOWANCES = new Map();
for (const { importer, value } of M4_FIXTURE.m1eSideEffectImportAllowances ?? []) {
  if (!M4_IMPORT_ALLOWANCES.has(importer)) M4_IMPORT_ALLOWANCES.set(importer, new Set());
  M4_IMPORT_ALLOWANCES.get(importer).add(`import "${value}";`);
}

const TUPLE = {
  legacyId: 0,
  sourcePath: 1,
  sourceRuleIndex: 2,
  sourceSelectorIndex: 3,
  selector: 4,
  atContext: 5,
  declarationSignature: 6,
};

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function declarationSignature(declarations) {
  return sha256(JSON.stringify(
    declarations.map(({ property, value, important }) => [property, value, important]),
  ));
}

function parsedStylesheet(path, source = readFileSync(resolve(ROOT, path), "utf8")) {
  return parseCss(path, source, null);
}

function baseSource(path) {
  return execFileSync(
    "git",
    ["show", `${FIXTURE.baseSha}:${path}`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 32 * 1024 * 1024 },
  );
}

function currentBaseSource(path) {
  return execFileSync(
    "git",
    ["show", `${FIXTURE.currentBaseSha ?? FIXTURE.baseSha}:${path}`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 32 * 1024 * 1024 },
  );
}

function parsedBaseStylesheet(path) {
  return parsedStylesheet(path, baseSource(path));
}

function parsedIdentity(row) {
  return JSON.stringify([
    row.selector,
    row.atContext ?? [],
    declarationSignature(row.declarations),
  ]);
}

function isCorrectionTarget(row, correction) {
  return row.selector === correction.selector
    && JSON.stringify(row.atContext ?? []) === JSON.stringify(correction.atContext ?? []);
}

function hasCorrectionDeclarations(row, correction) {
  return isCorrectionTarget(row, correction)
    && correction.declarations.every((expected) => row.declarations.some((actual) => (
      actual.property === expected.property
      && actual.value === expected.value
      && actual.important === expected.important
    )));
}

function stripCorrectionDeclarations(row, correction) {
  if (!isCorrectionTarget(row, correction)) return row;
  const properties = new Set(correction.declarations.map(({ property }) => property));
  return {
    ...row,
    declarations: row.declarations.filter(({ property }) => !properties.has(property)),
  };
}

function oracleIdentity(tuple) {
  return JSON.stringify([
    tuple[TUPLE.selector],
    tuple[TUPLE.atContext] ?? [],
    tuple[TUPLE.declarationSignature],
  ]);
}

function oracleSourceKey(tuple) {
  return `${tuple[TUPLE.sourcePath]}\0${tuple[TUPLE.sourceRuleIndex]}`;
}

function groupRows(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const value = key(row);
    if (!groups.has(value)) groups.set(value, []);
    groups.get(value).push(row);
  }
  return groups;
}

function groupIdentity(rows, identity) {
  return JSON.stringify(rows.map(identity));
}

function walkTsx(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return walkTsx(path);
    return entry.isFile() && entry.name.endsWith(".tsx") ? [path] : [];
  });
}

function walkSourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return walkSourceFiles(path);
    return entry.isFile() && /\.(?:ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

function exceptionKey(entry) {
  return `${entry.ruleId}|${entry.path}|${entry.fingerprint}`;
}

function stripDeclaredM4Imports(source, importer) {
  const allowed = M4_IMPORT_ALLOWANCES.get(importer);
  if (!allowed?.size) return source;
  return source
    .split(/\r?\n/)
    .filter((line) => !allowed.has(line.trim()))
    .join("\n");
}

test("M1E integration freezes the reviewed base oracle and current residual source", () => {
  assert.doesNotThrow(() => execFileSync(
    "git",
    ["cat-file", "-e", `${FIXTURE.baseSha}^{commit}`],
    { cwd: ROOT, stdio: "ignore" },
  ));
  assert.equal(
    execFileSync("git", ["merge-base", "HEAD", FIXTURE.baseSha], { cwd: ROOT, encoding: "utf8" }).trim(),
    FIXTURE.baseSha,
  );
  const oracle = FIXTURE.moves.flatMap((move) => move.oracle);
  assert.equal(oracle.length, FIXTURE.aggregate.selectorRows);
  assert.equal(oracle.length, 334);
  assert.equal(
    FIXTURE.moves.reduce(
      (total, move) => total + new Set(move.oracle.map(oracleSourceKey)).size,
      0,
    ),
    FIXTURE.aggregate.ruleGroups,
  );
  assert.deepEqual(
    FIXTURE.moves.map(({ expectedRows, expectedGroups }) => [expectedRows, expectedGroups]),
    [[37, 26], [62, 59], [84, 78], [50, 46], [101, 95]],
  );

  const baseByPath = new Map(FIXTURE.legacySources.map(
    (path) => [path, parsedBaseStylesheet(path)],
  ));
  for (const tuple of FIXTURE.moves.slice(0, 4).flatMap((move) => move.oracle)) {
    const base = baseByPath.get(tuple[TUPLE.sourcePath]).find((row) => (
      row.ruleIndex === tuple[TUPLE.sourceRuleIndex]
      && row.selectorIndex === tuple[TUPLE.sourceSelectorIndex]
    ));
    assert.ok(base, `missing frozen base tuple ${tuple[TUPLE.legacyId]}`);
    assert.equal(parsedIdentity(base), oracleIdentity(tuple), `base tuple drift ${tuple[TUPLE.legacyId]}`);
  }

  const oracleGroups = groupRows(
    FIXTURE.moves.slice(0, 4).flatMap((move) => move.oracle),
    oracleSourceKey,
  );
  for (const [key, tuples] of oracleGroups) {
    const [path, ruleIndex] = key.split("\0");
    const baseGroup = baseByPath.get(path).filter((row) => row.ruleIndex === Number(ruleIndex));
    assert.equal(
      groupIdentity(baseGroup, parsedIdentity),
      groupIdentity(tuples, oracleIdentity),
      `incomplete frozen source group ${key}`,
    );
  }

  const inventory = JSON.parse(readFileSync(resolve(ROOT, FIXTURE.frozenInventory.path), "utf8"));
  const movedIdentities = new Set(FIXTURE.moves.at(-1).oracle.map(oracleIdentity));
  for (const path of FIXTURE.legacySources) {
    const expected = inventory.selectors
      .filter((row) => row.source.path === path && !movedIdentities.has(JSON.stringify([
        row.selector,
        row.source.atContext ?? [],
        row.declarations.signatureSha256,
      ])))
      .map((row) => JSON.stringify([
        row.selector,
        row.source.atContext ?? [],
        row.declarations.signatureSha256,
      ]));
    const current = parsedStylesheet(path).map(parsedIdentity);
    assert.deepEqual(current, expected, `${path}: current residual source drift`);
  }
});

test("M1E owner styles and legacy residual are the exact serial Lane A then Lane B replay", () => {
  const corrections = new Map(FIXTURE.corrections.map((correction) => [
    correction.target,
    correction,
  ]));
  for (const move of FIXTURE.moves) {
    const sourceRank = new Map(move.sourceOrder.map((path, index) => [path, index]));
    const expected = [...move.oracle].sort((left, right) => (
      sourceRank.get(left[TUPLE.sourcePath]) - sourceRank.get(right[TUPLE.sourcePath])
      || left[TUPLE.sourceRuleIndex] - right[TUPLE.sourceRuleIndex]
      || left[TUPLE.sourceSelectorIndex] - right[TUPLE.sourceSelectorIndex]
    ));
    const correction = corrections.get(move.target);
    const expectedIdentities = new Set(move.oracle.map(oracleIdentity));
    const ownerIdentityExceptions = new Set(move.ownerIdentityExceptions ?? []);
    const exceptionSelectors = move.oracle
      .filter((tuple) => ownerIdentityExceptions.has(tuple[TUPLE.legacyId]))
      .map((tuple) => JSON.stringify([tuple[TUPLE.selector], tuple[TUPLE.atContext] ?? []]));
    const exceptionTupleBySelector = new Map(move.oracle
      .filter((tuple) => ownerIdentityExceptions.has(tuple[TUPLE.legacyId]))
      .map((tuple) => [JSON.stringify([tuple[TUPLE.selector], tuple[TUPLE.atContext] ?? []]), tuple]));
    const relocationActual = parsedStylesheet(move.target)
      .filter((row) => expectedIdentities.has(parsedIdentity(row))
        || (correction && hasCorrectionDeclarations(row, correction))
        || exceptionSelectors.includes(JSON.stringify([row.selector, row.atContext ?? []])))
      .map((row) => (correction && hasCorrectionDeclarations(row, correction)
        ? stripCorrectionDeclarations(row, correction)
        : row));
    const replayIdentity = (row) => exceptionTupleBySelector.has(JSON.stringify([row.selector, row.atContext ?? []]))
      ? oracleIdentity(exceptionTupleBySelector.get(JSON.stringify([row.selector, row.atContext ?? []])))
      : parsedIdentity(row);
    assert.equal(relocationActual.length, move.expectedRows, `${move.name}: target row count`);
    assert.equal(new Set(relocationActual.map((row) => row.ruleIndex)).size, move.expectedGroups, `${move.name}: target groups`);
    assert.deepEqual(relocationActual.map(replayIdentity), expected.map(oracleIdentity), `${move.name}: tuple/order drift`);

    const actualGroups = [...groupRows(relocationActual, (row) => row.ruleIndex).values()];
    const expectedGroups = [...groupRows(expected, oracleSourceKey).values()];
    assert.deepEqual(
      actualGroups.map((rows) => groupIdentity(rows, replayIdentity)),
      expectedGroups.map((rows) => groupIdentity(rows, oracleIdentity)),
      `${move.name}: complete-group boundary drift`,
    );
  }

  const inventory = JSON.parse(readFileSync(resolve(ROOT, FIXTURE.frozenInventory.path), "utf8"));
  const movedIdentities = new Set(FIXTURE.moves.at(-1).oracle.map(oracleIdentity));
  for (const path of FIXTURE.legacySources) {
    const expectedResidual = inventory.selectors
      .filter((row) => row.source.path === path && !movedIdentities.has(JSON.stringify([
        row.selector,
        row.source.atContext ?? [],
        row.declarations.signatureSha256,
      ])))
      .map((row) => JSON.stringify([
        row.selector,
        row.source.atContext ?? [],
        row.declarations.signatureSha256,
      ]));
    const actualResidual = parsedStylesheet(path);
    assert.deepEqual(
      actualResidual.map(parsedIdentity),
      expectedResidual,
      `${path}: non-roster deletion, declaration, context, or selector-order drift`,
    );
  }
});

test("M1E2 compact production stage-shell correction stays inside the existing 101/95 owner roster", () => {
  assert.deepEqual(FIXTURE.corrections.map(({ id }) => id), ["M1E2-production-stage-shell-compact-boundary"]);
  const correction = FIXTURE.corrections[0];
  const owner = parsedStylesheet(correction.target);
  const move = FIXTURE.moves.find(({ target }) => target === correction.target);
  assert.ok(move, "the compact correction target must be a frozen move owner");
  const expectedIdentities = new Set(move.oracle.map(oracleIdentity));
  const ownerRoster = owner.filter((row) => expectedIdentities.has(parsedIdentity(row)) || hasCorrectionDeclarations(row, correction));
  assert.equal(ownerRoster.length, move.expectedRows, "the correction must not add a selector row");
  assert.equal(new Set(ownerRoster.map((row) => row.ruleIndex)).size, move.expectedGroups, "the correction must not add a rule group");

  const rows = ownerRoster.filter((row) => hasCorrectionDeclarations(row, correction));
  assert.equal(rows.length, 1, "the corrective declarations must stay in one existing owner row");
  assert.equal(rows[0].selector, correction.selector);
  assert.deepEqual(rows[0].atContext, correction.atContext);
  assert.deepEqual(
    rows[0].declarations.filter(({ property }) => correction.declarations.some((entry) => entry.property === property)),
    correction.declarations,
  );
  const baseTuple = move.oracle.find((tuple) => tuple[TUPLE.legacyId] === correction.baseLegacyId);
  assert.ok(baseTuple, "the correction must name its frozen relocation row");
  assert.equal(parsedIdentity(stripCorrectionDeclarations(rows[0], correction)), oracleIdentity(baseTuple));

  const core = readFileSync(resolve(ROOT, correction.target), "utf8");
  assert.match(core, /@media\s*\(max-width:\s*900px\)/);
  assert.match(core, /\.application-shell:has\(\.processing-workbench-page\) \.modeling-stage-shell/);
  assert.ok(Object.values(M4_FIXTURE.owners)
    .find((ownerEntry) => ownerEntry.path === correction.target)
    .ids.some((id) => M4_FIXTURE.targetTuples
      .find((tuple) => tuple[0] === id)?.[5] === ".application-shell:has(.processing-workbench-page) .modeling-stage-shell"));
  assert.match(core, /min-height:\s*calc\(var\(--ux-interactive-min-block-size\)\s*\*\s*2\)\s*!important/);
  assert.match(core, /flex-basis:\s*calc\(var\(--ux-interactive-min-block-size\)\s*\*\s*2\)\s*!important/);

  const captureHelper = readFileSync(resolve(ROOT, "scripts/capture_issue_261_m1e2_before.py"), "utf8");
  assert.match(captureHelper, /stageNavigationEvidence/);
  assert.match(captureHelper, /buttonCount/);
  assert.match(captureHelper, /withinShellBounds/);
  assert.match(captureHelper, /args\.phase == "after" and label == "breakpoint" and viewport\[0\] <= 900/);
});

test("M1E exclusions, mixed groups, and unique producer imports remain exact", () => {
  const legacy = new Map(FIXTURE.legacySources.map((path) => [path, parsedStylesheet(path)]));
  const targets = FIXTURE.moves.flatMap((move) => parsedStylesheet(move.target).map(parsedIdentity));
  const supersededLegacyPresenceIds = new Set(FIXTURE.preservation.supersededLegacyPresenceIds ?? []);
  for (const tuple of FIXTURE.preservation.excludedAndResponsive) {
    const identity = oracleIdentity(tuple);
    if (supersededLegacyPresenceIds.has(tuple[TUPLE.legacyId])) {
      assert.equal(
        legacy.get(tuple[TUPLE.sourcePath]).filter((row) => parsedIdentity(row) === identity).length,
        0,
        `${tuple[TUPLE.legacyId]} was superseded by an earlier Modeling owner move`,
      );
      assert.equal(targets.includes(identity), true, `${tuple[TUPLE.legacyId]} must remain in its earlier owner stylesheet`);
      continue;
    }
    assert.equal(
      legacy.get(tuple[TUPLE.sourcePath]).filter((row) => parsedIdentity(row) === identity).length,
      1,
      `${tuple[TUPLE.legacyId]} must remain exactly once in legacy`,
    );
    assert.equal(targets.includes(identity), false, `${tuple[TUPLE.legacyId]} leaked into an owner stylesheet`);
  }

  const ownerIdentities = new Set(targets);
  const mixed = groupRows(FIXTURE.preservation.mixedGroups, oracleSourceKey);
  for (const [key, tuples] of mixed) {
    const path = tuples[0][TUPLE.sourcePath];
    const activeTuples = tuples.filter((tuple) => {
      const identity = oracleIdentity(tuple);
      return legacy.get(path).some((row) => parsedIdentity(row) === identity) && !ownerIdentities.has(identity);
    });
    // Historical mixed groups can be wholly superseded by an earlier Modeling
    // owner move.  The current M1E4 contract only retains the audited peers.
    if (activeTuples.length === 0) continue;
    const currentGroups = [...groupRows(legacy.get(path), (row) => row.ruleIndex).values()];
    const expected = groupIdentity(activeTuples, oracleIdentity);
    assert.equal(
      currentGroups.filter((rows) => groupIdentity(rows, parsedIdentity) === expected).length,
      1,
      `mixed source group ${key} was moved or split`,
    );
  }

  const tsxFiles = walkTsx(resolve(ROOT, "apps/web/src"));
  for (const move of FIXTURE.moves) {
    const importLine = `import "${move.importSpecifier}";`;
    const importers = [];
    for (const path of tsxFiles) {
      const source = readFileSync(path, "utf8");
      const count = source.split(importLine).length - 1;
      if (count) importers.push({
        path: relative(ROOT, path).replaceAll("\\", "/"),
        count,
      });
    }
    assert.deepEqual(
      importers.sort((left, right) => left.path.localeCompare(right.path)),
      move.importers.map((path) => ({ path, count: 1 })).sort((left, right) => left.path.localeCompare(right.path)),
      `${move.name}: import ownership drift`,
    );
    for (const importer of move.importers) {
      const current = readFileSync(resolve(ROOT, importer), "utf8").replaceAll("\r\n", "\n");
      const currentWithoutDeclaredM4 = stripDeclaredM4Imports(current, importer);
      assert.equal(
        currentWithoutDeclaredM4,
        currentBaseSource(importer).replaceAll("\r\n", "\n"),
        `${importer}: M1E4 must not change the already-owned side-effect import`,
      );
    }
  }
});

test("M1E historical handoff remains frozen while M4 advances inventory and guard ownership", () => {
  const inventory = JSON.parse(readFileSync(resolve(ROOT, FIXTURE.frozenInventory.path), "utf8"));
  assert.equal(inventory.sourceSha, M4_FIXTURE.baseSha);
  assert.equal(inventory.mergeBaseSha, M4_FIXTURE.baseSha);
  assert.equal(inventory.summary.selectorRows, 1103);
  assert.equal(inventory.summary.cssRuleGroups, 941);
  for (const [batch, expected] of Object.entries(FIXTURE.aggregate.residual.byMigrationBatch)) {
    assert.equal(inventory.migrationPlan.combinedB4.residualRouting[batch], expected, `${batch} route`);
  }
  assert.equal(inventory.summary.byMigrationBatch["M4-shared-cleanup"] ?? 0, 0);
  assert.equal(inventory.summary.byMigrationBatch["ACCEPTED-shared-layout-in-place"], 11);
  assert.equal(inventory.summary.byMigrationBatch["HOLD-owner-or-cross-feature-split"], 525);
  assert.equal(inventory.summary.byMigrationBatch["M6-zero-consumer-removal-candidate"], 529);
  const checkpoints = new Map(inventory.migrationPlan.checkpoints.map((checkpoint) => [checkpoint.unit, checkpoint]));
  assert.equal(checkpoints.get("M1E5-producer-routed-residual").status, "ACCEPTED_MAIN_VISUAL_AND_RUNTIME");
  assert.equal(checkpoints.get("M4-shared-css-ownership-consolidation").approvedMove.rows, 288);

  const baseline = JSON.parse(readFileSync(resolve(ROOT, "apps/web/frontend-guard-baseline.json"), "utf8"));
  const baseBaseline = JSON.parse(execFileSync(
    "git",
    ["show", `${M4_FIXTURE.baseSha}:apps/web/frontend-guard-baseline.json`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 32 * 1024 * 1024 },
  ));
  assert.equal(baseline.sourceSha, M4_FIXTURE.baseSha);
  assert.equal(
    baseline.debt.find((entry) => entry.ruleId === "CMP-FE-GLOBAL-CSS-SELECTOR" && entry.scope === "apps/web/src").count,
    941,
  );
  assert.equal(baseline.hotspots.find((entry) => entry.path === "apps/web/src/styles.css").baselineLines, 3922);
  assert.equal(baseline.hotspots.find((entry) => entry.path === "apps/web/src/design/layout.css").baselineLines, 3767);

  const normalizedBase = structuredClone(baseBaseline);
  normalizedBase.sourceSha = M4_FIXTURE.baseSha;
  normalizedBase.debt.find(
    (entry) => entry.ruleId === "CMP-FE-GLOBAL-CSS-SELECTOR" && entry.scope === "apps/web/src",
  ).count = 941;
  normalizedBase.hotspots.find((entry) => entry.path === "apps/web/src/styles.css").baselineLines = 3922;
  normalizedBase.hotspots.find((entry) => entry.path === "apps/web/src/design/layout.css").baselineLines = 3767;
  const currentExceptions = baseline.exceptions;
  const baseExceptions = normalizedBase.exceptions;
  delete baseline.exceptions;
  delete normalizedBase.exceptions;
  assert.deepEqual(baseline, normalizedBase, "non-relocation guard debt/history changed");

  const m4ExceptionKey = (entry) => `${entry.ruleId}\0${entry.path}\0${entry.fingerprint}`;
  const currentByKey = new Map(currentExceptions.map((entry) => [m4ExceptionKey(entry), entry]));
  const baseByKey = new Map(baseExceptions.map((entry) => [m4ExceptionKey(entry), entry]));
  const removed = [...baseByKey.keys()].filter((key) => !currentByKey.has(key)).sort();
  const added = [...currentByKey.keys()].filter((key) => !baseByKey.has(key)).sort();
  const currentGuardDelta = M4_FIXTURE.frontendGuardDelta;
  assert.equal(removed.length, currentGuardDelta.removedCount);
  assert.equal(added.length, currentGuardDelta.addedCount);
  assert.equal(sha256(JSON.stringify(removed)), currentGuardDelta.removedSha256);
  assert.equal(sha256(JSON.stringify(added)), currentGuardDelta.addedSha256);
  for (const [key, entry] of baseByKey) {
    if (currentByKey.has(key)) assert.deepEqual(currentByKey.get(key), entry, `existing guard exception changed: ${key}`);
  }
  for (const key of removed) {
    const entry = baseByKey.get(key);
    assert.ok(["CMP-FE-GLOBAL-CSS-SELECTOR", "CMP-FE-RAW-COLOR", "CMP-FE-FONT-WEIGHT", "CMP-FE-WIDE-MEDIA"].includes(entry.ruleId));
    assert.ok(new Set([
      ...M4_FIXTURE.legacySources.map(({ path }) => path),
      ...Object.values(M4_FIXTURE.owners).map(({ path }) => path),
      ...Object.values(M4_FIXTURE.ownerCompanions ?? {}),
    ]).has(entry.path));
  }
  for (const key of added) {
    const entry = currentByKey.get(key);
    assert.ok(["CMP-FE-GLOBAL-CSS-SELECTOR", "CMP-FE-RAW-COLOR", "CMP-FE-FONT-WEIGHT", "CMP-FE-WIDE-MEDIA"].includes(entry.ruleId));
    assert.ok(new Set([
      ...M4_FIXTURE.legacySources.map(({ path }) => path),
      ...Object.values(M4_FIXTURE.owners).map(({ path }) => path),
      ...Object.values(M4_FIXTURE.ownerCompanions ?? {}),
    ]).has(entry.path));
    assert.equal(entry.ownerIssue, "#261");
    assert.match(entry.reason, /^FE-06 M4 moves this exact declaration or selector/);
  }
});

test("M1E deferrals, boundary IDs, responsive tuples, and provenance metadata remain explicit", () => {
  const expectedDeferralIds = [
    "CSS-0133", "CSS-0134", "CSS-0138", "CSS-0142", "CSS-0143", "CSS-0144", "CSS-0146", "CSS-0147",
    "CSS-0179", "CSS-0182", "CSS-0183", "CSS-0184", "CSS-0185", "CSS-0235", "CSS-0327", "CSS-0364",
    "CSS-0366", "CSS-0368", "CSS-0372", "CSS-0373", "CSS-0374", "CSS-0379", "CSS-0393", "CSS-0404",
    "CSS-0408", "CSS-0419", "CSS-0423", "CSS-0426", "CSS-0427", "CSS-0429", "CSS-0430", "CSS-0434",
    "CSS-0435", "CSS-0438", "CSS-0443", "CSS-0444", "CSS-0445", "CSS-0446", "CSS-0447", "CSS-0448",
    "CSS-0458", "CSS-0661", "CSS-0663", "CSS-0664", "CSS-0668", "CSS-0669", "CSS-0670", "CSS-0675",
    "CSS-0698", "CSS-0700", "CSS-0702", "CSS-0703", "CSS-0705", "CSS-0706", "CSS-0707", "CSS-0708",
    "CSS-0710", "CSS-0711", "CSS-0712", "CSS-0713", "CSS-0714", "CSS-0718", "CSS-0734", "CSS-1354",
    "CSS-1358", "CSS-1544", "CSS-1545", "CSS-1549", "CSS-1564", "CSS-1577",
  ];
  const expectedBoundaryExactIds = [
    "EXACT-0018", "EXACT-0019", "EXACT-0023", "EXACT-0024", "EXACT-0025", "EXACT-0033", "EXACT-0036",
    "EXACT-0037", "EXACT-0038", "EXACT-0039", "EXACT-0062", "EXACT-0067", "EXACT-0082", "EXACT-0085",
    "EXACT-0087", "EXACT-0088", "EXACT-0089", "EXACT-0090", "EXACT-0092", "EXACT-0093", "EXACT-0094",
    "EXACT-0095",
  ];
  const expectedBoundaryTargetIds = [
    "TARGET-0096", "TARGET-0101", "TARGET-0105", "TARGET-0107", "TARGET-0111", "TARGET-0114", "TARGET-0121",
    "TARGET-0122", "TARGET-0123", "TARGET-0126", "TARGET-0131", "TARGET-0132", "TARGET-0148", "TARGET-0151",
    "TARGET-0152", "TARGET-0183", "TARGET-0184", "TARGET-0185", "TARGET-0186", "TARGET-0212", "TARGET-0249",
    "TARGET-0250", "TARGET-0251", "TARGET-0252", "TARGET-0253", "TARGET-0254", "TARGET-0255", "TARGET-0256",
    "TARGET-0257", "TARGET-0275", "TARGET-0293", "TARGET-0294", "TARGET-0295", "TARGET-0326", "TARGET-0327",
    "TARGET-0334", "TARGET-0335", "TARGET-0353", "TARGET-0356", "TARGET-0357", "TARGET-0358", "TARGET-0359",
    "TARGET-0360", "TARGET-0361", "TARGET-0365", "TARGET-0373", "TARGET-0374", "TARGET-0375", "TARGET-0377",
    "TARGET-0378", "TARGET-0379", "TARGET-0380", "TARGET-0407", "TARGET-0986", "TARGET-0987", "TARGET-0995",
  ];
  const expectedResponsiveIds = ["CSS-0169", "CSS-0170", "CSS-0171", "CSS-0634", "CSS-0635", "CSS-1815", "CSS-1816"];

  const deferrals = FIXTURE.preservation.deferrals;
  const supersededDeferralIds = new Set(FIXTURE.preservation.supersededDeferralIds ?? []);
  assert.deepEqual(deferrals.ids, expectedDeferralIds);
  assert.deepEqual(deferrals.tuples.map((tuple) => tuple[TUPLE.legacyId]), expectedDeferralIds);
  assert.equal(sha256(JSON.stringify(deferrals.tuples)), deferrals.orderedTupleSha256);
  const legacy = new Map(FIXTURE.legacySources.map((path) => [path, parsedStylesheet(path)]));
  const ownerIdentities = new Set(FIXTURE.moves.flatMap((move) => parsedStylesheet(move.target).map(parsedIdentity)));
  for (const tuple of deferrals.tuples) {
    const identity = oracleIdentity(tuple);
    if (supersededDeferralIds.has(tuple[TUPLE.legacyId])) {
      assert.equal(
        legacy.get(tuple[TUPLE.sourcePath]).filter((row) => parsedIdentity(row) === identity).length,
        0,
        `${tuple[TUPLE.legacyId]} was superseded by the approved M1E4 roster`,
      );
      assert.equal(ownerIdentities.has(identity), true, `${tuple[TUPLE.legacyId]} must be present in its M1E4 owner CSS`);
      continue;
    }
    assert.equal(
      legacy.get(tuple[TUPLE.sourcePath]).filter((row) => parsedIdentity(row) === identity).length,
      1,
      `${tuple[TUPLE.legacyId]} deferral must remain exactly once in legacy CSS`,
    );
    assert.equal(ownerIdentities.has(identity), false, `${tuple[TUPLE.legacyId]} deferral leaked into an owner CSS file`);
  }

  assert.deepEqual(FIXTURE.preservation.boundaryExactIds, expectedBoundaryExactIds);
  assert.deepEqual(FIXTURE.preservation.boundaryTargetIds, expectedBoundaryTargetIds);
  const responsive = FIXTURE.preservation.responsive;
  assert.deepEqual(responsive.ids, expectedResponsiveIds);
  assert.equal(sha256(JSON.stringify(responsive.ids)), responsive.orderedIdSha256);
  const responsiveTuples = FIXTURE.moves.at(-1).oracle.filter((tuple) => responsive.ids.includes(tuple[TUPLE.legacyId]));
  assert.equal(responsiveTuples.length, expectedResponsiveIds.length);
  assert.ok(responsiveTuples.every((tuple) => tuple[TUPLE.atContext].some((context) => /@media/.test(context))));

  const testOnlyStateContracts = [
    { label: "stale-recipe-conflict", status: "N/A", reason: "No pre-existing exact fixture safely produces this server conflict; M1E2 does not invent a behavior test for CSS relocation.", tests: [] },
    { label: "family-context-error", tests: ["apps/web/src/material-modeling-workspace.test.tsx::blocks a stale URL Material revision instead of substituting its current head", "apps/web/src/material-modeling-workspace.test.tsx::blocks a stale URL State revision instead of substituting its current head"] },
    { label: "hidden-support-drawer", status: "test-only/N/A for live capture", reason: "The core layout intentionally hides this companion.", tests: ["apps/web/src/common-processing-workbench.test.tsx::characterizes exact Data, Process, Fit, and Export continuity with explicit recovery"] },
    { label: "uncalculated-process-plot", status: "test-only/N/A for live capture", reason: "The canonical seeded route resumes its saved Process preview, and no immediate deterministic UI action guarantees an empty plot without mutating demo data.", tests: ["apps/web/src/common-processing-workbench.test.tsx::restores history settings as a draft while preserving the saved Process current across rerender and reload", "apps/web/src/common-processing-workbench.test.tsx::defers Process reconciliation until Material context resolves without empty workspace patches"] },
  ];
  const expectedStories = [
    "foundation-modelingworkspacelayout--default",
    "foundation-modelingworkspacelayout--ribbon-collapsed",
    "foundation-modelingworkspacelayout--export-reclaims-navigator",
    "governed-workflowcomponents--modeling-stage-selected-with-readiness",
    "governed-workflowcomponents--modeling-stage-blocked",
  ];
  for (const phase of ["before", "after"]) {
    const evidenceRoot = resolve(ROOT, `docs/17-evidence/images/issue-261-m1e2-modeling-core-shell/${phase}`);
    const productEvidencePath = resolve(evidenceRoot, "product/cascade-provenance.json");
    const storybookEvidencePath = resolve(evidenceRoot, "storybook/storybook-cascade-provenance.json");
    assert.equal(existsSync(productEvidencePath), true, `${phase} product provenance evidence is required`);
    assert.equal(existsSync(storybookEvidencePath), true, `${phase} Storybook provenance evidence is required`);
    const productEvidence = JSON.parse(readFileSync(productEvidencePath, "utf8"));
    assert.deepEqual(productEvidence.viewports, [[1366, 768], [1440, 900], [1920, 1080], [2560, 1440], [3840, 2160]]);
    assert.deepEqual(productEvidence.breakpoints, [[1181, 900], [1180, 900], [901, 768], [900, 768], [861, 768], [860, 768]]);
    assert.deepEqual(productEvidence.captureMetadata, {
      browserZoomPercent: 100,
      deviceScaleFactor: 1,
      visualViewportScale: 1,
      phase,
      evidenceStatus: `${phase}-relocation; every captured state has an explicit successful state assertion`,
    });
    assert.deepEqual(productEvidence.invalidStateRecords, []);
    assert.deepEqual(productEvidence.testOnlyStateContracts, testOnlyStateContracts);
    assert.ok(productEvidence.records.length >= productEvidence.viewports.length * 2 + productEvidence.breakpoints.length * 2);
    assert.ok(productEvidence.records.every((record) => record.pageErrors.length === 0 && record.consoleErrors.length === 0));
    assert.ok(productEvidence.records.every((record) => record.stateEvidence?.valid !== false));
    if (phase === "after") {
      const compactBoundaryRecords = productEvidence.records.filter((record) => (
        record.label === "breakpoint"
        && record.viewport[0] <= 900
      ));
      assert.equal(compactBoundaryRecords.length, 6, "after evidence must cover both routes at 900/861/860px");
      for (const record of compactBoundaryRecords) {
        const navigation = record.stageNavigationEvidence;
        assert.equal(navigation.assertion, "pass", `${record.route} ${record.viewport[0]}px stage navigation assertion`);
        assert.equal(navigation.buttonCount, 4, `${record.route} ${record.viewport[0]}px stage button count`);
        assert.deepEqual(
          navigation.buttons.map((button) => button.label),
          ["Data", "Process", "Fit", "Export"],
          `${record.route} ${record.viewport[0]}px stage labels`,
        );
        assert.equal(navigation.shellBounds.height, 68, `${record.route} ${record.viewport[0]}px stage shell height`);
        assert.equal(navigation.allFourRendered, true, `${record.route} ${record.viewport[0]}px rendered stages`);
        assert.equal(navigation.allFourVisible, true, `${record.route} ${record.viewport[0]}px visible stages`);
        assert.equal(navigation.allFourWithinShellBounds, true, `${record.route} ${record.viewport[0]}px bounded stages`);
        assert.equal(navigation.allFourReachable, true, `${record.route} ${record.viewport[0]}px reachable stages`);
      }
    }

    const storybookEvidence = JSON.parse(readFileSync(storybookEvidencePath, "utf8"));
    assert.deepEqual(storybookEvidence.stories, expectedStories);
    assert.deepEqual(storybookEvidence.captureMetadata, {
      browserZoomPercent: 100,
      deviceScaleFactor: 1,
      visualViewportScale: 1,
      phase,
      evidenceStatus: `${phase}-relocation Storybook provenance`,
    });
    assert.ok(storybookEvidence.records.length >= storybookEvidence.stories.length);
    assert.ok(storybookEvidence.records.every((record) => record.pageErrors.length === 0 && record.consoleErrors.length === 0));
    assert.ok(storybookEvidence.records.some((record) => record.viewport[0] === 1181));
    assert.ok(storybookEvidence.records.some((record) => record.viewport[0] === 1180));
    assert.ok(storybookEvidence.records.some((record) => record.viewport[0] === 901));
    assert.ok(storybookEvidence.records.some((record) => record.viewport[0] === 900));
  }

  const comparison = JSON.parse(readFileSync(resolve(
    ROOT,
    "docs/17-evidence/images/issue-261-m1e2-modeling-core-shell/before-after-comparison.json",
  ), "utf8"));
  assert.equal(comparison.result, "PASS");
  assert.deepEqual({
    imagePairs: comparison.areas.product.imagePairs,
    pixelIdenticalPairs: comparison.areas.product.pixelIdenticalPairs,
    intentionalCorrectionPairs: comparison.areas.product.intentionalCorrectionPairs,
    boundedNativeControlRasterVariancePairs: comparison.areas.product.boundedNativeControlRasterVariancePairs,
    unexpectedChangedPairs: comparison.areas.product.unexpectedChangedPairs,
    requiredFiveViewportPairs: comparison.areas.product.requiredFiveViewportPairs,
    requiredFiveViewportGeometryPassPairs: comparison.areas.product.requiredFiveViewportGeometryPassPairs,
    unaffectedComputedBoundsDriftRecords: comparison.areas.product.unaffectedComputedBoundsDriftRecords,
    normalizedRelocationDeclarationDriftRecords: comparison.areas.product.normalizedRelocationDeclarationDriftRecords,
  }, {
    imagePairs: 119,
    pixelIdenticalPairs: 98,
    intentionalCorrectionPairs: 18,
    boundedNativeControlRasterVariancePairs: 3,
    unexpectedChangedPairs: 0,
    requiredFiveViewportPairs: 50,
    requiredFiveViewportGeometryPassPairs: 50,
    unaffectedComputedBoundsDriftRecords: 0,
    normalizedRelocationDeclarationDriftRecords: 0,
  });
  assert.deepEqual({
    imagePairs: comparison.areas.storybook.imagePairs,
    pixelIdenticalPairs: comparison.areas.storybook.pixelIdenticalPairs,
    computedBoundsDriftRecords: comparison.areas.storybook.computedBoundsDriftRecords,
    normalizedRelocationDeclarationDriftRecords: comparison.areas.storybook.normalizedRelocationDeclarationDriftRecords,
  }, {
    imagePairs: 15,
    pixelIdenticalPairs: 15,
    computedBoundsDriftRecords: 0,
    normalizedRelocationDeclarationDriftRecords: 0,
  });
});

test("M1E Storybook importer is unique and follows the shared layout import", () => {
  const move = FIXTURE.moves.at(-1);
  const importLine = `import "${move.storybookImportSpecifier}";`;
  const storybookFiles = walkSourceFiles(resolve(ROOT, "apps/web/.storybook"));
  const importers = storybookFiles.flatMap((path) => {
    const source = readFileSync(path, "utf8");
    const count = source.split(importLine).length - 1;
    return count ? [{ path: relative(ROOT, path).replaceAll("\\", "/"), count }] : [];
  });
  assert.deepEqual(importers, move.storybookImporters.map((path) => ({ path, count: 1 })));
  const previewPath = resolve(ROOT, move.storybookImporters[0]);
  const preview = readFileSync(previewPath, "utf8").replaceAll("\r\n", "\n");
  const layoutImport = 'import "../src/design/layout.css";';
  assert.ok(preview.indexOf(layoutImport) >= 0);
  assert.equal(preview.indexOf(layoutImport) < preview.indexOf(importLine), true);
});

test("M1E integration does not touch forbidden app or global import owners", () => {
  const changed = new Set([
    ...execFileSync("git", ["diff", "--name-only", M4_FIXTURE.baseSha, "--"], { cwd: ROOT, encoding: "utf8" }).split(/\r?\n/),
    ...execFileSync("git", ["ls-files", "--others", "--exclude-standard"], { cwd: ROOT, encoding: "utf8" }).split(/\r?\n/),
  ].filter(Boolean).map((path) => path.replaceAll("\\", "/")));
  for (const path of FIXTURE.forbiddenChangedPaths) assert.equal(changed.has(path), false, path);
});

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const FIXTURE = JSON.parse(readFileSync(
  join(ROOT, "scripts/fixtures/issue-261-m1e4-modeling-core-stage-ownership.json"),
  "utf8",
));
const M1E5_FIXTURE = JSON.parse(readFileSync(
  join(ROOT, "scripts/fixtures/issue-261-m1e5-producer-routed-residual.json"),
  "utf8",
));
const FROZEN_INVENTORY = JSON.parse(execFileSync(
  "git",
  ["show", `${FIXTURE.baseSha}:${FIXTURE.frozenInventory.path}`],
  { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
));

function expandRanges(ranges, prefix = "CSS-") {
  return ranges.flatMap((range) => {
    const [startText, endText] = range.split("..");
    const start = Number(startText.slice(prefix.length));
    const end = endText ? Number(endText) : start;
    return Array.from({ length: end - start + 1 }, (_, index) => `${prefix}${String(start + index).padStart(4, "0")}`);
  });
}

function expandGroupRanges(ranges) {
  return ranges.flatMap((range) => {
    const [startText, endText] = range.split("..");
    const start = Number(startText);
    const end = endText ? Number(endText) : start;
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  });
}

function normalizeSpace(value) {
  return value.replace(/\s+/g, " ").trim();
}

function declarationSignature(declarations) {
  return createHash("sha256")
    .update(JSON.stringify(declarations.map(({ property, value, important }) => [property, value, important])))
    .digest("hex");
}

function inventoryIdentity(row) {
  return [
    normalizeSpace(row.selector),
    (row.source.atContext ?? []).join(" | "),
    row.declarations.signatureSha256,
  ].join("\0");
}

function cssIdentity(row) {
  return [
    normalizeSpace(row.selector),
    (row.atContext ?? []).join(" | "),
    declarationSignature(row.declarations),
  ].join("\0");
}

const M1E5_TARGET_IDENTITIES = new Set(M1E5_FIXTURE.targetTuples
  .filter((tuple) => M1E5_FIXTURE.approvedIds.includes(tuple[0]))
  .map((tuple) => [normalizeSpace(tuple[5]), tuple[6].join(" | "), tuple[10]].join("\0")));

function sourceGroupKey(path, ruleIndex) {
  return `${path.endsWith("styles.css") ? "styles.css" : "layout.css"}#${ruleIndex}`;
}

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

function normalizeTrailingWhitespace(value) {
  return value.replace(/[ \t]+$/gm, "");
}

function splitTopLevel(value, delimiter = ",") {
  const parts = [];
  let start = 0;
  let round = 0;
  let square = 0;
  let quote = null;
  for (let index = 0; index <= value.length; index += 1) {
    const character = value[index] ?? delimiter;
    if (quote) {
      if (character === "\\") index += 1;
      else if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if (character === "(") round += 1;
    else if (character === ")") round = Math.max(0, round - 1);
    else if (character === "[") square += 1;
    else if (character === "]") square = Math.max(0, square - 1);
    else if (character === delimiter && round === 0 && square === 0) {
      parts.push(value.slice(start, index).trim());
      start = index + 1;
    }
  }
  return parts.filter(Boolean);
}

function stripCommentsPreserveLines(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\r\n]/g, " "));
}

/** Return byte spans using the inventory's selector-row ruleIndex convention. */
function scanCss(source) {
  const clean = stripCommentsPreserveLines(source);
  const stack = [];
  const rules = [];
  let tokenStart = 0;
  let quote = null;
  for (let index = 0; index < clean.length; index += 1) {
    const character = clean[index];
    if (quote) {
      if (character === "\\") index += 1;
      else if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if (character === ";") {
      tokenStart = index + 1;
      continue;
    }
    if (character === "{") {
      const rawPrelude = clean.slice(tokenStart, index);
      const prelude = rawPrelude.trim();
      const leading = rawPrelude.search(/\S|$/);
      stack.push({
        type: prelude.startsWith("@") ? "at" : "rule",
        prelude,
        atContext: stack.filter((entry) => entry.type === "at").map((entry) => normalizeSpace(entry.prelude)),
        bodyStart: index + 1,
        open: index,
        start: tokenStart + leading,
      });
      tokenStart = index + 1;
      continue;
    }
    if (character !== "}") continue;
    const entry = stack.pop();
    if (entry?.type === "rule" && entry.prelude) {
      const ruleIndex = rules.length + 1;
      splitTopLevel(entry.prelude).forEach((selector, selectorIndex) => {
        rules.push({
          ruleIndex,
          selectorIndex: selectorIndex + 1,
          selector: normalizeSpace(selector),
          atContext: entry.atContext,
          start: entry.start,
          open: entry.open,
          close: index,
          bodyStart: entry.bodyStart,
        });
      });
    }
    tokenStart = index + 1;
  }
  return rules;
}

function deriveLegacyAfterMove(path) {
  const source = readBaseSource(path);
  const sourceRules = scanCss(source);
  const targetByKey = new Map(
    FROZEN_INVENTORY.selectors
      .filter((row) => TARGET_IDS.has(row.id) && row.source.path === path)
      .map((row) => [`${path}#${row.source.ruleIndex}#${row.source.selectorIndex}`, row]),
  );
  const groups = new Map();
  for (const rule of sourceRules) {
    const key = `${path}#${rule.ruleIndex}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(rule);
  }
  const replacements = [];
  for (const [key, group] of groups) {
    const moved = group.filter((rule) => targetByKey.has(`${key}#${rule.selectorIndex}`));
    if (!moved.length) continue;
    const first = group[0];
    const originalPrelude = source.slice(first.start, first.open);
    const originalSelectors = splitTopLevel(originalPrelude);
    const movedIndexes = new Set(moved.map((rule) => rule.selectorIndex));
    const remaining = originalSelectors.filter((_, index) => !movedIndexes.has(index + 1));
    const body = source.slice(first.bodyStart, first.close);
    replacements.push({
      start: first.start,
      end: first.close + 1,
      text: remaining.length ? `${remaining.join(",\n")} {${body}}` : "",
    });
  }
  return replacements
    .sort((left, right) => right.start - left.start)
    .reduce((value, replacement) => `${value.slice(0, replacement.start)}${replacement.text}${value.slice(replacement.end)}`, source)
    .replace(/[ \t]+$/gm, "");
}

const TARGET_IDS = new Set(expandRanges(FIXTURE.targetIdRanges));
const PLOT_IDS = new Set(expandRanges(FIXTURE.plotIdRanges));
const PEER_IDS = new Set(expandRanges(FIXTURE.retainedPeerIdRanges));
const DEFERRED_IDS = new Set(expandRanges(FIXTURE.deferredIdRanges));
const TARGET_ROWS = FROZEN_INVENTORY.selectors.filter((row) => TARGET_IDS.has(row.id));
const TARGET_BY_ID = new Map(TARGET_ROWS.map((row) => [row.id, row]));
const TARGET_GROUP_KEYS = new Set(TARGET_ROWS.map((row) => sourceGroupKey(row.source.path, row.source.ruleIndex)));
const COMPLETE_GROUP_KEYS = new Set(Object.entries(FIXTURE.completeGroups).flatMap(([file, ranges]) => expandGroupRanges(ranges).map((index) => `${file}#${index}`)));
const MIXED_GROUP_KEYS = new Set(Object.entries(FIXTURE.mixedGroups).flatMap(([file, ranges]) => expandGroupRanges(ranges).map((index) => `${file}#${index}`)));
const LEGACY_PATHS = FIXTURE.legacySources.map((source) => source.path);
const OWNER_PATHS = [FIXTURE.owners.core, FIXTURE.owners.plot];
const frozenLegacyRows = LEGACY_PATHS.flatMap((path) => parseCss(path, readBaseSource(path), null));
const currentLegacyRows = LEGACY_PATHS.flatMap((path) => parseCss(path, readCurrentSource(path), null));
const currentOwnerRows = OWNER_PATHS.flatMap((path) => parseCss(path, readCurrentSource(path), null));

test("M1E4 frozen roster, source order, and extended tuple digest are exact", () => {
  assert.equal(TARGET_ROWS.length, FIXTURE.aggregate.targetRows);
  assert.equal(TARGET_ROWS.filter((row) => !PLOT_IDS.has(row.id)).length, FIXTURE.aggregate.coreRows);
  assert.equal(TARGET_ROWS.filter((row) => PLOT_IDS.has(row.id)).length, FIXTURE.aggregate.plotRows);
  assert.equal(TARGET_GROUP_KEYS.size, FIXTURE.aggregate.targetGroups);
  assert.equal(COMPLETE_GROUP_KEYS.size, FIXTURE.aggregate.completeGroupRemovals);
  assert.equal(MIXED_GROUP_KEYS.size, FIXTURE.aggregate.mixedGroupShrinks);
  assert.deepEqual(new Set([...COMPLETE_GROUP_KEYS, ...MIXED_GROUP_KEYS]), TARGET_GROUP_KEYS);
  assert.equal(PEER_IDS.size, FIXTURE.aggregate.retainedPeerRows);
  assert.equal(DEFERRED_IDS.size, FIXTURE.aggregate.deferredRows);
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
  assert.equal(createHash("sha256").update(JSON.stringify(tuples)).digest("hex"), FIXTURE.targetTupleSha256);
});

test("legacy bytes are the deterministic frozen-base operation and complements remain exact", () => {
  for (const path of LEGACY_PATHS) {
    const current = readCurrentSource(path);
    assert.equal(current, normalizeTrailingWhitespace(current), `${path}: trailing whitespace introduced`);
  }
  const currentByIdentity = new Map();
  for (const row of currentLegacyRows) currentByIdentity.set(cssIdentity(row), (currentByIdentity.get(cssIdentity(row)) ?? 0) + 1);
  for (const row of TARGET_ROWS) assert.equal(currentByIdentity.get(inventoryIdentity(row)) ?? 0, 0, `${row.id}: target remains in legacy CSS`);
  for (const id of [...PEER_IDS, ...DEFERRED_IDS]) {
    const frozen = FROZEN_INVENTORY.selectors.find((row) => row.id === id);
    assert.ok(frozen, `${id}: frozen complement row missing`);
    if (M1E5_TARGET_IDENTITIES.has(inventoryIdentity(frozen))) continue;
    assert.equal(currentByIdentity.get(inventoryIdentity(frozen)) ?? 0, 1, `${id}: complement identity changed`);
  }
  for (const groupKey of COMPLETE_GROUP_KEYS) {
    const groupRows = TARGET_ROWS.filter((row) => sourceGroupKey(row.source.path, row.source.ruleIndex) === groupKey);
    assert.equal(groupRows.every((row) => (currentByIdentity.get(inventoryIdentity(row)) ?? 0) === 0), true, `${groupKey}: complete group remains`);
  }
  for (const groupKey of MIXED_GROUP_KEYS) {
    const groupRows = FROZEN_INVENTORY.selectors.filter((row) => sourceGroupKey(row.source.path, row.source.ruleIndex) === groupKey);
    const retained = groupRows.filter((row) => !TARGET_IDS.has(row.id));
    assert.equal(retained.length > 0, true, `${groupKey}: mixed group has no retained peer`);
    for (const row of retained) assert.equal(currentByIdentity.get(inventoryIdentity(row)) ?? 0, 1, `${row.id}: mixed peer moved`);
  }
  assert.equal(new Set(currentLegacyRows.map((row) => `${row.path}#${row.ruleIndex}`)).size, M1E5_FIXTURE.expectedAfter.cssRuleGroups);
  assert.equal(currentLegacyRows.length, M1E5_FIXTURE.expectedAfter.selectorRows);
});

test("hyperelastic chart selectors stay deferred in the original global producer order", () => {
  const residualIds = new Set(["CSS-1618", "CSS-1619"]);
  for (const id of residualIds) {
    assert.equal(TARGET_IDS.has(id), false, `${id}: family-specific chart rule must remain out of M1E4 targets`);
    assert.equal(DEFERRED_IDS.has(id), true, `${id}: family-specific chart rule must remain deferred`);
  }
  const residual = currentLegacyRows.filter((row) => residualIds.has(
    row.selector === ".hyperelastic-response-plot .chart-axis" ? "CSS-1618"
      : row.selector === ".hyperelastic-response-plot .chart-tick" ? "CSS-1619" : "",
  ));
  assert.deepEqual(residual.map((row) => row.path), [
    "apps/web/src/styles.css",
    "apps/web/src/styles.css",
  ]);
  assert.deepEqual(residual.map((row) => row.selector), [
    ".hyperelastic-response-plot .chart-axis",
    ".hyperelastic-response-plot .chart-tick",
  ]);
  assert.ok(residual[0].ruleIndex < residual[1].ruleIndex, "chart-axis must precede chart-tick in the original producer order");
  assert.equal(currentOwnerRows.some((row) => residualIds.has(
    row.selector === ".hyperelastic-response-plot .chart-axis" ? "CSS-1618"
      : row.selector === ".hyperelastic-response-plot .chart-tick" ? "CSS-1619" : "",
  )), false, "deferred chart selectors must not leak into either Modeling owner stylesheet");

  const block = (source) => {
    const start = source.indexOf(".hyperelastic-response-plot .chart-axis {");
    const end = source.indexOf(".modeling-elastomer-workspace", start);
    assert.ok(start >= 0 && end > start, "deferred chart block must remain bounded by its original neighbors");
    return source.slice(start, end);
  };
  assert.equal(block(readCurrentSource("apps/web/src/styles.css")), block(readBaseSource("apps/web/src/styles.css")), "deferred chart bytes/order drifted from the frozen producer");
});

test("owner stylesheets contain each target exactly once with truthful split and preserved declarations", () => {
  const ownerById = new Map();
  for (const row of currentOwnerRows) {
    for (const frozen of TARGET_ROWS) {
      if (cssIdentity(row) !== inventoryIdentity(frozen)) continue;
      if (ownerById.has(frozen.id)) assert.fail(`${frozen.id}: duplicate owner identity`);
      ownerById.set(frozen.id, row);
    }
  }
  assert.equal(ownerById.size, TARGET_ROWS.length);
  for (const frozen of TARGET_ROWS) {
    const owner = ownerById.get(frozen.id);
    assert.ok(owner, `${frozen.id}: owner identity missing`);
    const expectedPath = PLOT_IDS.has(frozen.id) ? FIXTURE.owners.plot : FIXTURE.owners.core;
    assert.equal(owner.path, expectedPath, `${frozen.id}: wrong feature owner`);
    assert.deepEqual(owner.atContext, frozen.source.atContext, `${frozen.id}: at-context changed`);
    assert.equal(declarationSignature(owner.declarations), frozen.declarations.signatureSha256, `${frozen.id}: declaration signature changed`);
    const original = frozenLegacyRows.find((row) => cssIdentity(row) === inventoryIdentity(frozen));
    assert.ok(original, `${frozen.id}: frozen declaration row missing`);
    assert.deepEqual(owner.declarations.map((declaration) => declaration.property), original.declarations.map((declaration) => declaration.property), `${frozen.id}: property order changed`);
    assert.deepEqual(owner.declarations.map((declaration) => [declaration.property, declaration.important]), original.declarations.map((declaration) => [declaration.property, declaration.important]), `${frozen.id}: important flags/order changed`);
  }
  const ownerTargetOrder = [...ownerById.entries()]
    .sort((left, right) => left[1].path.localeCompare(right[1].path) || left[1].ruleIndex - right[1].ruleIndex || left[1].selectorIndex - right[1].selectorIndex)
    .map(([id]) => id);
  const expectedOrder = [...TARGET_ROWS]
    .sort((left, right) => left.source.mainImportRank - right.source.mainImportRank || left.source.ruleIndex - right.source.ruleIndex || left.source.selectorIndex - right.source.selectorIndex)
    .map((row) => row.id);
  assert.deepEqual(new Set(ownerTargetOrder), new Set(expectedOrder));
  assert.equal(new Set(ownerTargetOrder).size, expectedOrder.length);
});

test("inventory and existing consumers record the post-move global totals", () => {
  const inventory = JSON.parse(readFileSync(join(ROOT, FIXTURE.frozenInventory.path), "utf8"));
  assert.equal(inventory.mergeBaseSha, M1E5_FIXTURE.baseSha);
  assert.equal(inventory.summary.selectorRows, M1E5_FIXTURE.expectedAfter.selectorRows);
  assert.equal(inventory.summary.cssRuleGroups, M1E5_FIXTURE.expectedAfter.cssRuleGroups);
  assert.equal(inventory.summary.byMigrationBatch["M1E-modeling-shell-and-family"] ?? 0, M1E5_FIXTURE.expectedAfter.m1eRows);
  const m1eGroups = new Set(inventory.selectors
    .filter((row) => row.owner.migrationBatch === "M1E-modeling-shell-and-family")
    .map((row) => sourceGroupKey(row.source.path, row.source.ruleIndex)));
  assert.equal(m1eGroups.size, M1E5_FIXTURE.expectedAfter.m1eGroups);
  assert.equal(inventory.summary.flags.crossCssDuplicate, M1E5_FIXTURE.expectedAfter.crossCssDuplicateRows);
  const consumers = [
    ["apps/web/src/material-modeling-workspace.tsx", "./features/modeling/ui/modeling-core-workbench.css"],
    ["apps/web/src/engineering-curve-plot.tsx", "./features/modeling/ui/modeling-engineering-curve-plot.css"],
  ];
  for (const [path, specifier] of consumers) {
    const source = readFileSync(join(ROOT, path), "utf8");
    assert.equal(source.split(specifier).length - 1, 1, `${path}: ${specifier} import count`);
  }
});

test("approved fixture is bounded to Modeling and records the pinned synthetic journey", () => {
  assert.deepEqual(FIXTURE.fixture, {
    material: "DP780",
    testDataKey: "CMP-DEMO-DP780-TEST-JSON",
    testDataRevision: "rev1",
    testDataTitle: "Tensile test 0001",
    fitMethod: "swift+voce",
    fitMethodLabel: "swift + voce 50/50",
    target: "abaqus/2025/kg_m_s",
    approximation: "openradioss/2025/kg_m_s",
    nativeMaterialName: "DP780_C1_REFERENCE",
  });
  assert.equal(FIXTURE.imports.core.length, 1);
  assert.equal(FIXTURE.imports.plot.length, 1);
});

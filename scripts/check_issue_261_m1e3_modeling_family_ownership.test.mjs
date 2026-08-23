import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const FIXTURE = JSON.parse(readFileSync(
  join(ROOT, "scripts/fixtures/issue-261-m1e3-modeling-family-ownership.json"),
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

function normalizeSelector(value) {
  return value.replace(/\s+/g, " ").trim();
}

function declarationSignature(declarations) {
  return createHash("sha256")
    .update(JSON.stringify(declarations.map(({ property, value, important }) => [property, value, important])))
    .digest("hex");
}

function identity(selector, atContext, signature) {
  return [normalizeSelector(selector), (atContext ?? []).join(" | "), signature].join("\0");
}

function inventoryIdentity(row) {
  return identity(row.selector, row.source.atContext, row.declarations.signatureSha256);
}

function cssIdentity(row) {
  return identity(row.selector, row.atContext, declarationSignature(row.declarations));
}

function readCss(path) {
  return readFileSync(join(ROOT, path), "utf8");
}

function rowsFor(path) {
  return parseCss(path, readCss(path), null);
}

const targetIds = new Set(FIXTURE.moves.flatMap((move) => move.ids));
const targetRows = FROZEN_INVENTORY.selectors.filter((row) => targetIds.has(row.id));
const targetById = new Map(targetRows.map((row) => [row.id, row]));

test("M1E3 frozen roster and tuple digest are exact", () => {
  assert.equal(targetRows.length, FIXTURE.aggregate.targetRows);
  const groups = new Map();
  for (const row of targetRows) {
    const key = [row.source.path, row.source.ruleIndex, row.source.atContext.join(" | ")].join("\0");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  assert.equal(groups.size, FIXTURE.aggregate.targetGroups);
  const allFrozenGroups = new Map();
  for (const row of FROZEN_INVENTORY.selectors) {
    const key = [row.source.path, row.source.ruleIndex, row.source.atContext.join(" | ")].join("\0");
    if (!allFrozenGroups.has(key)) allFrozenGroups.set(key, []);
    allFrozenGroups.get(key).push(row);
  }
  const mixed = [...groups].filter(([key, rows]) => rows.length < allFrozenGroups.get(key).length);
  assert.equal(mixed.length, FIXTURE.aggregate.mixedGroupShrinks);
  assert.equal(groups.size - mixed.length, FIXTURE.aggregate.fullGroupRemovals);

  const tuples = [...targetRows]
    .sort((left, right) => left.source.path.localeCompare(right.source.path)
      || left.source.ruleIndex - right.source.ruleIndex
      || left.source.selectorIndex - right.source.selectorIndex)
    .map((row) => [
      row.id,
      row.source.path,
      row.source.ruleIndex,
      row.source.selectorIndex,
      row.selector,
      row.source.atContext,
      row.declarations.signatureSha256,
    ]);
  assert.equal(
    createHash("sha256").update(JSON.stringify(tuples)).digest("hex"),
    FIXTURE.targetTupleSha256,
  );
});

test("M1E3 owners contain the moved roster and legacy CSS retains only approved peers", () => {
  const ownerRows = new Map();
  for (const move of FIXTURE.moves) {
    const rows = rowsFor(move.target);
    ownerRows.set(move.target, rows);
    assert.equal(rows.length >= move.rows, true, `${move.target}: owner rows unexpectedly shrank`);
    const expected = move.ids.map((id) => targetById.get(id));
    for (const row of expected) {
      const matches = rows.filter((candidate) => cssIdentity(candidate) === inventoryIdentity(row));
      if (row.id === "CSS-0876") continue;
      assert.equal(matches.length, 1, `${move.target}: ${row.id} owner identity count`);
    }
  }

  const legacyRows = [
    ...rowsFor("apps/web/src/styles.css"),
    ...rowsFor("apps/web/src/design/layout.css"),
  ];
  for (const row of targetRows) {
    const residual = legacyRows.filter((candidate) => cssIdentity(candidate) === inventoryIdentity(row));
    assert.deepEqual(residual, [], `${row.id}: canonical tuple remains in a legacy stylesheet`);
  }
  assert.equal(
    legacyRows.some((row) => normalizeSelector(row.selector) === ".icon-button"),
    false,
    "CSS-0876: icon-button remains in legacy CSS",
  );

  for (const id of FIXTURE.preservedPeers) {
    const row = FROZEN_INVENTORY.selectors.find((candidate) => candidate.id === id);
    assert.ok(row, `${id}: frozen preserved peer missing`);
    assert.equal(
      legacyRows.filter((candidate) => cssIdentity(candidate) === inventoryIdentity(row)).length,
      1,
      `${id}: preserved peer must remain exactly once in legacy CSS`,
    );
  }

  const iconBaseline = parseCss(
    "apps/web/src/styles.css",
    execFileSync("git", ["show", `${FIXTURE.baseSha}:apps/web/src/styles.css`], {
      cwd: ROOT,
      encoding: "utf8",
      maxBuffer: 16 * 1024 * 1024,
    }),
    null,
  ).find((row) => normalizeSelector(row.selector) === ".icon-button");
  const iconOwner = ownerRows.get("apps/web/src/features/modeling/ui/modeling-viscoelastic-workbenches.css")
    .find((row) => normalizeSelector(row.selector) === ".icon-button");
  assert.ok(iconBaseline && iconOwner, "CSS-0876: normalized icon-button owner row missing");
  assert.deepEqual(
    iconOwner.declarations.slice(0, iconBaseline.declarations.length),
    iconBaseline.declarations,
    "CSS-0876: canonical declarations must lead the existing owner rule",
  );

  const inventory = JSON.parse(readFileSync(join(ROOT, FIXTURE.frozenInventory.path), "utf8"));
  const m1eGroups = new Set(inventory.selectors
    .filter((row) => row.owner.migrationBatch === "M1E-modeling-shell-and-family")
    .map((row) => [row.source.path, row.source.ruleIndex, row.source.atContext.join(" | ")].join("\0")));
  assert.deepEqual(
    {
      selectorRows: inventory.summary.selectorRows,
      cssRuleGroups: inventory.summary.cssRuleGroups,
      m1eRows: inventory.summary.byMigrationBatch["M1E-modeling-shell-and-family"] ?? 0,
      m1eGroups: m1eGroups.size,
      crossCssDuplicateRows: inventory.summary.flags.crossCssDuplicate,
    },
    {
      selectorRows: M1E5_FIXTURE.expectedAfter.selectorRows,
      cssRuleGroups: M1E5_FIXTURE.expectedAfter.cssRuleGroups,
      m1eRows: M1E5_FIXTURE.expectedAfter.m1eRows,
      m1eGroups: M1E5_FIXTURE.expectedAfter.m1eGroups,
      crossCssDuplicateRows: M1E5_FIXTURE.expectedAfter.crossCssDuplicateRows,
    },
  );

  for (const move of FIXTURE.moves) {
    const specifier = `./features/modeling/ui/${basename(move.target)}`;
    for (const importer of move.importers) {
      const count = readFileSync(join(ROOT, importer), "utf8").split(specifier).length - 1;
      assert.equal(count, 1, `${importer}: ${specifier} import count`);
    }
  }
  const stageShell = readFileSync(join(ROOT, "apps/web/src/modeling-stage-shell.tsx"), "utf8");
  const exportImports = FIXTURE.moves[2].importOrder.map((specifier) => `import "${specifier}";`);
  let previous = -1;
  for (const line of exportImports) {
    const index = stageShell.indexOf(line);
    assert.ok(index > previous, `modeling-stage-shell.tsx: import order for ${line}`);
    previous = index;
  }
});

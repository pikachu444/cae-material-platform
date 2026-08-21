import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const M2_FIXTURE = JSON.parse(readFileSync(
  new URL("./fixtures/issue-261-m2-materials-css-ownership.json", import.meta.url),
  "utf8",
));

function m2BaselineInventory() {
  const { baselineSha } = M2_FIXTURE;
  assert.match(baselineSha ?? "", /^[0-9a-f]{40}$/, "M2 baselineSha must be a lowercase 40-character Git SHA");
  const currentHead = execFileSync(
    "git",
    ["rev-parse", "HEAD"],
    { cwd: ROOT, encoding: "utf8" },
  ).trim();
  assert.match(currentHead, /^[0-9a-f]{40}$/, "current HEAD must be a lowercase 40-character Git SHA");
  let isAncestor = true;
  try {
    execFileSync(
      "git",
      ["merge-base", "--is-ancestor", baselineSha, currentHead],
      { cwd: ROOT, stdio: "ignore" },
    );
  } catch {
    isAncestor = false;
  }
  assert.equal(isAncestor, true, `M2 baselineSha ${baselineSha} must be an ancestor of current HEAD ${currentHead}`);
  return JSON.parse(execFileSync(
    "git",
    ["show", `${baselineSha}:docs/17-evidence/issue-261-css-selector-inventory.json`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 32 * 1024 * 1024 },
  ));
}

function cssTuple(row) {
  return [row.path, row.selector, JSON.stringify(row.atContext ?? [])].join("\0");
}

function declarationSignature(row) {
  return createHash("sha256")
    .update(JSON.stringify(row.declarations.map(({ property, value, important }) => [property, value, important])))
    .digest("hex");
}

function parsedStylesheet(path) {
  const source = readFileSync(resolve(ROOT, path), "utf8");
  return parseCss(path, source, null);
}

test("M2 fixture closes the exhaustive 405-row reclassification roster", () => {
  const groups = Object.values(M2_FIXTURE.ids).map((ids) => new Set(ids));
  const all = groups.flatMap((ids) => [...ids]);
  assert.equal(all.length, M2_FIXTURE.expected.exhaustiveRows);
  assert.equal(new Set(all).size, M2_FIXTURE.expected.exhaustiveRows);
  assert.equal(M2_FIXTURE.ids.materials.length, M2_FIXTURE.expected.materialsRows);
  assert.equal(M2_FIXTURE.ids.activity.length, M2_FIXTURE.expected.activityRows);
  assert.equal(M2_FIXTURE.ids.modeling.length, M2_FIXTURE.expected.modelingRows);
  assert.equal(M2_FIXTURE.ids.m4.length, M2_FIXTURE.expected.m4Rows);
  assert.equal(M2_FIXTURE.ids.hold.length, M2_FIXTURE.expected.holdRows);
  for (let left = 0; left < groups.length; left += 1) {
    for (let right = left + 1; right < groups.length; right += 1) {
      assert.equal(
        [...groups[left]].some((id) => groups[right].has(id)),
        false,
        `M2 roster overlap between groups ${left} and ${right}`,
      );
    }
  }
  assert.equal(M2_FIXTURE.mixedGroups.length, M2_FIXTURE.expected.materialsMixedGroups);
  assert.deepEqual(
    M2_FIXTURE.mixedGroups.map((group) => group.rule),
    [21, 24, 29, 44, 47, 51, 60, 73, 137, 139, 181, 199, 201, 203, 212, 218, 316, 549, 552, 1367, 1370, 1376],
  );
});

test("M2 owner overrides are exact source tuples with no non-roster matches", () => {
  const baseline = m2BaselineInventory();
  const rosterById = new Map();
  for (const [owner, ids] of Object.entries(M2_FIXTURE.ids)) {
    for (const id of ids) rosterById.set(id, owner);
  }
  const entries = Object.entries(M2_FIXTURE.overrides).flatMap(([owner, rows]) =>
    rows.map((row) => ({ owner, ...row })),
  );
  const entryKeys = new Set(entries.map(cssTuple));
  const baselineRowsByKey = new Map();
  for (const row of baseline.selectors) {
    const key = cssTuple({
      path: row.source.path,
      selector: row.selector,
      atContext: row.source.atContext,
    });
    if (!baselineRowsByKey.has(key)) baselineRowsByKey.set(key, []);
    baselineRowsByKey.get(key).push(row);
  }
  for (const entry of entries) {
    const matches = baselineRowsByKey.get(cssTuple(entry)) ?? [];
    assert.ok(matches.length > 0, `override tuple has no baseline row: ${cssTuple(entry)}`);
    for (const row of matches) {
      const rosterOwner = rosterById.get(row.id);
      const expectedOwner = {
        activity: "activity-specific",
        modeling: "modeling-specific",
        m4: "shared-pane-split-layout",
        hold: "legacy-cross-feature",
      }[rosterOwner];
      assert.equal(expectedOwner, entry.owner, `override tuple changed non-roster owner ${row.id}`);
    }
  }
  for (const row of baseline.selectors) {
    if (rosterById.has(row.id)) continue;
    const key = cssTuple({
      path: row.source.path,
      selector: row.selector,
      atContext: row.source.atContext,
    });
    assert.equal(entryKeys.has(key), false, `non-roster row shares an M2 override tuple: ${row.id}`);
  }
  for (const [owner, ids] of Object.entries(M2_FIXTURE.ids)) {
    if (owner === "materials") continue;
    for (const id of ids) {
      const row = baseline.selectors.find((candidate) => candidate.id === id);
      assert.ok(row, `missing baseline roster row ${id}`);
      assert.equal(entryKeys.has(cssTuple({
        path: row.source.path,
        selector: row.selector,
        atContext: row.source.atContext,
      })), true, `missing exact override tuple for ${id}`);
    }
  }
});

test("M2 extraction preserves 257 selector rows, 221 groups, mixed signatures, and at-rule context", () => {
  const baseline = m2BaselineInventory();
  const materialsIds = new Set(M2_FIXTURE.ids.materials);
  const baselineMaterials = baseline.selectors.filter((row) => materialsIds.has(row.id));
  const materialsRows = parsedStylesheet(M2_FIXTURE.materialsSourcePath);
  const layoutRows = parsedStylesheet(M2_FIXTURE.legacyLayoutPath);
  assert.equal(materialsRows.length, M2_FIXTURE.expected.materialsRows);
  assert.equal(new Set(materialsRows.map((row) => row.ruleIndex)).size, M2_FIXTURE.expected.materialsRuleGroups);
  assert.equal(layoutRows.length, M2_FIXTURE.expected.postLayoutRows);
  assert.equal(new Set(layoutRows.map((row) => row.ruleIndex)).size, M2_FIXTURE.expected.postLayoutRuleGroups);
  const materialTupleKeys = new Set(materialsRows.map((row) => cssTuple(row)));
  const layoutSignatures = new Set(layoutRows.map((row) => `${cssTuple(row)}\0${declarationSignature(row)}`));
  for (const row of baselineMaterials) {
    const key = cssTuple({ path: M2_FIXTURE.materialsSourcePath, selector: row.selector, atContext: row.source.atContext });
    const matches = materialsRows.filter((candidate) =>
      cssTuple(candidate) === key && declarationSignature(candidate) === row.declarations.signatureSha256,
    );
    assert.equal(matches.length, 1, `missing or duplicated moved selector ${row.id}`);
    assert.equal(materialTupleKeys.has(key), true);
    assert.equal(layoutSignatures.has(`${cssTuple({ path: M2_FIXTURE.legacyLayoutPath, selector: row.selector, atContext: row.source.atContext })}\0${row.declarations.signatureSha256}`), false, `moved row remains in layout ${row.id}`);
  }
  const mixed = M2_FIXTURE.mixedGroups;
  const mixedMoved = new Set(mixed.flatMap((group) => group.moved));
  const mixedResidual = new Set(mixed.flatMap((group) => group.residual));
  assert.equal(mixedMoved.size, 29);
  assert.equal(mixedResidual.size, mixed.flatMap((group) => group.residual).length);
  for (const group of mixed) {
    const movedRows = group.moved.map((id) => baseline.selectors.find((row) => row.id === id));
    const residualRows = group.residual.map((id) => baseline.selectors.find((row) => row.id === id));
    assert.ok(movedRows.every(Boolean));
    assert.ok(residualRows.every(Boolean));
    assert.equal(new Set(movedRows.map((row) => row.declarations.signatureSha256)).size, 1);
    assert.equal(movedRows[0].declarations.signatureSha256, group.signature);
    assert.equal(new Set(residualRows.map((row) => row.source.ruleIndex)).size, 1);
  }
  assert.equal(mixedMoved.size + baselineMaterials.filter((row) => !mixedMoved.has(row.id)).length, M2_FIXTURE.expected.materialsRows);
});

test("M2 import order, source hashes, and accepted external target disjointness are frozen", () => {
  const main = readFileSync(resolve(ROOT, "apps/web/src/main.tsx"), "utf8");
  const imports = [...main.matchAll(/import\s+["']([^"']+\.css)["']/g)].map((match) => `apps/web/src/${match[1].replace(/^\.\//, "")}`);
  assert.deepEqual(imports.slice(0, M2_FIXTURE.importOrder.length), M2_FIXTURE.importOrder);
  for (const [path, expected] of Object.entries(M2_FIXTURE.sourceExpectations)) {
    const source = readFileSync(resolve(ROOT, path));
    assert.equal(source.byteLength, expected.bytes, `${path} byte count`);
    assert.equal(createHash("sha256").update(source).digest("hex"), expected.sha256, `${path} hash`);
  }
  const baseline = m2BaselineInventory();
  const rosterById = new Map(Object.entries(M2_FIXTURE.ids).flatMap(([owner, ids]) => ids.map((id) => [id, owner])));
  for (const [groupId, target] of Object.entries(M2_FIXTURE.externalTargets)) {
    const internal = target.internal.map((id) => baseline.selectors.find((row) => row.id === id));
    const external = target.external.map((id) => baseline.selectors.find((row) => row.id === id));
    assert.ok(internal.every(Boolean), `${groupId} internal fixture row missing`);
    assert.ok(external.every(Boolean), `${groupId} external fixture row missing`);
    assert.ok(internal.every((row) => rosterById.get(row.id) === "materials"), `${groupId} internal row outside Materials roster`);
    assert.equal(new Set(internal.map((row) => row.selector)).size, internal.length, `${groupId} moved selectors overlap`);
    assert.equal(new Set(external.map((row) => row.selector)).size, external.length, `${groupId} external selectors overlap`);
    assert.equal(internal.some((row) => external.some((peer) => peer.selector === row.selector)), false, `${groupId} external selector overlap`);
  }
});

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const FIXTURE = JSON.parse(readFileSync(
  join(ROOT, "scripts", "fixtures", "issue-261-m1e-modeling-ownership-integration.json"),
  "utf8",
));
function normalizeContext(context) {
  return (context ?? []).map((value) => String(value)
    .replace(/\s+/g, " ")
    .replace(/:\s+/g, ":")
    .replace(/\((?:width<=|max-width:)\s*([^\)]+)\)/g, "(max-width:$1)")
    .trim());
}

function normalizeSelector(selector) {
  return selector
    .replace(/\s+/g, " ")
    .replace(/\s*([>+~,:])\s*/g, "$1")
    .replace(/\s*([+-])\s*/g, "$1")
    .replace(/\[([^=\]]+)=(["'])?([^\]"']+)\2\]/g, "[$1=$3]")
    .trim();
}

function selectorContextKey(selector, atContext) {
  return JSON.stringify([
    normalizeSelector(selector),
    normalizeContext(atContext),
  ]);
}

function rowIdentity(row) {
  return selectorContextKey(row.selector, row.atContext);
}

function walkCss(directory) {
  if (!existsSync(directory)) return [];
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return walkCss(path);
    return entry.isFile() && extname(entry.name) === ".css" ? [path] : [];
  });
}

function checkBundle(rootArg, label) {
  const root = resolve(ROOT, rootArg);
  const files = walkCss(root);
  assert.ok(files.length > 0, `${label}: no CSS assets under ${rootArg}`);
  const rows = files.flatMap((path) => parseCss(relative(ROOT, path).replaceAll("\\", "/"), readFileSync(path, "utf8"), null));
  const counts = new Map();
  for (const row of rows) {
    const identity = rowIdentity(row);
    counts.set(identity, (counts.get(identity) ?? 0) + 1);
  }
  const allOwnerRows = parseCss(
    FIXTURE.moves.at(-1).target,
    readFileSync(resolve(ROOT, FIXTURE.moves.at(-1).target), "utf8"),
    null,
  );
  const correction = FIXTURE.corrections[0];
  const correctionKey = selectorContextKey(correction.selector, correction.atContext);
  const ownerCorrectionRows = allOwnerRows.filter((row) => rowIdentity(row) === correctionKey);
  assert.equal(ownerCorrectionRows.length, 1, `${label}: compact stage-shell declarations must stay in one existing owner row`);
  assert.equal(allOwnerRows.length, FIXTURE.moves.at(-1).expectedRows, `${label}: source owner row roster drift`);
  assert.equal(new Set(allOwnerRows.map((row) => row.ruleIndex)).size, FIXTURE.moves.at(-1).expectedGroups, `${label}: source owner group roster drift`);
  const ownerRows = allOwnerRows;
  const expectedCounts = new Map();
  const ownerGroups = new Map();
  for (const row of ownerRows) {
    const key = rowIdentity(row);
    if (!ownerGroups.has(key)) ownerGroups.set(key, []);
    ownerGroups.get(key).push(row);
  }
  for (const [key, group] of ownerGroups) {
    const emitted = group.filter((row, index) => !group.slice(index + 1).some((later) => (
      later.declarations.map(({ property }) => property).join("\0")
      === row.declarations.map(({ property }) => property).join("\0")
    )));
    expectedCounts.set(key, emitted.length);
  }
  const missing = [];
  const duplicate = [];
  for (const [identity, expected] of expectedCounts) {
    const count = counts.get(identity) ?? 0;
    const selector = JSON.parse(identity)[0];
    if (count === 0) missing.push(selector);
    if (count !== expected && count > 0) duplicate.push({ selector, expected, count });
  }
  assert.deepEqual(missing, [], `${label}: moved modeling-core selectors missing from generated CSS`);
  assert.deepEqual(duplicate, [], `${label}: moved modeling-core selectors duplicated in generated CSS`);
  const emittedCorrectionRows = rows.filter((row) => rowIdentity(row) === correctionKey);
  assert.equal(emittedCorrectionRows.length, expectedCounts.get(correctionKey), `${label}: compact stage-shell selector/context emitted unexpectedly`);
  const emittedCorrectionProperties = new Set(emittedCorrectionRows.flatMap((row) => row.declarations.map(({ property }) => property)));
  for (const { property } of correction.declarations) {
    assert.ok(emittedCorrectionProperties.has(property), `${label}: compact stage-shell ${property} declaration missing`);
  }

  const ownerAssetFiles = files.filter((path) => parseCss(
    relative(ROOT, path).replaceAll("\\", "/"),
    readFileSync(path, "utf8"),
    null,
  ).some((row) => rowIdentity(row) === correctionKey));
  assert.equal(ownerAssetFiles.length, 1, `${label}: owner selector must be emitted in exactly one CSS asset`);
  if (label === "production") {
    const ownerAssetName = ownerAssetFiles[0].split(/[\\/]/).at(-1);
    assert.match(ownerAssetName, /^material-modeling-workspace-.*\.css$/, `${label}: owner CSS must stay in the lazy Modeling workspace chunk`);
    const ownerJs = readdirSync(root, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && entry.name === "assets")
      .flatMap(() => readdirSync(join(root, "assets")))
      .filter((name) => /^material-modeling-workspace-.*\.js$/.test(name));
    assert.equal(ownerJs.length, 1, `${label}: lazy Modeling workspace JS chunk missing or duplicated`);
    const entryJs = readdirSync(join(root, "assets")).filter((name) => /^index-.*\.js$/.test(name));
    assert.ok(entryJs.some((name) => {
      const source = readFileSync(join(root, "assets", name), "utf8");
      return source.includes(ownerAssetName) && source.includes(ownerJs[0]);
    }), `${label}: entry preload graph does not reference the lazy Modeling owner JS/CSS chunks`);
  }
  return {
    label,
    root: rootArg,
    files: files.map((path) => relative(ROOT, path).replaceAll("\\", "/")),
    cssRows: rows.length,
    oracleRows: ownerRows.length,
    oracleGroups: FIXTURE.moves.at(-1).expectedGroups,
    correctionRows: emittedCorrectionRows.length,
    ownerAssets: ownerAssetFiles.map((path) => relative(ROOT, path).replaceAll("\\", "/")),
  };
}

const productRoot = process.argv[2] ?? "apps/web/dist";
const storybookRoot = process.argv[3] ?? "apps/web/storybook-static";
const result = [checkBundle(productRoot, "production"), checkBundle(storybookRoot, "storybook")];
console.log(JSON.stringify({ ok: true, result }, null, 2));

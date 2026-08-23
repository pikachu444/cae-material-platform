import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const FIXTURE = JSON.parse(readFileSync(
  join(ROOT, "scripts/fixtures/issue-261-m4-shared-css-ownership.json"),
  "utf8",
));
const APPROVED_IDS = new Set(FIXTURE.approvedIds);
const TARGET_ROWS = FIXTURE.targetTuples
  .filter((tuple) => APPROVED_IDS.has(tuple[0]))
  .map((tuple) => ({
    id: tuple[0],
    source: { path: tuple[1], atContext: tuple[6] },
    selector: tuple[5],
    declarations: {
      properties: tuple[8],
      importantProperties: tuple[9],
      signatureSha256: tuple[10],
    },
  }));
const OWNER_BY_ID = new Map(
  Object.values(FIXTURE.owners)
    .flatMap((owner) => owner.ids.map((id) => [id, owner.path])),
);
const OWNER_PATHS = [...new Set(OWNER_BY_ID.values())];
const SHARED_STORYBOOK_OWNERS = new Set([
  "apps/web/src/design/primitives.css",
  "apps/web/src/design/shell.css",
  "apps/web/src/design/tokens.css",
]);

function normalizeSpace(value) {
  return value.replace(/\s+/g, " ").trim();
}

function normalizeSelector(value) {
  return normalizeSpace(value)
    .replace(/\s*,\s*/g, ",")
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")")
    .replace(/\s*([>+~])\s*/g, "$1")
    .replace(/\[([^\]=]+)=["']([^"']+)["']\]/g, "[$1=$2]")
    .replace(/::(before|after|first-line|first-letter|selection|backdrop|placeholder|marker|file-selector-button)/g, ":$1");
}

function splitTopLevel(value) {
  const parts = [];
  let start = 0;
  let round = 0;
  let square = 0;
  let quote = null;
  for (let index = 0; index <= value.length; index += 1) {
    const character = value[index] ?? ",";
    if (quote) {
      if (character === "\\") index += 1;
      else if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'") quote = character;
    else if (character === "(") round += 1;
    else if (character === ")") round = Math.max(0, round - 1);
    else if (character === "[") square += 1;
    else if (character === "]") square = Math.max(0, square - 1);
    else if (character === "," && round === 0 && square === 0) {
      parts.push(value.slice(start, index).trim());
      start = index + 1;
    }
  }
  return parts.filter(Boolean);
}

function selectorMatch(frozen, emitted) {
  const expected = normalizeSelector(frozen);
  const actual = normalizeSelector(emitted);
  if (expected === actual) return true;
  for (const pseudo of [":is(", ":where("]) {
    if (actual.startsWith(pseudo) && actual.endsWith(")")) {
      const members = splitTopLevel(actual.slice(pseudo.length, -1));
      if (members.includes(expected)) return true;
    }
  }
  return false;
}

function normalizeAtContext(values) {
  return values.map((value) => normalizeSpace(value)
    .replace(/\(max-width\s*:\s*([^)]*)\)/g, "(width<=$1)")
    .replace(/\(min-width\s*:\s*([^)]*)\)/g, "(width>=$1)")
    .replace(/\(max-height\s*:\s*([^)]*)\)/g, "(height<=$1)")
    .replace(/\(min-height\s*:\s*([^)]*)\)/g, "(height>=$1)"));
}

function declarationSignature(declarations) {
  return createHash("sha256").update(JSON.stringify(
    declarations.map(({ property, value, important }) => [property, value, important]),
  )).digest("hex");
}

function identity(row) {
  return [
    normalizeSpace(row.selector),
    (row.source?.atContext ?? row.atContext ?? []).join(" | "),
    row.declarations?.signatureSha256 ?? declarationSignature(row.declarations),
  ].join("\0");
}

function bundleMatch(frozen, emitted) {
  if (!selectorMatch(frozen.selector, emitted.selector)) return false;
  if (normalizeAtContext(frozen.source.atContext ?? []).join(" | ")
      !== normalizeAtContext(emitted.atContext ?? []).join(" | ")) return false;
  const properties = new Set(emitted.declarations.map(({ property }) => property));
  const important = new Set(emitted.declarations
    .filter(({ important: isImportant }) => isImportant)
    .map(({ property }) => property));
  const shorthandCoverage = {
    "grid-column": ["grid-area"],
    "grid-row": ["grid-area"],
    "overflow-x": ["overflow"],
    "overflow-y": ["overflow"],
  };
  return frozen.declarations.properties.every((property) => properties.has(property)
      || (shorthandCoverage[property] ?? []).some((shorthand) => properties.has(shorthand)))
    && frozen.declarations.importantProperties.every((property) => important.has(property));
}

function sourceRows(path) {
  return parseCss(path, readFileSync(join(ROOT, path), "utf8"), null);
}

function walkCss(root) {
  if (!existsSync(root)) return [];
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = join(root, entry.name);
    if (entry.isDirectory()) return walkCss(path);
    return entry.isFile() && path.endsWith(".css") ? [path] : [];
  });
}

function assertSourceOwners() {
  const legacyRows = FIXTURE.legacySources.flatMap(({ path }) => sourceRows(path));
  const ownerRowsByPath = new Map(OWNER_PATHS.map((path) => [path, sourceRows(path)]));
  const legacyIdentities = new Set(legacyRows.map(identity));
  for (const target of TARGET_ROWS) {
    const owner = OWNER_BY_ID.get(target.id);
    assert.ok(owner, `${target.id}: owner missing`);
    assert.equal(legacyIdentities.has(identity(target)), false, `${target.id}: identity remains in legacy CSS`);
    assert.equal(ownerRowsByPath.get(owner).filter((row) => identity(row) === identity(target)).length, 1,
      `${target.id}: identity is not exactly once in ${owner}`);
    assert.equal([...ownerRowsByPath.entries()]
      .filter(([path]) => path !== owner)
      .some(([, rows]) => rows.some((row) => identity(row) === identity(target))), false,
    `${target.id}: identity leaked to another M4 owner`);
  }
  console.log(`PASS M4 source ownership: ${TARGET_ROWS.length} identities in ${OWNER_PATHS.length} truthful owner files`);
}

function assertBundle(root, label, required) {
  assert.ok(existsSync(root), `${label}: bundle root ${root} is absent`);
  const files = walkCss(root);
  assert.ok(files.length, `${label}: no emitted CSS assets`);
  const rows = files.flatMap((path) => parseCss(relative(ROOT, path), readFileSync(path, "utf8"), null));
  const targets = TARGET_ROWS.filter((target) => required(target));
  for (const target of targets) {
    assert.equal(rows.some((row) => bundleMatch(target, row)), true, `${label}: ${target.id} absent from emitted CSS`);
  }
  console.log(`PASS ${label}: ${targets.length}/${TARGET_ROWS.length} required M4 rows emitted across ${files.length} CSS assets`);
}

assertSourceOwners();
const productRoot = resolve(process.argv[2] ?? join(ROOT, "apps/web/dist"));
const storybookRoot = resolve(process.argv[3] ?? join(ROOT, "apps/web/storybook-static"));
assertBundle(productRoot, "Product bundle", () => true);
assertBundle(storybookRoot, "Storybook bundle", (target) => SHARED_STORYBOOK_OWNERS.has(OWNER_BY_ID.get(target.id)));

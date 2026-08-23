import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { basename, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const FIXTURE = JSON.parse(readFileSync(
  join(ROOT, "scripts/fixtures/issue-261-m1e5-producer-routed-residual.json"),
  "utf8",
));
const FROZEN_INVENTORY = JSON.parse(execFileSync(
  "git",
  ["show", `${FIXTURE.baseSha}:${FIXTURE.frozenInventory.path}`],
  { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
));
const APPROVED_IDS = new Set(FIXTURE.approvedIds);
const TARGET_ROWS = FROZEN_INVENTORY.selectors.filter((row) => APPROVED_IDS.has(row.id));
const TARGET_BY_ID = new Map(TARGET_ROWS.map((row) => [row.id, row]));
const OWNER_BY_ID = new Map(
  Object.values(FIXTURE.owners)
    .flatMap((owner) => owner.ids.filter((id) => APPROVED_IDS.has(id)).map((id) => [id, owner.path])),
);
const OWNER_PATHS = [...new Set(OWNER_BY_ID.values())];
const HOLD_SELECTORS = new Set([".hyperelastic-response-plot .chart-axis", ".hyperelastic-response-plot .chart-tick"]);
// Storybook's registered stories do not mount the lazy Materials curve chart or
// canonical Test JSON route. Their feature CSS is therefore absent from the
// Storybook bundle by design; Product remains the authoritative reachability
// check for every owner while eager shared/governed/mapping owners are checked
// below.
const STORYBOOK_NON_REACHABLE_OWNER_PATHS = new Set([
  "apps/web/src/features/materials/ui/curve-contract-chart.css",
  "apps/web/src/features/test-data/ui/canonical-test-data-workbench.css",
]);

function normalizeSpace(value) {
  return value.replace(/\s+/g, " ").trim();
}

function normalizeSelector(value) {
  // Production minifiers remove insignificant whitespace around combinators;
  // retain descendant spacing while comparing the emitted selector identity.
  return normalizeSpace(value)
    .replace(/\s*([>+~])\s*/g, "$1")
    // CSSOM/minifier output may serialize legacy pseudo-element spelling with
    // one colon while source inventory records the canonical double-colon form.
    .replace(/::(before|after|first-line|first-letter|selection|backdrop|placeholder|marker|file-selector-button)/g, ":$1");
}

function normalizeAtContext(values) {
  return values.map((value) => normalizeSpace(value)
    .replace(/\(max-width\s*:\s*([^)]*)\)/g, "(width<=$1)")
    .replace(/\(min-width\s*:\s*([^)]*)\)/g, "(width>=$1)")
    .replace(/\(max-height\s*:\s*([^)]*)\)/g, "(height<=$1)")
    .replace(/\(min-height\s*:\s*([^)]*)\)/g, "(height>=$1)"));
}

function declarationSignature(declarations) {
  const canonical = declarations.map(({ property, value, important }) => [property, value, important]);
  return createHash("sha256").update(JSON.stringify(canonical)).digest("hex");
}

function identity(row) {
  return [normalizeSpace(row.selector), (row.source?.atContext ?? row.atContext ?? []).join(" | "),
    row.declarations?.signatureSha256 ?? declarationSignature(row.declarations)].join("\0");
}

function bundleMatch(frozen, emitted) {
  if (normalizeSelector(frozen.selector) !== normalizeSelector(emitted.selector)) return false;
  if (normalizeAtContext(frozen.source.atContext ?? []).join(" | ") !== normalizeAtContext(emitted.atContext ?? []).join(" | ")) return false;
  const properties = new Set(emitted.declarations.map(({ property }) => property));
  const important = new Set(emitted.declarations.filter(({ important: isImportant }) => isImportant).map(({ property }) => property));
  return frozen.declarations.properties.every((property) => properties.has(property))
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
  const ownerRows = OWNER_PATHS.flatMap((path) => sourceRows(path));
  const legacyIdentities = new Set(legacyRows.map(identity));
  const ownerIdentities = new Map();
  for (const row of ownerRows) ownerIdentities.set(identity(row), (ownerIdentities.get(identity(row)) ?? 0) + 1);

  for (const target of TARGET_ROWS) {
    assert.equal(legacyIdentities.has(identity(target)), false, `${target.id}: moved identity remains in legacy CSS`);
    assert.equal(ownerIdentities.get(identity(target)) ?? 0, 1, `${target.id}: owner identity is not exactly once`);
    const owner = OWNER_BY_ID.get(target.id);
    assert.ok(owner, `${target.id}: truthful owner missing`);
    const ownerRowsForPath = sourceRows(owner);
    assert.ok(ownerRowsForPath.some((row) => identity(row) === identity(target)), `${target.id}: wrong owner file`);
  }
  const holdRows = legacyRows.filter((row) => HOLD_SELECTORS.has(row.selector));
  assert.equal(holdRows.length, 2, "both producer-routed hold selectors must remain in legacy CSS");
  assert.equal(ownerRows.some((row) => HOLD_SELECTORS.has(row.selector)), false, "hold selectors leaked into owner CSS");
  console.log(`PASS source ownership: ${TARGET_ROWS.length} moved identities, ${holdRows.length} retained hold identities`);
}

function assertOptionalBundle(root, label, { allowMissingOwnerPaths = new Set() } = {}) {
  if (!existsSync(root)) {
    console.log(`SKIP ${label}: bundle root ${root} is absent; Main build evidence is pending`);
    return;
  }
  const files = walkCss(root);
  assert.ok(files.length, `${label}: no CSS files under ${root}`);
  const rows = files.flatMap((path) => parseCss(relative(ROOT, path), readFileSync(path, "utf8"), null));
  const skipped = [];
  for (const target of TARGET_ROWS) {
    if (allowMissingOwnerPaths.has(OWNER_BY_ID.get(target.id))) {
      skipped.push(target.id);
      continue;
    }
    assert.equal(rows.some((row) => bundleMatch(target, row)), true, `${label}: ${target.id} absent from emitted CSS`);
  }
  for (const selector of HOLD_SELECTORS) {
    assert.equal(rows.filter((row) => row.selector === selector).length, 1,
      `${label}: ${selector} must be emitted exactly once in the global producer set`);
  }
  const suffix = skipped.length ? `; ${skipped.length} feature rows are non-reachable in this story set` : "";
  console.log(`PASS ${label}: ${files.length} CSS assets preserve the M1E5 source identity set${suffix}`);
}

assertSourceOwners();
const productRoot = resolve(process.argv[2] ?? join(ROOT, "apps/web/dist"));
const storybookRoot = resolve(process.argv[3] ?? join(ROOT, "apps/web/storybook-static"));
assertOptionalBundle(productRoot, "Product bundle");
assertOptionalBundle(storybookRoot, "Storybook bundle", {
  allowMissingOwnerPaths: STORYBOOK_NON_REACHABLE_OWNER_PATHS,
});

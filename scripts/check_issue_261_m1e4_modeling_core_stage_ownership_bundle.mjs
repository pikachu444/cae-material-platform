import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { basename, dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const FIXTURE = JSON.parse(readFileSync(
  join(ROOT, "scripts/fixtures/issue-261-m1e4-modeling-core-stage-ownership.json"),
  "utf8",
));
const INVENTORY = JSON.parse(execFileSync(
  "git",
  ["show", `${FIXTURE.baseSha}:${FIXTURE.frozenInventory.path}`],
  { cwd: ROOT, encoding: "utf8", maxBuffer: 128 * 1024 * 1024 },
));

function expandRanges(ranges) {
  return ranges.flatMap((range) => {
    const [startText, endText] = range.split("..");
    const start = Number(startText.slice(4));
    const end = endText ? Number(endText) : start;
    return Array.from({ length: end - start + 1 }, (_, index) => `CSS-${String(start + index).padStart(4, "0")}`);
  });
}

function normalizeSpace(value) {
  return value.replace(/\s+/g, " ").trim();
}

// Rollup/esbuild canonicalize selector punctuation (and may emit :before for ::before).
function canonicalSelector(value) {
  return normalizeSpace(value)
    .replace(/::/g, ":")
    .replace(/\s*([>+~])\s*/g, "$1")
    .replace(/\s*,\s*/g, ",")
    .replace(/\[\s*([\w-]+)\s*=\s*(["'])([^"']*)\2\s*\]/g, "[$1=$3]")
    .replace(/\s*:\s*/g, ":");
}

// CSS minifiers commonly spell max/min-width as width<=/width>= and remove spaces.
function canonicalAtContext(value) {
  return normalizeSpace(value)
    .replace(/\(\s*max-width\s*:\s*/gi, "(width<=")
    .replace(/\(\s*min-width\s*:\s*/gi, "(width>=")
    .replace(/\s*:\s*/g, ":")
    .replace(/\s+/g, "")
    .toLowerCase();
}

function canonicalValue(value) {
  return normalizeSpace(value)
    .replace(/\s*([,:()/])\s*/g, "$1")
    .replace(/\b0+(?:\.0+)?px\b/g, "0")
    .toLowerCase();
}

function propertySet(row) {
  const properties = row.declarations?.properties ?? row.declarations.map(({ property }) => property);
  const result = new Set(properties);
  // Minifiers may replace equivalent longhands with a shorthand.
  if (result.has("grid-area")) {
    result.add("grid-column");
    result.add("grid-row");
  }
  if (result.has("overflow")) {
    result.add("overflow-x");
    result.add("overflow-y");
  }
  return result;
}

function importantPropertySet(row) {
  return new Set(row.declarations?.importantProperties ?? row.declarations
    .filter(({ important }) => important)
    .map(({ property }) => property));
}

function walkCss(directory) {
  if (!existsSync(directory)) return [];
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return walkCss(path);
    return entry.isFile() && extname(entry.name) === ".css" ? [path] : [];
  });
}

function readBaseSource(path) {
  return execFileSync("git", ["show", `${FIXTURE.baseSha}:${path}`], {
    cwd: ROOT,
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
  });
}

const BASE_ROWS = [
  "apps/web/src/styles.css",
  "apps/web/src/design/layout.css",
].flatMap((path) => parseCss(path, readBaseSource(path), null));
const BASE_ROW_BY_SOURCE = new Map(BASE_ROWS.map((row) => [
  `${row.path}#${row.ruleIndex}#${row.selectorIndex}`,
  row,
]));

function frozenSourceRow(frozen) {
  return BASE_ROW_BY_SOURCE.get(`${frozen.source.path}#${frozen.source.ruleIndex}#${frozen.source.selectorIndex}`);
}

function directIdentityMatches(frozen, emitted) {
  return canonicalSelector(emitted.selector) === canonicalSelector(frozen.selector)
    && (emitted.atContext ?? []).map(canonicalAtContext).join("|")
      === (frozen.source.atContext ?? []).map(canonicalAtContext).join("|")
    && [...new Set(frozen.declarations.properties)].every((property) => propertySet(emitted).has(property))
    && [...new Set(frozen.declarations.importantProperties)].every((property) => importantPropertySet(emitted).has(property));
}

// Values are a preference, not the emitted identity: minifiers can fold colors,
// shorthands, and redundant declarations. The frozen source still supplies the
// authoritative values/signature for this preference.
function valueMatches(frozen, emitted) {
  const source = frozenSourceRow(frozen);
  if (!source) return false;
  const emittedValues = new Map(emitted.declarations.map(({ property, value }) => [property, canonicalValue(value)]));
  for (const declaration of source.declarations) {
    if (["grid-column", "grid-row", "overflow-x", "overflow-y"].includes(declaration.property)) continue;
    if (emittedValues.get(declaration.property) !== canonicalValue(declaration.value)) return false;
  }
  return true;
}

function ownerRole(root, path) {
  const file = basename(path).toLowerCase();
  if (file.includes("engineering-curve-plot")) return "plot";
  if (file.includes("material-modeling-workspace") || file.includes("modeling-core-workbench")) return "core";
  if (root.toLowerCase().includes("storybook") && (file.includes("iframe") || file.includes("governed-workflow"))) return "consolidated";
  return "other";
}

function isAllowedOwnerChunk(root, role, path) {
  const chunkRole = ownerRole(root, path);
  return chunkRole === role || (root.toLowerCase().includes("storybook") && chunkRole === "consolidated");
}

function assertBundle(root, label) {
  const files = walkCss(root);
  assert.ok(files.length > 0, `${label}: no emitted CSS files under ${root}`);
  const rows = files.flatMap((path) => parseCss(relative(ROOT, path), readFileSync(path, "utf8"), null)
    .map((row) => ({ ...row, emittedFile: path })));
  const targets = INVENTORY.selectors.filter((row) => TARGET_IDS.has(row.id));
  const deferred = INVENTORY.selectors.filter((row) => DEFERRED_IDS.has(row.id));
  const matchesFor = (frozen) => {
    const all = rows.filter((row) => directIdentityMatches(frozen, row));
    const valuePreferred = all.filter((row) => valueMatches(frozen, row));
    return { all, selected: valuePreferred.length ? valuePreferred : all };
  };

  const targetMatches = new Map();
  for (const frozen of targets) {
    const found = matchesFor(frozen);
    assert.ok(found.all.length > 0, `${label}: ${frozen.id} emitted selector/property identity missing`);
    const expectedRole = PLOT_IDS.has(frozen.id) ? "plot" : "core";
    assert.ok(found.all.every((row) => isAllowedOwnerChunk(root, expectedRole, row.emittedFile)),
      `${label}: ${frozen.id} crossed its ${expectedRole} consumer-chunk partition`);
    assert.ok(found.selected.some((row) => isAllowedOwnerChunk(root, expectedRole, row.emittedFile)),
      `${label}: ${frozen.id} has no selected ${expectedRole} consumer chunk`);
    targetMatches.set(frozen.id, found);
  }

  const deferredMatches = new Map();
  for (const frozen of deferred) {
    const found = matchesFor(frozen);
    assert.ok(found.all.length > 0, `${label}: deferred ${frozen.id} is absent from the emitted CSS set`);
    assert.equal(found.selected.length, 1, `${label}: deferred ${frozen.id} must remain exactly once after value/signature preference`);
    assert.ok(found.all.every((row) => ownerRole(root, row.emittedFile) === "other" || ownerRole(root, row.emittedFile) === "consolidated"),
      `${label}: deferred ${frozen.id} leaked into an isolated core/plot owner chunk`);
    deferredMatches.set(frozen.id, found.selected[0]);
  }
  assert.equal(deferredMatches.size, deferred.length, `${label}: deferred total mismatch`);

  // CSS minification can merge adjacent source rules with one selector. Check
  // monotonic order at the emitted selector/context-group level, retaining all
  // source rows in the group while ignoring duplicate emitted effects.
  for (const role of ["core", "plot"]) {
    const byFile = new Map();
    for (const frozen of targets.filter((row) => (PLOT_IDS.has(row.id) ? "plot" : "core") === role)) {
      const found = targetMatches.get(frozen.id);
      for (const emitted of found.selected) {
        if (!isAllowedOwnerChunk(root, role, emitted.emittedFile)) continue;
        if (!byFile.has(emitted.emittedFile)) byFile.set(emitted.emittedFile, new Map());
        const groups = byFile.get(emitted.emittedFile);
        const key = `${canonicalSelector(frozen.selector)}\0${(frozen.source.atContext ?? []).map(canonicalAtContext).join("|")}`;
        const group = groups.get(key) ?? {
          first: frozen,
          positions: new Set(),
        };
        group.positions.add(emitted.ruleIndex);
        if (compareSourceOrder(frozen, group.first) < 0) group.first = frozen;
        groups.set(key, group);
      }
    }
    for (const [path, groups] of byFile) {
      const ordered = [...groups.values()].sort((left, right) => compareSourceOrder(left.first, right.first));
      let previous = -1;
      for (const group of ordered) {
        const current = Math.min(...group.positions);
        assert.ok(current >= previous, `${label}: ${role} target selector order regressed in ${basename(path)} (${previous} > ${current})`);
        previous = current;
      }
    }
  }

  const targetFiles = new Set([...targetMatches.values()].flatMap(({ selected }) => selected.map((row) => basename(row.emittedFile))));
  const deferredFiles = new Set([...deferredMatches.values()].map((row) => basename(row.emittedFile)));
  console.log(`${label}: PASS (${targets.length} target identities partitioned into core/plot chunks, ${deferred.length} deferred identities exactly once, ${files.length} CSS assets; target files=${[...targetFiles].sort().join(",")}; deferred files=${[...deferredFiles].sort().join(",")})`);
}

function compareSourceOrder(left, right) {
  return left.source.mainImportRank - right.source.mainImportRank
    || left.source.ruleIndex - right.source.ruleIndex
    || left.source.selectorIndex - right.source.selectorIndex;
}

const TARGET_IDS = new Set(expandRanges(FIXTURE.targetIdRanges));
const PLOT_IDS = new Set(expandRanges(FIXTURE.plotIdRanges));
const DEFERRED_IDS = new Set(expandRanges(FIXTURE.deferredIdRanges));
const productRoot = resolve(process.argv[2] ?? join(ROOT, "apps/web/dist"));
const storybookRoot = resolve(process.argv[3] ?? join(ROOT, "apps/web/storybook-static"));
assertBundle(productRoot, "Product bundle");
assertBundle(storybookRoot, "Storybook bundle");

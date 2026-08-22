import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import {
  basename,
  dirname,
  extname,
  join,
  relative,
  resolve,
} from "node:path";
import { fileURLToPath } from "node:url";

import { parseCss } from "./check_issue_261_css_inventory.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const FIXTURE = JSON.parse(readFileSync(
  join(ROOT, "scripts/fixtures/issue-261-m1e3-modeling-family-ownership.json"),
  "utf8",
));
const FROZEN_INVENTORY = JSON.parse(execFileSync(
  "git",
  ["show", FIXTURE.baseSha + ":" + FIXTURE.frozenInventory.path],
  { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
));

const TARGET_IDS = new Set(FIXTURE.moves.flatMap((move) => move.ids));
const TARGET_ROWS = FROZEN_INVENTORY.selectors.filter((row) => TARGET_IDS.has(row.id));
const TARGET_BY_ID = new Map(TARGET_ROWS.map((row) => [row.id, row]));
assert.equal(
  TARGET_ROWS.length,
  FIXTURE.aggregate.targetRows,
  "frozen M1E3 target roster count drift",
);

function normalizeNumeric(value) {
  return String(value)
    .replace(/(^|[^\w.])(-?)0+\.0+(?=$|[^0-9])/g, (_match, prefix, sign) => prefix + sign + "0")
    .replace(/(^|[^\w.])(-?)0+\.(\d+)/g, "$1$2.$3")
    .replace(/(^|[^\w.])(-?\d+\.\d*?[1-9])0+(?=$|[^0-9])/g, "$1$2");
}

function normalizeSelector(value) {
  return String(value)
    .replace(/\s*([>+~,:])\s*/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeAtContext(value) {
  return (value ?? []).map((entry) => {
    let normalized = String(entry)
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
    normalized = normalized.replace(
      /\(\s*(max|min)-([a-z-]+)\s*:\s*([^)]+)\)/g,
      (_match, direction, feature, dimension) => (
        "(" + feature + (direction === "max" ? "<=" : ">=")
        + normalizeNumeric(dimension.trim()) + ")"
      ),
    );
    normalized = normalized.replace(
      /\(\s*([a-z-]+)\s*([<>]=)\s*([^)]+)\)/g,
      (_match, feature, operator, dimension) => (
        "(" + feature + operator + normalizeNumeric(dimension.trim()) + ")"
      ),
    );
    return normalized
      .replace(/\s*([,:])\s*/g, "$1")
      .replace(/\s*([<>]=)\s*/g, "$1")
      .replace(/\s+/g, " ")
      .trim();
  });
}

function selectorContextKey(selector, atContext) {
  return JSON.stringify([normalizeSelector(selector), normalizeAtContext(atContext)]);
}

function declarationSignature(declarations) {
  return createHash("sha256")
    .update(JSON.stringify(declarations.map(({ property, value, important }) => [property, value, important])))
    .digest("hex");
}

function channelByte(value) {
  const text = String(value).trim();
  const parsed = text.endsWith("%")
    ? Number.parseFloat(text.slice(0, -1)) * 255 / 100
    : Number.parseFloat(text);
  if (!Number.isFinite(parsed)) return null;
  return Math.max(0, Math.min(255, Math.round(parsed)));
}

function alphaByte(value) {
  const text = String(value).trim();
  const parsed = text.endsWith("%")
    ? Number.parseFloat(text.slice(0, -1)) * 255 / 100
    : Number.parseFloat(text) * 255;
  if (!Number.isFinite(parsed)) return null;
  return Math.max(0, Math.min(255, Math.round(parsed)));
}

function byteHex(value) {
  return value.toString(16).padStart(2, "0");
}

function normalizeColorFunction(match) {
  const open = match.indexOf("(");
  const inner = match.slice(open + 1, -1).trim();
  let channels;
  let alpha;
  if (inner.includes(",")) {
    const parts = inner.split(/\s*,\s*/);
    channels = parts.slice(0, 3);
    alpha = parts[3];
  } else {
    const parts = inner.split(/\s+/);
    const slash = parts.indexOf("/");
    channels = slash < 0 ? parts : parts.slice(0, slash);
    alpha = slash < 0 ? undefined : parts[slash + 1];
  }
  if (!channels || channels.length !== 3) return match;
  const rgb = channels.map(channelByte);
  const alphaChannel = alpha === undefined ? 255 : alphaByte(alpha);
  if (rgb.some((channel) => channel === null) || alphaChannel === null) return match;
  const suffix = alphaChannel < 255 ? byteHex(alphaChannel) : "";
  return "#" + rgb.map(byteHex).join("") + suffix;
}

function normalizeColorTokens(value) {
  return String(value)
    .replace(/rgba?\([^()]*\)/gi, normalizeColorFunction)
    .replace(/#([0-9a-f]{3,8})\b/gi, (_match, raw) => {
      const hex = raw.toLowerCase();
      if (hex.length === 3 || hex.length === 4) {
        return "#" + hex.split("").map((character) => character + character).join("");
      }
      return "#" + hex;
    })
    .replace(/\btransparent\b/gi, "#00000000");
}

function normalizeValue(property, value) {
  let normalized = String(value)
    .trim()
    .replace(/\s+/g, " ");
  normalized = normalizeNumeric(normalized)
    .replace(/\s*,\s*/g, ",")
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")");
  normalized = normalizeColorTokens(normalized)
    .replace(/\s*\/\s*/g, "/")
    .replace(/calc\(([^()]*)\)/gi, "$1")
    .replace(/linear-gradient\(180deg,/gi, "linear-gradient(");
  if (property === "stroke-width" && /^-?\d*\.?\d+$/.test(normalized)) {
    normalized += "px";
  }
  if (property === "background" && normalized === "0 0") normalized = "#00000000";
  return normalized;
}

function normalizeDeclaration(declaration) {
  const property = String(declaration.property).trim().toLowerCase();
  return {
    property,
    value: normalizeValue(property, declaration.value),
    important: Boolean(declaration.important),
  };
}

function normalizedDeclarations(declarations) {
  return declarations.map(normalizeDeclaration);
}

function effectiveMap(declarations) {
  const map = new Map();
  for (const declaration of normalizedDeclarations(declarations)) {
    const previous = map.get(declaration.property);
    if (
      !previous
      || previous.important === declaration.important
      || declaration.important
    ) {
      map.set(declaration.property, declaration);
    }
  }
  return map;
}

function mapEquivalent(leftDeclarations, rightDeclarations) {
  const left = effectiveMap(leftDeclarations);
  const right = effectiveMap(rightDeclarations);
  if (left.size !== right.size) return false;
  for (const [property, declaration] of left) {
    const candidate = right.get(property);
    if (!candidate || candidate.value !== declaration.value || candidate.important !== declaration.important) {
      return false;
    }
  }
  return true;
}

function propertyCounts(declarations) {
  const counts = new Map();
  for (const declaration of normalizedDeclarations(declarations)) {
    counts.set(declaration.property, (counts.get(declaration.property) ?? 0) + 1);
  }
  return counts;
}

function occurrenceValues(declarations, property) {
  return normalizedDeclarations(declarations)
    .filter((declaration) => declaration.property === property)
    .map((declaration) => declaration.value + "\0" + (declaration.important ? "!" : ""));
}

function combinedContributionMatches(expectedRows, emittedRow) {
  const expectedDeclarations = expectedRows.flatMap((row) => row.declarations);
  const emittedDeclarations = emittedRow.declarations;
  const expectedNormalized = normalizedDeclarations(expectedDeclarations);
  const emittedNormalized = normalizedDeclarations(emittedDeclarations);
  if (expectedNormalized.length !== emittedNormalized.length) return false;
  if (!mapEquivalent(expectedDeclarations, emittedDeclarations)) return false;

  const expectedCounts = propertyCounts(expectedDeclarations);
  const emittedCounts = propertyCounts(emittedDeclarations);
  if (expectedCounts.size !== emittedCounts.size) return false;
  for (const [property, count] of expectedCounts) {
    if (emittedCounts.get(property) !== count) return false;
    if (count > 1 && JSON.stringify(occurrenceValues(expectedDeclarations, property))
      !== JSON.stringify(occurrenceValues(emittedDeclarations, property))) {
      return false;
    }
  }
  return true;
}

function matchGroup(expectedRows, emittedRows) {
  if (!expectedRows.length || !emittedRows.length) return null;
  const icon = expectedRows.some((row) => row.id === "CSS-0876");
  if (icon) {
    if (expectedRows.length !== 1 || emittedRows.length !== 1) return null;
    if (!mapEquivalent(expectedRows[0].declarations, emittedRows[0].declarations)) return null;
    const expectedProperties = effectiveMap(expectedRows[0].declarations).keys();
    const emittedCounts = propertyCounts(emittedRows[0].declarations);
    for (const property of expectedProperties) {
      if ((emittedCounts.get(property) ?? 0) !== 1) return null;
    }
    return { segments: [[expectedRows[0].id]] };
  }

  if (expectedRows.length === emittedRows.length) {
    const direct = expectedRows.every((expected, index) => (
      combinedContributionMatches([expected], emittedRows[index])
    ));
    if (direct) return { segments: expectedRows.map((row) => [row.id]) };

    const used = new Set();
    const assignment = [];
    function assign(index) {
      if (index === expectedRows.length) return true;
      for (let emittedIndex = 0; emittedIndex < emittedRows.length; emittedIndex += 1) {
        if (used.has(emittedIndex)) continue;
        if (!combinedContributionMatches([expectedRows[index]], emittedRows[emittedIndex])) continue;
        used.add(emittedIndex);
        assignment[index] = emittedIndex;
        if (assign(index + 1)) return true;
        used.delete(emittedIndex);
      }
      return false;
    }
    if (assign(0)) {
      return {
        segments: assignment.map((emittedIndex, index) => [expectedRows[index].id, emittedIndex]),
      };
    }
    return null;
  }

  if (expectedRows.length < emittedRows.length) return null;
  const segments = [];
  function partition(expectedIndex, emittedIndex) {
    if (emittedIndex === emittedRows.length) return expectedIndex === expectedRows.length;
    const remainingEmitted = emittedRows.length - emittedIndex - 1;
    const lastExpected = expectedRows.length - remainingEmitted;
    for (let end = expectedIndex + 1; end <= lastExpected; end += 1) {
      const group = expectedRows.slice(expectedIndex, end);
      if (!combinedContributionMatches(group, emittedRows[emittedIndex])) continue;
      segments.push(group.map((row) => row.id));
      if (partition(end, emittedIndex + 1)) return true;
      segments.pop();
    }
    return false;
  }
  return partition(0, 0) ? { segments: [...segments] } : null;
}

function walkFiles(directory, extension) {
  if (!existsSync(directory)) return [];
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return walkFiles(path, extension);
    return entry.isFile() && extname(entry.name) === extension ? [path] : [];
  });
}

function walkCss(directory) {
  return walkFiles(directory, ".css");
}

function relativePath(path) {
  return relative(ROOT, path).replaceAll("\\", "/");
}

function buildExpectedMoves() {
  return FIXTURE.moves.map((move) => {
    const ownerRows = parseCss(move.target, readFileSync(resolve(ROOT, move.target), "utf8"), null);
    const rows = move.ids.map((id) => {
      const frozen = TARGET_BY_ID.get(id);
      assert.ok(frozen, id + ": frozen target row missing");
      let candidates = ownerRows.filter((row) => (
        selectorContextKey(row.selector, row.atContext)
        === selectorContextKey(frozen.selector, frozen.source.atContext)
        && declarationSignature(row.declarations) === frozen.declarations.signatureSha256
      ));
      if (id === "CSS-0876") {
        candidates = ownerRows.filter((row) => normalizeSelector(row.selector) === ".icon-button");
      }
      assert.equal(candidates.length, 1, move.target + ": " + id + " owner source identity count");
      return {
        id,
        selector: candidates[0].selector,
        atContext: candidates[0].atContext,
        declarations: candidates[0].declarations,
        ruleIndex: candidates[0].ruleIndex,
        selectorIndex: candidates[0].selectorIndex,
      };
    }).sort((left, right) => (
      left.ruleIndex - right.ruleIndex || left.selectorIndex - right.selectorIndex
    ));

    const groups = new Map();
    for (const row of rows) {
      const key = selectorContextKey(row.selector, row.atContext);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    }
    const orderedGroups = [...groups.entries()]
      .map(([key, group]) => ({ key, rows: group }))
      .sort((left, right) => (
        left.rows[0].ruleIndex - right.rows[0].ruleIndex
        || left.rows[0].selectorIndex - right.rows[0].selectorIndex
      ));
    return { move, rows, groups: orderedGroups };
  });
}

const EXPECTED_MOVES = buildExpectedMoves();

function rowsByKey(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = selectorContextKey(row.selector, row.atContext);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  return groups;
}

function evaluateMove(assetRows, expectedMove) {
  const emittedGroups = rowsByKey(assetRows);
  const matchedGroups = [];
  const matchedIds = [];
  for (const expectedGroup of expectedMove.groups) {
    const emittedRows = emittedGroups.get(expectedGroup.key) ?? [];
    const match = matchGroup(expectedGroup.rows, emittedRows);
    if (!match) continue;
    matchedGroups.push(expectedGroup.key);
    matchedIds.push(...expectedGroup.rows.map((row) => row.id));
  }
  return {
    matchedGroups,
    matchedIds,
    allGroups: matchedGroups.length === expectedMove.groups.length,
  };
}

function collectReferences(bundleRoot) {
  const files = [...walkFiles(bundleRoot, ".js"), ...walkFiles(bundleRoot, ".html")];
  const cssFiles = walkCss(bundleRoot);
  const references = new Map();
  for (const path of files) {
    const source = readFileSync(path, "utf8");
    for (const cssPath of cssFiles) {
      const name = basename(cssPath);
      if (source.includes(name)) {
        if (!references.has(name)) references.set(name, []);
        references.get(name).push(path);
      }
    }
  }
  return references;
}

function assertOwnerTopology(bundleRoot, label, ownerPath, references) {
  const ownerName = basename(ownerPath);
  const referencedBy = references.get(ownerName) ?? [];
  assert.ok(referencedBy.length > 0, label + ": " + ownerName + " is not referenced by the emitted JS/HTML graph");

  if (label === "production") {
    const lazyJs = walkFiles(bundleRoot, ".js")
      .filter((path) => /^material-modeling-workspace-.*\.js$/.test(basename(path)));
    assert.equal(lazyJs.length, 1, label + ": lazy Modeling workspace JS chunk missing or duplicated");
    assert.ok(
      referencedBy.some((path) => path === lazyJs[0]),
      label + ": " + ownerName + " is not attached to the lazy Modeling workspace chunk",
    );
  } else {
    const storybookFrameJs = walkFiles(bundleRoot, ".js")
      .filter((path) => /^iframe-.*\.js$/.test(basename(path)));
    assert.ok(
      referencedBy.some((path) => storybookFrameJs.includes(path)),
      label + ": " + ownerName + " is not attached to the Storybook iframe graph",
    );
  }
}

function expectedOwnerPrefix(move, label) {
  if (move === FIXTURE.moves[0]) return "engineering-curve-plot-";
  if (move === FIXTURE.moves[2]) {
    return label === "production" ? "common-processing-workbench-" : "governed-workflow-";
  }
  return basename(move.target, ".css") + "-";
}

function checkBundle(rootArg, label) {
  const bundleRoot = resolve(ROOT, rootArg);
  const files = walkCss(bundleRoot);
  assert.ok(files.length, label + ": no CSS assets under " + rootArg);
  const assets = files.map((path) => ({
    path,
    name: basename(path),
    rows: parseCss(relativePath(path), readFileSync(path, "utf8"), null),
  }));
  const references = collectReferences(bundleRoot);
  const moveResults = [];

  for (const expectedMove of EXPECTED_MOVES) {
    const evaluations = assets.map((asset) => ({
      asset,
      evaluation: evaluateMove(asset.rows, expectedMove),
    }));
    const expectedIds = new Set(expectedMove.rows.map((row) => row.id));
    const matchingByGroup = expectedMove.groups.map((group) => ({
      key: group.key,
      ids: group.rows.map((row) => row.id),
      assets: evaluations
        .filter(({ asset }) => evaluateMove(asset.rows, { groups: [group] }).allGroups)
        .map(({ asset }) => asset),
    }));
    const coveredIds = new Set(matchingByGroup.flatMap((group) => (
      group.assets.length === 1 ? group.ids : []
    )));
    if (label === "production") {
      assert.equal(
        coveredIds.size,
        expectedIds.size,
        label + ": " + expectedMove.move.name + " target selector/property coverage is incomplete",
      );
    } else if (coveredIds.size > 0 && coveredIds.size !== expectedIds.size) {
      assert.fail(
        label + ": " + expectedMove.move.name + " is partially emitted ("
        + coveredIds.size + "/" + expectedIds.size + " target contributions)",
      );
    }

    for (const group of matchingByGroup) {
      if (label === "production" || coveredIds.size > 0) {
        assert.equal(
          group.assets.length,
          1,
          label + ": " + expectedMove.move.name + " " + group.ids.join(",")
          + " owner contribution must emit in exactly one CSS asset",
        );
      } else {
        assert.equal(
          group.assets.length,
          0,
          label + ": " + expectedMove.move.name + " absent Storybook family unexpectedly emitted",
        );
      }
    }

    const fullCandidates = evaluations
      .filter(({ evaluation }) => evaluation.allGroups)
      .map(({ asset }) => asset);
    if (label === "storybook" && coveredIds.size === 0) {
      moveResults.push({
        name: expectedMove.move.name,
        skipped: true,
        reason: "family is not part of the current Storybook import graph",
        targetRows: expectedMove.rows.length,
        targetGroups: expectedMove.move.groups,
        ownerAssets: [],
        multiplicities: {},
      });
      continue;
    }

    assert.equal(
      fullCandidates.length,
      1,
      label + ": " + expectedMove.move.name + " must have one complete owner CSS asset",
    );
    const ownerAsset = fullCandidates[0];
    const prefix = expectedOwnerPrefix(expectedMove.move, label);
    assert.ok(
      ownerAsset.name.startsWith(prefix),
      label + ": " + expectedMove.move.name + " emitted owner " + ownerAsset.name
      + " does not match expected " + prefix + " asset topology",
    );
    assertOwnerTopology(bundleRoot, label, ownerAsset.path, references);

    const matchedEvaluation = evaluations.find(({ asset }) => asset.path === ownerAsset.path);
    assert.ok(matchedEvaluation?.evaluation.allGroups, label + ": selected owner asset lost a target group");
    moveResults.push({
      name: expectedMove.move.name,
      skipped: false,
      targetRows: expectedMove.rows.length,
      targetGroups: expectedMove.move.groups,
      ownerAssets: [relativePath(ownerAsset.path)],
      matchedRows: matchedEvaluation.evaluation.matchedIds.length,
      multiplicities: Object.fromEntries(expectedMove.rows.map((row) => [row.id, 1])),
    });
  }

  const iconRows = assets.flatMap((asset) => asset.rows
    .filter((row) => normalizeSelector(row.selector) === ".icon-button")
    .map((row) => ({ asset, row })));
  if (label === "production" || iconRows.length > 0) {
    assert.equal(iconRows.length, 1, label + ": normalized icon-button must emit once");
    const iconExpected = EXPECTED_MOVES.find((move) => move.move.ids.includes("CSS-0876"));
    assert.equal(
      evaluateMove(iconRows[0].asset.rows, iconExpected).matchedIds.includes("CSS-0876"),
      true,
      label + ": normalized icon-button declaration union drift",
    );
  }

  return {
    label,
    root: rootArg,
    cssAssets: files.map(relativePath),
    cssRows: assets.reduce((total, asset) => total + asset.rows.length, 0),
    movedRows: TARGET_ROWS.length,
    moves: moveResults,
  };
}

const productRoot = process.argv[2] ?? "apps/web/dist";
const storybookRoot = process.argv[3] ?? "apps/web/storybook-static";
const production = checkBundle(productRoot, "production");
const storybook = checkBundle(storybookRoot, "storybook");
for (let index = 0; index < production.moves.length; index += 1) {
  const productionMove = production.moves[index];
  const storybookMove = storybook.moves[index];
  if (!productionMove.skipped && !storybookMove.skipped) {
    assert.deepEqual(
      storybookMove.multiplicities,
      productionMove.multiplicities,
      "storybook: " + productionMove.name + " target contribution parity drift",
    );
  }
}
console.log(JSON.stringify({ ok: true, result: [production, storybook] }, null, 2));

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const fixtureIndex = process.argv.indexOf("--fixture");
const fixturePath = fixtureIndex >= 0
  ? process.argv[fixtureIndex + 1]
  : "scripts/fixtures/issue-261-residual-owner-boundary.json";
if (!fixturePath) throw new Error("--fixture requires a repository-relative JSON path");
const FIXTURE = JSON.parse(readFileSync(resolve(ROOT, fixturePath), "utf8"));
const TARGET_IDS = new Set(FIXTURE.targetIds);
const ROW_BY_KEY = new Map(FIXTURE.targetTuples.map((tuple) => [
  `${tuple[1]}#${tuple[3]}#${tuple[4]}`,
  {
    id: tuple[0],
    path: tuple[1],
    ruleIndex: tuple[3],
    selectorIndex: tuple[4],
    selector: tuple[5],
    atContext: tuple[6],
    signature: tuple[10],
  },
]));
const OWNER_BY_ID = new Map(
  Object.values(FIXTURE.owners).flatMap((owner) => owner.ids.map((id) => [id, owner.path])),
);
const M6_TUPLES = FIXTURE.m6Handoff.tuples;

function normalizeSpace(value) { return value.replace(/\s+/g, " ").trim(); }

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
    if (character === "'" || character === '"') {
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
    if (character === "'" || character === '"') {
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
        start: tokenStart + leading,
        open: index,
        bodyStart: index + 1,
      });
      tokenStart = index + 1;
      continue;
    }
    if (character !== "}") continue;
    const entry = stack.pop();
    if (entry?.type === "rule" && entry.prelude) {
      const ruleIndex = rules.length + 1;
      splitTopLevel(entry.prelude).forEach((selector, selectorIndex) => rules.push({
        ruleIndex,
        selectorIndex: selectorIndex + 1,
        selector: normalizeSpace(selector),
        atContext: entry.atContext,
        start: entry.start,
        open: entry.open,
        close: index,
        bodyStart: entry.bodyStart,
      }));
    }
    tokenStart = index + 1;
  }
  return rules;
}

function declarationSignature(body) {
  const declarations = [];
  let start = 0;
  let quote = null;
  let round = 0;
  for (let index = 0; index <= body.length; index += 1) {
    const character = body[index] ?? ";";
    if (quote) {
      if (character === "\\") index += 1;
      else if (character === quote) quote = null;
      continue;
    }
    if (character === "'" || character === '"') quote = character;
    else if (character === "(") round += 1;
    else if (character === ")") round = Math.max(0, round - 1);
    else if (character === ";" && round === 0) {
      const declaration = body.slice(start, index).trim();
      start = index + 1;
      const colon = declaration.indexOf(":");
      if (colon < 1) continue;
      const property = declaration.slice(0, colon).trim().toLowerCase();
      const rawValue = declaration.slice(colon + 1).trim();
      const important = /\s*!important\s*$/i.test(rawValue);
      const value = normalizeSpace(rawValue.replace(/\s*!important\s*$/i, ""));
      if (!/^--[\w-]+$|^[a-z-]+$/i.test(property) || !value) continue;
      declarations.push([property, value, important]);
    }
  }
  return createHash("sha256").update(JSON.stringify(declarations)).digest("hex");
}

function eolFor(source) { return source.includes("\r\n") ? "\r\n" : "\n"; }

function formatRule(selectors, body, eol) {
  const lines = body.split(/\r?\n/);
  while (lines.length && !lines[0].trim()) lines.shift();
  while (lines.length && !lines.at(-1).trim()) lines.pop();
  const baseIndent = Math.min(...lines.filter((line) => line.trim()).map((line) => line.match(/^\s*/)?.[0].length ?? 0));
  const normalizedBody = lines
    .map((line) => `${line.trim() ? "  " : ""}${line.slice(Number.isFinite(baseIndent) ? baseIndent : 0)}`.replace(/[ \t]+$/, ""))
    .join(eol);
  return `${selectors.join(`,${eol}`)} {${eol}${normalizedBody}${eol}}`;
}

function wrapAtContext(ruleText, atContext, eol) {
  let wrapped = ruleText;
  for (let index = atContext.length - 1; index >= 0; index -= 1) {
    wrapped = `${atContext[index]} {${eol}${wrapped.split(/\r?\n/).map((line) => `  ${line}`).join(eol)}${eol}}`;
  }
  return wrapped;
}

function frozenSource(path) {
  return execFileSync("git", ["show", `${FIXTURE.baseSha}:${path}`], {
    cwd: ROOT,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
  });
}

function frozenOwnerSource(path) {
  if (path === "apps/web/src/domain-workflow-links.css") return "";
  try {
    return frozenSource(path);
  } catch {
    return "";
  }
}

function identity(row) {
  return `${normalizeSpace(row.selector)}\0${(row.atContext ?? []).join(" | ")}\0${row.signature}`;
}

function tupleIdentity(tuple) {
  return `${normalizeSpace(tuple[5])}\0${(tuple[6] ?? []).join(" | ")}\0${tuple[10]}`;
}

function sourceGroupKey(path, ruleIndex) { return `${path}#${ruleIndex}`; }

function targetBlocks(path, source) {
  const rules = scanCss(source);
  const groups = new Map();
  for (const rule of rules) {
    const key = sourceGroupKey(path, rule.ruleIndex);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(rule);
  }
  const replacements = [];
  const blocks = [];
  for (const [key, group] of groups) {
    const selected = group
      .map((rule) => ({ rule, row: ROW_BY_KEY.get(`${path}#${rule.ruleIndex}#${rule.selectorIndex}`) }))
      .filter(({ row }) => row && TARGET_IDS.has(row.id));
    if (!selected.length) continue;
    const first = group[0];
    const originalPrelude = source.slice(first.start, first.open);
    const originalSelectors = splitTopLevel(originalPrelude);
    const selectedIndexes = new Set(selected.map(({ rule }) => rule.selectorIndex));
    const selectedSelectors = originalSelectors.filter((_, index) => selectedIndexes.has(index + 1));
    const remainingSelectors = originalSelectors.filter((_, index) => !selectedIndexes.has(index + 1));
    const body = source.slice(first.bodyStart, first.close);
    const eol = eolFor(source);
    const remainingText = remainingSelectors.length ? formatRule(remainingSelectors, body, eol) : "";
    let replacementStart = first.start;
    if (!remainingSelectors.length) {
      const lineStart = Math.max(0, source.lastIndexOf("\n", first.start - 1) + 1);
      if (!source.slice(lineStart, first.start).trim()) replacementStart = lineStart;
    }
    replacements.push({ start: replacementStart, end: first.close + 1, text: remainingText });
    const selectedByOwner = new Map();
    for (const entry of selected) {
      const ownerPath = OWNER_BY_ID.get(entry.row.id);
      if (!selectedByOwner.has(ownerPath)) selectedByOwner.set(ownerPath, []);
      selectedByOwner.get(ownerPath).push(entry);
    }
    for (const [ownerPath, ownerEntries] of selectedByOwner) {
      const ownerIndexes = new Set(ownerEntries.map(({ rule }) => rule.selectorIndex));
      const ownerSelectors = originalSelectors.filter((_, index) => ownerIndexes.has(index + 1));
      blocks.push({
        ownerPath,
        sourceKey: key,
        sourceRank: ownerEntries[0].row.mainImportRank ?? 0,
        ruleIndex: first.ruleIndex,
        selectorIndex: ownerEntries[0].rule.selectorIndex,
        rowIds: ownerEntries.map(({ row }) => row.id),
        identityRows: ownerEntries.map(({ row }) => ({ selector: row.selector, atContext: row.atContext, signature: row.signature })),
        text: wrapAtContext(formatRule(ownerSelectors, body, eol), first.atContext, eol),
      });
    }
  }
  const nextSource = replacements
    .sort((left, right) => right.start - left.start)
    .reduce((value, replacement) => `${value.slice(0, replacement.start)}${replacement.text}${value.slice(replacement.end)}`, source);
  return { nextSource, blocks };
}

function ownerRows(path, source = readFileSync(resolve(ROOT, path), "utf8")) {
  return scanCss(source).map((rule) => ({
    ...rule,
    signature: declarationSignature(source.slice(rule.bodyStart, rule.close)),
  }));
}

function integrate(ownerPath, blocks) {
  const ownerFile = resolve(ROOT, ownerPath);
  mkdirSync(resolve(ownerFile, ".."), { recursive: true });
  const existing = frozenOwnerSource(ownerPath);
  const eol = eolFor(existing || "\n");
  const existingIdentities = new Set(existing ? ownerRows(ownerPath, existing).map(identity) : []);
  const fresh = blocks
    .sort((left, right) => left.sourceRank - right.sourceRank || left.ruleIndex - right.ruleIndex || left.selectorIndex - right.selectorIndex)
    .filter((block) => block.identityRows.some((row) => !existingIdentities.has(identity(row))));
  if (!fresh.length) return false;
  const base = existing.replace(/\s+$/, "");
  let additions = "";
  fresh.forEach((block) => {
    additions += `${additions ? `${eol}${eol}` : ""}/* FE-06 residual owner-boundary consolidation: ${block.sourceKey}; peers ${block.rowIds.join(", ")}. */${eol}${block.text.replace(/\r?\n/g, eol)}`;
  });
  // Both legacy sources load before feature-owner stylesheets.  Prepending
  // preserves their relative position ahead of the owner's existing rules;
  // the audited layout->early-design exceptions remain accepted in layout.css.
  writeFileSync(ownerFile, `${additions}${base ? `${eol}${eol}${base}` : ""}${eol}`, "utf8");
  return true;
}

function frozenTransformation() {
  const nextLegacyByPath = new Map();
  const blocksByOwner = new Map();
  for (const { path } of FIXTURE.legacySources) {
    const { nextSource, blocks } = targetBlocks(path, frozenSource(path));
    nextLegacyByPath.set(path, nextSource);
    for (const block of blocks) {
      if (!blocksByOwner.has(block.ownerPath)) blocksByOwner.set(block.ownerPath, []);
      blocksByOwner.get(block.ownerPath).push(block);
    }
  }
  return { nextLegacyByPath, blocksByOwner };
}

function verifyLegacyTargets() {
  const missing = [];
  for (const { path } of FIXTURE.legacySources) {
    const rows = ownerRows(path);
    const present = new Set(rows.map(identity));
    for (const tuple of FIXTURE.targetTuples.filter((item) => item[1] === path)) {
      if (present.has(tupleIdentity(tuple))) missing.push(tuple[0]);
    }
  }
  if (missing.length) throw new Error(`migrated target rows remain in legacy CSS: ${missing.join(", ")}`);
}

function verifyOwners() {
  const byPath = new Map(Object.values(FIXTURE.owners).map((owner) => [owner.path, ownerRows(owner.path)]));
  const missing = [];
  const duplicate = [];
  for (const tuple of FIXTURE.targetTuples) {
    const expected = OWNER_BY_ID.get(tuple[0]);
    const targetIdentity = tupleIdentity(tuple);
    const matches = [];
    for (const [path, rows] of byPath) {
      if (rows.some((row) => identity(row) === targetIdentity)) matches.push(path);
    }
    if (!matches.includes(expected)) missing.push(tuple[0]);
    if (matches.length !== 1) duplicate.push(`${tuple[0]}:${matches.join(",")}`);
  }
  if (missing.length || duplicate.length) {
    throw new Error(`owner proof failed; missing=${missing.join(",")}; duplicate=${duplicate.join(",")}`);
  }
}

function verifyM6Handoff() {
  const missing = [];
  for (const tuple of M6_TUPLES) {
    const source = readFileSync(resolve(ROOT, tuple[1]), "utf8");
    const rows = ownerRows(tuple[1], source);
    const count = rows.filter((row) => identity(row) === tupleIdentity(tuple)).length;
    if (count !== 1) missing.push(`${tuple[0]}:${count}`);
  }
  if (missing.length) throw new Error(`M6 handoff drifted: ${missing.join(", ")}`);
}

function verifyExactTransformation() {
  const { nextLegacyByPath, blocksByOwner } = frozenTransformation();
  const drift = [];
  for (const [path, expected] of nextLegacyByPath) {
    if (readFileSync(resolve(ROOT, path), "utf8") !== expected) drift.push(path);
  }
  for (const [ownerPath, blocks] of blocksByOwner) {
    const frozenOwner = frozenOwnerSource(ownerPath);
    const existing = readFileSync(resolve(ROOT, ownerPath), "utf8");
    const eol = eolFor(existing);
    const existingIdentities = new Set(ownerRows(ownerPath, frozenOwner).map(identity));
    const fresh = blocks
      .sort((left, right) => left.sourceRank - right.sourceRank || left.ruleIndex - right.ruleIndex || left.selectorIndex - right.selectorIndex)
      .filter((block) => block.identityRows.some((row) => !existingIdentities.has(identity(row))));
    const base = frozenOwner.replace(/\s+$/, "").replace(/\r?\n/g, eol);
    let additions = "";
    fresh.forEach((block) => {
      additions += `${additions ? `${eol}${eol}` : ""}/* FE-06 residual owner-boundary consolidation: ${block.sourceKey}; peers ${block.rowIds.join(", ")}. */${eol}${block.text.replace(/\r?\n/g, eol)}`;
    });
    const expected = fresh.length ? `${additions}${base ? `${eol}${eol}${base}` : ""}${eol}` : frozenOwner;
    if (existing !== expected) {
      const firstDifference = [...existing].findIndex((character, index) => character !== expected[index]);
      drift.push(`${ownerPath} (actual ${existing.length}, expected ${expected.length}, first ${firstDifference})`);
    }
  }
  if (drift.length) throw new Error(`exact frozen transformation drifted: ${drift.join(", ")}`);
}

function report(mode) {
  const legacyRows = FIXTURE.legacySources.flatMap(({ path }) => ({
    path,
    rows: ownerRows(path),
  }));
  const targetPresent = legacyRows.reduce((count, { path, rows }) => count + rows.filter((row) => FIXTURE.targetTuples
    .filter((tuple) => tuple[1] === path)
    .some((tuple) => identity(row) === tupleIdentity(tuple))).length, 0);
  console.log(JSON.stringify({
    mode,
    baseSha: FIXTURE.baseSha,
    targetRows: FIXTURE.targetRows.rows,
    targetGroups: FIXTURE.targetRows.groups,
    legacySelectorRowsAfter: legacyRows.reduce((count, { rows }) => count + rows.length, 0),
    targetRowsPresentAfter: targetPresent,
    m6RowsHandoff: FIXTURE.m6Handoff.rows,
    idempotent: targetPresent === 0,
  }, null, 2));
}

if (process.argv.includes("--write")) {
  for (const ownerPath of FIXTURE.touchedOwnerPaths ?? []) {
    const ownerFile = resolve(ROOT, ownerPath);
    const base = frozenOwnerSource(ownerPath);
    if (base || existsSync(ownerFile)) {
      mkdirSync(resolve(ownerFile, ".."), { recursive: true });
      writeFileSync(ownerFile, base, "utf8");
    }
  }
  const allBlocks = [];
  for (const { path } of FIXTURE.legacySources) {
    const { nextSource, blocks } = targetBlocks(path, frozenSource(path));
    writeFileSync(resolve(ROOT, path), nextSource, "utf8");
    allBlocks.push(...blocks);
  }
  const blocksByOwner = new Map();
  for (const block of allBlocks) {
    if (!blocksByOwner.has(block.ownerPath)) blocksByOwner.set(block.ownerPath, []);
    blocksByOwner.get(block.ownerPath).push(block);
  }
  for (const [ownerPath, blocks] of blocksByOwner) {
    if (integrate(ownerPath, blocks)) console.log(`WROTE ${ownerPath}: ${blocks.length} source groups`);
  }
  verifyLegacyTargets();
  verifyOwners();
  verifyM6Handoff();
  report("write");
} else if (process.argv.includes("--check")) {
  verifyLegacyTargets();
  verifyOwners();
  verifyM6Handoff();
  if (process.argv.includes("--exact")) verifyExactTransformation();
  report("check");
} else {
  console.error("Refusing to modify CSS without --write");
  process.exitCode = 2;
}

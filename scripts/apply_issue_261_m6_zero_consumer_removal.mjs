import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const FIXTURE_PATH = "scripts/fixtures/issue-261-m6-zero-consumer-audit.json";
const FIXTURE = JSON.parse(readFileSync(resolve(ROOT, FIXTURE_PATH), "utf8"));
const REMOVE_KEYS = new Set(FIXTURE.auditRows
  .filter((row) => row.disposition === "REMOVE")
  .map((row) => `${row.source.path}#${row.source.ruleIndex}#${row.source.selectorIndex}`));
const HOLD_KEYS = new Set(FIXTURE.auditRows
  .filter((row) => row.disposition === "HOLD")
  .map((row) => `${row.source.path}#${row.source.ruleIndex}#${row.source.selectorIndex}`));

function normalizeSpace(value) { return value.replace(/\s+/g, " ").trim(); }
function sha256(value) { return createHash("sha256").update(value).digest("hex"); }
function eolFor(source) { return source.includes("\r\n") ? "\r\n" : "\n"; }

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
    if (character === "'" || character === '"') quote = character;
    else if (character === "(") round += 1;
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
  return sha256(JSON.stringify(declarations));
}

function formatRule(selectors, body, eol) {
  const lines = body.split(/\r?\n/);
  while (lines.length && !lines[0].trim()) lines.shift();
  while (lines.length && !lines.at(-1).trim()) lines.pop();
  const indents = lines.filter((line) => line.trim()).map((line) => line.match(/^\s*/)?.[0].length ?? 0);
  const baseIndent = indents.length ? Math.min(...indents) : 0;
  const normalizedBody = lines
    .map((line) => `${line.trim() ? "  " : ""}${line.slice(baseIndent)}`.replace(/[ \t]+$/, ""))
    .join(eol);
  return `${selectors.join(`,${eol}`)} {${eol}${normalizedBody}${eol}}`;
}

function frozenSource(path) {
  return execFileSync("git", ["show", `${FIXTURE.baseSha}:${path}`], {
    cwd: ROOT,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
  });
}

function normalizeRemovalWhitespace(source) {
  const eol = eolFor(source);
  let normalized = source;
  let previous;
  do {
    previous = normalized;
    normalized = normalized.replace(
      /^[ \t]*@(media|supports|container)[^{\r\n]*\{[ \t\r\n]*\}[ \t]*(?:\r?\n)?/gm,
      "",
    );
  } while (normalized !== previous);
  const compact = normalized
    .replace(/[ \t]+(?=\r?$)/gm, "")
    .replace(/(?:\r?\n[ \t]*){3,}/g, `${eol}${eol}`);
  return `${compact.replace(/[ \t\r\n]+$/, "")}${eol}`;
}

function transform(path, source) {
  const rules = scanCss(source);
  const groups = new Map();
  for (const rule of rules) {
    const key = `${path}#${rule.ruleIndex}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(rule);
  }
  const replacements = [];
  for (const [groupKey, group] of groups) {
    const selectedIndexes = new Set(group
      .filter((rule) => REMOVE_KEYS.has(`${groupKey}#${rule.selectorIndex}`))
      .map((rule) => rule.selectorIndex));
    if (!selectedIndexes.size) continue;
    const first = group[0];
    const selectors = splitTopLevel(source.slice(first.start, first.open));
    const remaining = selectors.filter((_, index) => !selectedIndexes.has(index + 1));
    const body = source.slice(first.bodyStart, first.close);
    const replacement = remaining.length ? formatRule(remaining, body, eolFor(source)) : "";
    let start = first.start;
    if (!remaining.length) {
      const lineStart = Math.max(0, source.lastIndexOf("\n", first.start - 1) + 1);
      if (!source.slice(lineStart, first.start).trim()) start = lineStart;
    }
    replacements.push({ start, end: first.close + 1, replacement });
  }
  const transformed = replacements
    .sort((left, right) => right.start - left.start)
    .reduce(
      (value, item) => `${value.slice(0, item.start)}${item.replacement}${value.slice(item.end)}`,
      source,
    );
  return normalizeRemovalWhitespace(transformed);
}

function rowKey(path, row) { return `${path}#${row.ruleIndex}#${row.selectorIndex}`; }
function verify(actualByPath, { exact }) {
  const holdsMissing = [];
  let selectorRows = 0;
  let cssRuleGroups = 0;
  for (const sourceInfo of FIXTURE.legacySources) {
    const path = sourceInfo.path;
    const actual = actualByPath.get(path);
    const rows = scanCss(actual);
    selectorRows += rows.length;
    cssRuleGroups += new Set(rows.map((row) => row.ruleIndex)).size;
    const frozenRows = scanCss(frozenSource(path));
    for (const row of frozenRows.filter((item) => HOLD_KEYS.has(rowKey(path, item)))) {
      const count = rows.filter((candidate) => (
        candidate.selector === row.selector
        && candidate.atContext.join(" | ") === row.atContext.join(" | ")
        && declarationSignature(actual.slice(candidate.bodyStart, candidate.close))
          === declarationSignature(frozenSource(path).slice(row.bodyStart, row.close))
      )).length;
      if (count < 1) holdsMissing.push(rowKey(path, row));
    }
    if (exact) {
      const expected = transform(path, frozenSource(path));
      if (actual !== expected) throw new Error(`exact M6 transform drifted: ${path}`);
    }
  }
  if (holdsMissing.length) {
    throw new Error(`M6 HOLD proof failed; holdsMissing=${holdsMissing}`);
  }
  if (selectorRows !== FIXTURE.expectedAfter.selectorRows
      || cssRuleGroups !== FIXTURE.expectedAfter.cssRuleGroups) {
    throw new Error(`M6 totals drifted: rows=${selectorRows}, groups=${cssRuleGroups}`);
  }
  return { selectorRows, cssRuleGroups };
}

const expectedByPath = new Map(FIXTURE.legacySources.map(({ path, sha256: expectedSha }) => {
  const frozen = frozenSource(path);
  if (sha256(frozen) !== expectedSha) throw new Error(`frozen legacy source drifted: ${path}`);
  return [path, transform(path, frozen)];
}));

if (process.argv.includes("--write")) {
  for (const [path, source] of expectedByPath) writeFileSync(resolve(ROOT, path), source, "utf8");
  const result = verify(expectedByPath, { exact: true });
  console.log(JSON.stringify({ mode: "write", remove: FIXTURE.remove, hold: FIXTURE.hold, ...result }, null, 2));
} else if (process.argv.includes("--check")) {
  const actualByPath = new Map(FIXTURE.legacySources.map(({ path }) => [
    path,
    readFileSync(resolve(ROOT, path), "utf8"),
  ]));
  const result = verify(actualByPath, { exact: process.argv.includes("--exact") });
  console.log(JSON.stringify({ mode: "check", remove: FIXTURE.remove, hold: FIXTURE.hold, ...result }, null, 2));
} else {
  console.error("Refusing to modify CSS without --write");
  process.exitCode = 2;
}

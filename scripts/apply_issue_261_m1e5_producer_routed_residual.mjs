import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const FIXTURE = JSON.parse(readFileSync(
  resolve(ROOT, "scripts/fixtures/issue-261-m1e5-producer-routed-residual.json"),
  "utf8",
));
const FROZEN_INVENTORY_TEXT = execFileSync(
  "git",
  ["show", `${FIXTURE.baseSha}:${FIXTURE.frozenInventory.path}`],
  { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "ignore"] },
);
const TARGET_IDS = new Set(FIXTURE.approvedIds);
const ROW_BY_KEY = new Map(FIXTURE.targetTuples.map((tuple) => [
  `${tuple[1]}#${tuple[3]}#${tuple[4]}`,
  {
    id: tuple[0],
    path: tuple[1],
    mainImportRank: tuple[2],
    ruleIndex: tuple[3],
    selectorIndex: tuple[4],
    selector: tuple[5],
    atContext: tuple[6],
    signature: tuple[10],
  },
]));
const OWNER_BY_ID = new Map(
  Object.values(FIXTURE.owners)
    .flatMap((owner) => owner.ids.filter((id) => TARGET_IDS.has(id)).map((id) => [id, owner.path])),
);

function normalizeSpace(value) {
  return value.replace(/\s+/g, " ").trim();
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

/** Parse CSS with the selector-row ordering used by the inventory generator. */
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

function sourceGroupKey(path, ruleIndex) {
  return `${path}#${ruleIndex}`;
}

function cssIdentity(row) {
  return `${normalizeSpace(row.selector)}\0${(row.atContext ?? []).join(" | ")}\0${row.signature ?? ""}`;
}

function tupleIdentity(path, selector, atContext) {
  return `${path}\0${normalizeSpace(selector)}\0${(atContext ?? []).join(" | ")}`;
}

const APPROVED_BY_IDENTITY = new Map(
  FIXTURE.targetTuples
    .filter((tuple) => TARGET_IDS.has(tuple[0]))
    .map((tuple) => [tupleIdentity(tuple[1], tuple[5], tuple[6]), tuple]),
);

function eolFor(source) {
  return source.includes("\r\n") ? "\r\n" : "\n";
}

function convertEol(value, eol) {
  return value.replace(/\r?\n/g, eol);
}

function parseDeclarations(body) {
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
    if (character === '"' || character === "'") quote = character;
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
      declarations.push({ property, value, important });
    }
  }
  return declarations;
}

function declarationSignature(body) {
  return createHash("sha256").update(JSON.stringify(
    parseDeclarations(body).map(({ property, value, important }) => [property, value, important]),
  )).digest("hex");
}

function wrapAtContext(ruleText, atContext, eol) {
  let wrapped = ruleText;
  for (let index = atContext.length - 1; index >= 0; index -= 1) {
    wrapped = `${atContext[index]} {${eol}${wrapped.split(/\r?\n/).map((line) => `  ${line}`).join(eol)}${eol}}`;
  }
  return wrapped;
}

function formatMovedRule(selectors, body, eol) {
  const lines = body.split(/\r?\n/);
  while (lines.length && !lines[0].trim()) lines.shift();
  while (lines.length && !lines.at(-1).trim()) lines.pop();
  const indents = lines
    .filter((line) => line.trim())
    .map((line) => line.match(/^\s*/)?.[0].length ?? 0);
  const baseIndent = indents.length ? Math.min(...indents) : 0;
  const normalizedBody = lines
    .map((line) => `${line.trim() ? "  " : ""}${line.slice(baseIndent)}`)
    .join(eol);
  return `${selectors.join(`,${eol}`)} {${eol}${normalizedBody}${eol}}`;
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(resolve(ROOT, path))).digest("hex");
}

function sha256Text(value) {
  return createHash("sha256").update(value).digest("hex");
}

function frozenSource(path) {
  return execFileSync("git", ["show", `${FIXTURE.baseSha}:${path}`], {
    cwd: ROOT,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
    maxBuffer: 16 * 1024 * 1024,
  });
}

function resetFromFrozenBase() {
  for (const { path } of FIXTURE.legacySources) {
    writeFileSync(resolve(ROOT, path), frozenSource(path), "utf8");
  }
  for (const ownerPath of new Set(Object.values(FIXTURE.owners).map((owner) => owner.path))) {
    let source = "";
    try {
      source = frozenSource(ownerPath);
    } catch {
      source = "";
    }
    const ownerFile = resolve(ROOT, ownerPath);
    mkdirSync(resolve(ownerFile, ".."), { recursive: true });
    writeFileSync(ownerFile, source, "utf8");
  }
}

function currentTargetRows(path, source) {
  const rules = scanCss(source);
  return rules
    .map((rule) => ({
      rule,
      tuple: APPROVED_BY_IDENTITY.get(tupleIdentity(path, rule.selector, rule.atContext)),
    }))
    .filter(({ tuple }) => tuple);
}

function ownerRows(path) {
  const source = readFileSync(resolve(ROOT, path), "utf8");
  return scanCss(source).map((rule) => ({
    ...rule,
    signature: declarationSignature(source.slice(rule.bodyStart, rule.close)),
  }));
}

function targetOwnerBlocks(path, source) {
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
    const targetRows = group
      .map((rule) => ({ rule, row: ROW_BY_KEY.get(`${path}#${rule.ruleIndex}#${rule.selectorIndex}`) }))
      .filter(({ row }) => row && TARGET_IDS.has(row.id));
    if (!targetRows.length) continue;
    const first = group[0];
    const originalPrelude = source.slice(first.start, first.open);
    const originalSelectors = splitTopLevel(originalPrelude);
    const selectedIndexes = new Set(targetRows.map(({ rule }) => rule.selectorIndex));
    const selectedSelectors = originalSelectors.filter((_, index) => selectedIndexes.has(index + 1));
    const remainingSelectors = originalSelectors.filter((_, index) => !selectedIndexes.has(index + 1));
    const body = source.slice(first.bodyStart, first.close);
    const sourceEol = eolFor(source);
    const remainingText = remainingSelectors.length ? formatMovedRule(remainingSelectors, body, sourceEol) : "";
    // Consume indentation when a complete rule is removed; otherwise nested
    // media rules leave whitespace-only lines that fail git diff --check.
    let replacementStart = first.start;
    if (!remainingSelectors.length) {
      const lineStart = Math.max(0, source.lastIndexOf("\n", first.start - 1) + 1);
      if (!source.slice(lineStart, first.start).trim()) replacementStart = lineStart;
    }
    replacements.push({ start: replacementStart, end: first.close + 1, text: remainingText });
    const byOwner = new Map();
    for (const target of targetRows) {
      const ownerPath = OWNER_BY_ID.get(target.row.id);
      if (!ownerPath) throw new Error(`${target.row.id}: target row has no truthful owner`);
      if (!byOwner.has(ownerPath)) byOwner.set(ownerPath, []);
      byOwner.get(ownerPath).push(target);
    }
    for (const [ownerPath, ownerTargets] of byOwner) {
      const ownerIndexes = new Set(ownerTargets.map(({ rule }) => rule.selectorIndex));
      const ownerSelectors = originalSelectors.filter((_, index) => ownerIndexes.has(index + 1));
      const selectedText = formatMovedRule(ownerSelectors, body, sourceEol);
      blocks.push({
        ownerPath,
        sourceKey: key,
        sourceRank: ownerTargets[0].row.mainImportRank,
        ruleIndex: first.ruleIndex,
        selectorIndex: ownerTargets[0].rule.selectorIndex,
        rowIds: ownerTargets.map(({ row }) => row.id),
        identityRows: ownerTargets.map(({ row }) => ({ selector: row.selector, atContext: row.atContext, signature: row.signature })),
        text: wrapAtContext(selectedText, first.atContext, sourceEol),
      });
    }
  }
  const nextSource = replacements
    .sort((left, right) => right.start - left.start)
    .reduce((value, replacement) => `${value.slice(0, replacement.start)}${replacement.text}${value.slice(replacement.end)}`, source);
  return { nextSource, blocks };
}

function appendBlocks(ownerPath, blocks) {
  const ownerFile = resolve(ROOT, ownerPath);
  if (!existsSync(ownerFile)) {
    mkdirSync(resolve(ownerFile, ".."), { recursive: true });
    writeFileSync(ownerFile, "", "utf8");
  }
  const existing = readFileSync(ownerFile, "utf8");
  const eol = eolFor(existing);
  const existingRules = ownerRows(ownerPath);
  const existingIdentities = new Set(existingRules.map(cssIdentity));
  const freshBlocks = blocks
    .sort((left, right) => left.sourceRank - right.sourceRank || left.ruleIndex - right.ruleIndex || left.selectorIndex - right.selectorIndex)
    .filter((block) => block.identityRows.some((row) => !existingIdentities.has(cssIdentity(row))));
  if (!freshBlocks.length) return false;
  const base = existing.replace(/[ \t]+$/, "");
  const prefix = base ? `${base}${eol}${eol}` : "";
  const separated = freshBlocks.map((_, index) => (index ? `${eol}${eol}` : ""));
  let body = "";
  freshBlocks.forEach((block, index) => {
    const blockText = `${separated[index]}/* M1E5 frozen ownership move: ${block.sourceKey}. */${eol}${convertEol(block.text, eol)}`;
    body += blockText;
  });
  writeFileSync(ownerFile, `${prefix}${body}${eol}`, "utf8");
  return true;
}

function verifyOwners() {
  const rowsByOwner = new Map();
  for (const ownerPath of new Set(OWNER_BY_ID.values())) {
    rowsByOwner.set(ownerPath, ownerRows(ownerPath));
  }
  const missing = [];
  const duplicate = [];
  for (const tuple of FIXTURE.targetTuples.filter((row) => TARGET_IDS.has(row[0]))) {
    const expectedOwner = OWNER_BY_ID.get(tuple[0]);
    const identity = `${normalizeSpace(tuple[5])}\0${tuple[6].join(" | ")}\0${tuple[10]}`;
    const matches = [];
    for (const [ownerPath, rows] of rowsByOwner) {
      for (const row of rows) {
        if (cssIdentity(row) === identity) matches.push(ownerPath);
      }
    }
    if (!matches.includes(expectedOwner)) missing.push(tuple[0]);
    if (matches.length > 1) duplicate.push(`${tuple[0]}:${matches.join(",")}`);
  }
  if (missing.length || duplicate.length) {
    throw new Error(`owner verification failed; missing=${missing.join(",")}; duplicate=${duplicate.join(",")}`);
  }
}

function report(mode) {
  const legacyRows = FIXTURE.legacySources.flatMap(({ path }) => {
    const source = readFileSync(resolve(ROOT, path), "utf8");
    return currentTargetRows(path, source);
  });
  const ownerCount = FIXTURE.approvedIds.filter((id) => OWNER_BY_ID.has(id)).length;
  console.log(JSON.stringify({
    mode,
    baseSha: FIXTURE.baseSha,
    frozenInventorySha256: FIXTURE.frozenInventory.sha256,
    approvedRows: FIXTURE.approvedMove.rows,
    approvedGroups: FIXTURE.approvedMove.groups,
    legacyTargetRowsPresent: legacyRows.length,
    ownerRowsExpected: ownerCount,
    idempotent: legacyRows.length === 0,
  }, null, 2));
}

if (process.argv.includes("--check")) {
  report("check");
  if (sha256Text(FROZEN_INVENTORY_TEXT) !== FIXTURE.frozenInventory.sha256) {
    throw new Error("frozen current inventory hash drifted; regenerate the current inventory before applying M1E5");
  }
  verifyOwners();
} else if (!process.argv.includes("--write")) {
  console.error("Refusing to modify CSS without --write");
  process.exitCode = 2;
} else {
  if (process.argv.includes("--repair-from-base")) resetFromFrozenBase();
  const allBlocks = [];
  for (const { path } of FIXTURE.legacySources) {
    // The transform is anchored to the frozen f51 producer source. This keeps
    // repeated runs deterministic after a failed/partial attempt; callers
    // must still review the resulting scoped diff before publication.
    const source = frozenSource(path);
    const { nextSource, blocks } = targetOwnerBlocks(path, source);
    if (nextSource !== source) writeFileSync(resolve(ROOT, path), nextSource, "utf8");
    allBlocks.push(...blocks);
  }
  const blocksByOwner = new Map();
  for (const block of allBlocks) {
    if (!blocksByOwner.has(block.ownerPath)) blocksByOwner.set(block.ownerPath, []);
    blocksByOwner.get(block.ownerPath).push(block);
  }
  for (const [ownerPath, blocks] of blocksByOwner) {
    if (appendBlocks(ownerPath, blocks)) console.log(`WROTE ${ownerPath}: ${blocks.length} frozen source groups`);
    else console.log(`UNCHANGED ${ownerPath}: all frozen identities already present`);
  }
  verifyOwners();
  report("write");
}

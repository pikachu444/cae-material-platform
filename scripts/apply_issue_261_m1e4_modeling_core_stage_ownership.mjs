import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const FIXTURE_PATH = resolve(ROOT, "scripts/fixtures/issue-261-m1e4-modeling-core-stage-ownership.json");
const fixture = JSON.parse(readFileSync(FIXTURE_PATH, "utf8"));
const inventory = JSON.parse(readFileSync(resolve(ROOT, fixture.frozenInventory.path), "utf8"));

function expandRanges(ranges, prefix = "CSS-") {
  return ranges.flatMap((range) => {
    const [startText, endText] = range.split("..");
    const start = Number(startText.slice(prefix.length));
    const end = endText ? Number(endText) : start;
    return Array.from({ length: end - start + 1 }, (_, index) => `${prefix}${String(start + index).padStart(4, "0")}`);
  });
}

function expandGroupRanges(ranges) {
  return ranges.flatMap((range) => {
    const [startText, endText] = range.split("..");
    const start = Number(startText);
    const end = endText ? Number(endText) : start;
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  });
}

function stripCommentsPreserveLines(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\r\n]/g, " "));
}

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

/** Parse CSS with the same rule/selector ordering as check_issue_261_css_inventory.mjs. */
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
    if (character === "}") {
      const entry = stack.pop();
      if (entry?.type === "rule" && entry.prelude) {
        // The inventory's ruleIndex is intentionally selector-row based: it uses
        // rows.length + 1 at rule close, so multi-selector groups create gaps.
        const ruleIndex = rules.length + 1;
        const selectors = splitTopLevel(entry.prelude);
        selectors.forEach((selector, selectorIndex) => {
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
  }
  return rules;
}

function groupKey(path, ruleIndex) {
  return `${path.endsWith("styles.css") ? "styles.css" : "layout.css"}#${ruleIndex}`;
}

const targetIds = new Set(expandRanges(fixture.targetIdRanges));
const plotIds = new Set(expandRanges(fixture.plotIdRanges));
const targetBySourceKey = new Map();
for (const row of inventory.selectors) {
  if (!targetIds.has(row.id)) continue;
  targetBySourceKey.set(`${row.source.path}#${row.source.ruleIndex}#${row.source.selectorIndex}`, row);
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(resolve(ROOT, path))).digest("hex");
}

function indent(value, prefix = "  ") {
  return value.split("\n").map((line) => `${prefix}${line}`).join("\n");
}

function wrapAtContext(ruleText, atContext) {
  let wrapped = ruleText;
  for (let index = atContext.length - 1; index >= 0; index -= 1) {
    wrapped = `${atContext[index]} {\n${indent(wrapped)}\n}`;
  }
  return wrapped;
}

function applySource(path, ownerPath) {
  const source = readFileSync(resolve(ROOT, path), "utf8");
  const rules = scanCss(source);
  const byGroup = new Map();
  for (const rule of rules) {
    const key = `${path}#${rule.ruleIndex}`;
    if (!byGroup.has(key)) byGroup.set(key, []);
    byGroup.get(key).push(rule);
  }
  const replacements = [];
  const ownerBlocks = [];
  for (const [key, group] of byGroup) {
    const targetRows = group
      .map((rule) => ({ rule, row: targetBySourceKey.get(`${path}#${rule.ruleIndex}#${rule.selectorIndex}`) }))
      .filter(({ row }) => row);
    if (!targetRows.length) continue;
    const first = group[0];
    const originalPrelude = source.slice(first.start, first.open);
    const originalSelectors = splitTopLevel(originalPrelude);
    const selectedIndexes = new Set(targetRows.map(({ rule }) => rule.selectorIndex));
    const selectedSelectors = originalSelectors.filter((_, index) => selectedIndexes.has(index + 1));
    const remainingSelectors = originalSelectors.filter((_, index) => !selectedIndexes.has(index + 1));
    const body = source.slice(first.bodyStart, first.close);
    const sourceGroup = groupKey(path, first.ruleIndex);
    const isComplete = remainingSelectors.length === 0;
    if (isComplete) {
      replacements.push({ start: first.start, end: first.close + 1, text: "" });
    } else {
      replacements.push({
        start: first.start,
        end: first.close + 1,
        text: `${remainingSelectors.join(",\n")} {${body}}`,
      });
    }
    const ownerSelectorText = selectedSelectors.join(",\n");
    ownerBlocks.push({
      sort: [fixture.legacySources.find((sourceFile) => sourceFile.path === path).mainImportRank, first.ruleIndex],
      id: sourceGroup,
      plot: targetRows.some(({ row }) => plotIds.has(row.id)),
      text: wrapAtContext(`${ownerSelectorText} {${body}}`, first.atContext),
    });
  }
  const nextSource = replacements
    .sort((left, right) => right.start - left.start)
    .reduce((value, replacement) => `${value.slice(0, replacement.start)}${replacement.text}${value.slice(replacement.end)}`, source);
  writeFileSync(resolve(ROOT, path), nextSource, "utf8");
  return ownerBlocks;
}

if (process.argv.includes("--check")) {
  for (const sourceFile of fixture.legacySources) {
    const actual = sha256(sourceFile.path);
    if (actual !== sourceFile.sha256) throw new Error(`${sourceFile.path}: frozen source hash drift (${actual})`);
    const rows = scanCss(readFileSync(resolve(ROOT, sourceFile.path), "utf8"));
    const expectedRows = inventory.selectors.filter((row) => row.source.path === sourceFile.path);
    if (rows.length !== expectedRows.length) throw new Error(`${sourceFile.path}: frozen selector count drift`);
  }
  const targetRows = inventory.selectors.filter((row) => targetIds.has(row.id));
  if (targetRows.length !== fixture.aggregate.targetRows) throw new Error("frozen target count drift");
  const groups = new Set(targetRows.map((row) => `${row.source.path}#${row.source.ruleIndex}`));
  if (groups.size !== fixture.aggregate.targetGroups) throw new Error("frozen target group count drift");
  console.log(JSON.stringify({
    targetRows: targetRows.length,
    targetGroups: groups.size,
    coreRows: targetRows.filter((row) => !plotIds.has(row.id)).length,
    plotRows: targetRows.filter((row) => plotIds.has(row.id)).length,
    completeGroups: Object.values(fixture.completeGroups).flatMap(expandGroupRanges).length,
    mixedGroups: Object.values(fixture.mixedGroups).flatMap(expandGroupRanges).length,
    retainedPeerRows: expandRanges(fixture.retainedPeerIdRanges).length,
    deferredRows: expandRanges(fixture.deferredIdRanges).length,
  }, null, 2));
} else if (!process.argv.includes("--write")) {
  console.error("Refusing to modify CSS without --write");
  process.exitCode = 2;
} else {
  const allBlocks = [
    ...applySource("apps/web/src/styles.css", fixture.owners.core),
    ...applySource("apps/web/src/design/layout.css", fixture.owners.core),
  ].sort((left, right) => left.sort[0] - right.sort[0] || left.sort[1] - right.sort[1]);
  const byOwner = new Map([[fixture.owners.core, []], [fixture.owners.plot, []]]);
  for (const block of allBlocks) byOwner.get(block.plot ? fixture.owners.plot : fixture.owners.core).push(block);
  for (const [ownerPath, blocks] of byOwner) {
    const path = resolve(ROOT, ownerPath);
    const original = readFileSync(path, "utf8").replace(/\s*$/, "");
    const suffix = blocks.map((block) => `\n\n/* M1E4 frozen ownership move: ${block.id}. */\n${block.text}`).join("");
    writeFileSync(path, `${original}${suffix}\n`, "utf8");
    console.log(`WROTE ${ownerPath}: ${blocks.length} groups`);
  }
}

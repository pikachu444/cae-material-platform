import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFile, readdir } from "node:fs/promises";
import { dirname, extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const BASELINE_SCHEMA = "cmp.frontend-guard-baseline.v1";

const SOURCE_ROOT = "apps/web/src";
const DEFAULT_BASELINE = "apps/web/frontend-guard-baseline.json";
const BASELINE_PROVENANCE_PATHS = new Set([
  DEFAULT_BASELINE,
  "scripts/check_frontend_guard.mjs",
  "scripts/check_frontend_guard.test.mjs",
]);
const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SOURCE_EXTENSIONS = new Set([".ts", ".tsx", ".css"]);
const CODE_EXTENSIONS = [".ts", ".tsx"];
const EXCLUDED_SOURCE = /\.(?:test|spec|stories)\.[^.]+$/;
const HOTSPOT_DECLARATION = /^(?:import\b|export\b|(?:async\s+)?function\b|class\b|interface\b|type\b|enum\b|namespace\b|(?:const|let|var)\b)/;
const SEMANTIC_CLASS_RULES = new Map([
  ["workbench-card", "CMP-FE-WORKBENCH-CARD"],
  ["eyebrow", "CMP-FE-EYEBROW"],
  ["status-chip", "CMP-FE-STATUS-CHIP"],
]);
const RAW_COLOR_LITERAL = /#[0-9a-f]{3,8}\b|\b(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color)a?\s*\(/i;
const CSS_NAMED_COLORS = new Set(`
  aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown
  burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan
  darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid
  darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet
  deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro
  ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki
  lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray
  lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey
  lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid
  mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue
  mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod
  palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple
  red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue
  slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white
  whitesmoke yellow yellowgreen
`.trim().split(/\s+/));
const COLOR_VALUE_PROPERTY = /^(?:--|.*(?:color|background|border|outline|fill|stroke|shadow|filter|decoration|caret|accent|column-rule|text-emphasis))/;
const GLOBAL_CSS = new Set([
  "apps/web/src/styles.css",
  "apps/web/src/design/layout.css",
]);

export class FrontendGuardError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "FrontendGuardError";
    this.code = code;
  }
}

function posix(value) {
  return value.split(sep).join("/");
}

function lineAt(source, offset) {
  let line = 1;
  for (let index = 0; index < offset; index += 1) {
    if (source.charCodeAt(index) === 10) line += 1;
  }
  return line;
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function normalizeSpace(value) {
  return value.replace(/\s+/g, " ").trim();
}

function finding(ruleId, path, line, signature, message, remediation, extra = {}) {
  const fingerprint = sha256([ruleId, path, String(line), normalizeSpace(signature)].join("\0"));
  return {
    ruleId,
    path,
    line,
    signature: normalizeSpace(signature),
    fingerprint,
    message,
    remediation,
    ...extra,
  };
}

function issueReference(value) {
  return typeof value === "string" && /^#\d+$/.test(value);
}

function nonEmpty(value) {
  return typeof value === "string" && value.trim().length > 0;
}

export function validateBaseline(baseline) {
  const errors = [];
  if (!baseline || typeof baseline !== "object" || Array.isArray(baseline)) {
    return ["baseline must be an object"];
  }
  if (baseline.schemaVersion !== BASELINE_SCHEMA) {
    errors.push(`schemaVersion must be ${BASELINE_SCHEMA}`);
  }
  if (typeof baseline.sourceSha !== "string" || !/^[0-9a-f]{40}$/.test(baseline.sourceSha)) {
    errors.push("sourceSha must be a lowercase 40-character Git SHA");
  }
  if (!issueReference(baseline.ownerIssue)) errors.push("ownerIssue must be an issue reference such as #256");
  if (!Array.isArray(baseline.hotspots)) errors.push("hotspots must be an array");
  if (!Array.isArray(baseline.debt)) errors.push("debt must be an array");
  if (!Array.isArray(baseline.exceptions)) errors.push("exceptions must be an array");

  const hotspotPaths = new Set();
  for (const [index, hotspot] of (baseline.hotspots ?? []).entries()) {
    if (!hotspot || typeof hotspot !== "object") {
      errors.push(`hotspots[${index}] must be an object`);
      continue;
    }
    if (!nonEmpty(hotspot.path)) errors.push(`hotspots[${index}].path is required`);
    if (hotspotPaths.has(hotspot.path)) errors.push(`hotspot path is duplicated: ${hotspot.path}`);
    hotspotPaths.add(hotspot.path);
    if (!Number.isSafeInteger(hotspot.baselineLines) || hotspot.baselineLines < 1) {
      errors.push(`hotspots[${index}].baselineLines must be a positive integer`);
    }
    if (!Array.isArray(hotspot.responsibilities) || hotspot.responsibilities.some((item) => !nonEmpty(item))) {
      errors.push(`hotspots[${index}].responsibilities must contain non-empty strings`);
    }
    if (!issueReference(hotspot.followUpIssue)) errors.push(`hotspots[${index}].followUpIssue must be an issue reference`);
    if (!nonEmpty(hotspot.removalCondition)) errors.push(`hotspots[${index}].removalCondition is required`);
  }

  const debtKeys = new Set();
  for (const [index, debt] of (baseline.debt ?? []).entries()) {
    if (!debt || typeof debt !== "object") {
      errors.push(`debt[${index}] must be an object`);
      continue;
    }
    if (!nonEmpty(debt.ruleId)) errors.push(`debt[${index}].ruleId is required`);
    if (!nonEmpty(debt.scope)) errors.push(`debt[${index}].scope is required`);
    const key = `${debt.ruleId}\0${debt.scope}`;
    if (debtKeys.has(key)) errors.push(`debt entry is duplicated: ${debt.ruleId} ${debt.scope}`);
    debtKeys.add(key);
    if (!Number.isSafeInteger(debt.count) || debt.count < 0) errors.push(`debt[${index}].count must be a non-negative integer`);
    if (!nonEmpty(debt.reason)) errors.push(`debt[${index}].reason is required`);
    if (!issueReference(debt.followUpIssue)) errors.push(`debt[${index}].followUpIssue must be an issue reference`);
    if (!nonEmpty(debt.removalCondition)) errors.push(`debt[${index}].removalCondition is required`);
  }

  const exceptionKeys = new Set();
  for (const [index, exception] of (baseline.exceptions ?? []).entries()) {
    if (!exception || typeof exception !== "object") {
      errors.push(`exceptions[${index}] must be an object`);
      continue;
    }
    if (!nonEmpty(exception.ruleId)) errors.push(`exceptions[${index}].ruleId is required`);
    if (!nonEmpty(exception.path)) errors.push(`exceptions[${index}].path is required`);
    if (typeof exception.fingerprint !== "string" || !/^[0-9a-f]{64}$/.test(exception.fingerprint)) {
      errors.push(`exceptions[${index}].fingerprint must be a lowercase SHA-256`);
    }
    const key = `${exception.ruleId}\0${exception.path}\0${exception.fingerprint}`;
    if (exceptionKeys.has(key)) errors.push(`exception is duplicated: ${exception.ruleId} ${exception.path}`);
    exceptionKeys.add(key);
    if (!Number.isSafeInteger(exception.maxOccurrences) || exception.maxOccurrences < 1) {
      errors.push(`exceptions[${index}].maxOccurrences must be a positive integer`);
    }
    if (!nonEmpty(exception.reason)) errors.push(`exceptions[${index}].reason is required`);
    if (!issueReference(exception.ownerIssue)) errors.push(`exceptions[${index}].ownerIssue must be an issue reference`);
    if (!nonEmpty(exception.removalCondition)) errors.push(`exceptions[${index}].removalCondition is required`);
  }
  return errors.sort();
}

export function assertBaselineProvenance(baseline, mergeBase) {
  if (baseline.sourceSha !== mergeBase) {
    throw new FrontendGuardError(
      "BASELINE_PROVENANCE",
      `baseline sourceSha ${baseline.sourceSha} does not match origin/main merge-base ${mergeBase}`,
    );
  }
}

export function requiresBaselineProvenance(changedPaths) {
  return [...changedPaths].some(
    (path) => path.startsWith(`${SOURCE_ROOT}/`) || BASELINE_PROVENANCE_PATHS.has(path),
  );
}

async function collectSourceFiles(projectRoot) {
  const root = resolve(projectRoot, SOURCE_ROOT);
  const files = [];
  async function visit(directory) {
    const entries = await readdir(directory, { withFileTypes: true });
    entries.sort((left, right) => left.name.localeCompare(right.name));
    for (const entry of entries) {
      const absolute = join(directory, entry.name);
      if (entry.isDirectory()) await visit(absolute);
      else if (SOURCE_EXTENSIONS.has(extname(entry.name)) && !EXCLUDED_SOURCE.test(entry.name)) files.push(absolute);
    }
  }
  await visit(root);
  return files;
}

function resolveImport(sourcePath, specifier, fileSet) {
  if (!specifier.startsWith(".")) return null;
  const base = resolve(dirname(sourcePath), specifier);
  for (const candidate of [base, ...CODE_EXTENSIONS.map((extension) => `${base}${extension}`), ...CODE_EXTENSIONS.map((extension) => join(base, `index${extension}`))]) {
    if (fileSet.has(resolve(candidate))) return resolve(candidate);
  }
  return null;
}

function layer(path) {
  const relativePath = path.replace(/^apps\/web\/src\//, "");
  if (relativePath === "app.tsx" || relativePath === "main.tsx" || relativePath.startsWith("app/")) return { kind: "app" };
  const feature = /^features\/([^/]+)(?:\/|$)/.exec(relativePath);
  if (feature) return { kind: "feature", name: feature[1] };
  if (relativePath.startsWith("shared/") || relativePath.startsWith("design/")) return { kind: "shared" };
  return { kind: "legacy" };
}

function stripCodeComments(source) {
  let result = "";
  let quote = null;
  let lineComment = false;
  let blockComment = false;
  for (let index = 0; index < source.length; index += 1) {
    const current = source[index];
    const next = source[index + 1];
    if (lineComment) {
      if (current === "\n") {
        lineComment = false;
        result += current;
      } else result += " ";
      continue;
    }
    if (blockComment) {
      if (current === "*" && next === "/") {
        result += "  ";
        index += 1;
        blockComment = false;
      } else result += current === "\n" ? "\n" : " ";
      continue;
    }
    if (quote) {
      result += current;
      if (current === "\\") {
        if (index + 1 < source.length) {
          result += source[index + 1];
          index += 1;
        }
      } else if (current === quote) quote = null;
      continue;
    }
    if (current === '"' || current === "'" || current === "`") {
      quote = current;
      result += current;
    } else if (current === "/" && next === "/") {
      result += "  ";
      index += 1;
      lineComment = true;
    } else if (current === "/" && next === "*") {
      result += "  ";
      index += 1;
      blockComment = true;
    } else result += current;
  }
  return result;
}

function moduleSpecifiers(source) {
  const clean = stripCodeComments(source);
  const imports = [];
  const patterns = [
    /\bimport\s+(?!\()(?:type\s+)?(?:[^;]*?\s+from\s+)?["']([^"']+)["']/gs,
    /\bexport\s+(?:type\s+)?[^;]*?\s+from\s+["']([^"']+)["']/gs,
    /\bimport\s*\(\s*["']([^"']+)["']\s*\)/g,
  ];
  for (const pattern of patterns) {
    for (const match of clean.matchAll(pattern)) {
      imports.push({ specifier: match[1], offset: match.index });
    }
  }
  return imports.sort((left, right) => left.offset - right.offset || left.specifier.localeCompare(right.specifier));
}

function scanCodeFile({ absolute, path, source, fileSet, projectRoot, changedLines, hotspot }) {
  const findings = [];
  const edges = [];
  const sourceLayer = layer(path);

  for (const item of moduleSpecifiers(source)) {
    const targetAbsolute = resolveImport(absolute, item.specifier, fileSet);
    if (!targetAbsolute) continue;
    const targetPath = posix(relative(projectRoot, targetAbsolute));
    const targetLayer = layer(targetPath);
    const line = lineAt(source, item.offset);
    edges.push({ targetPath, line });
    if (targetPath === "apps/web/src/api.ts" && path !== targetPath) {
      findings.push(finding(
        "CMP-FE-ROOT-API-COMPATIBILITY", path, line, `${path}->${targetPath}`,
        "module imports the bounded root API compatibility facade",
        "Import transport/auth from shared or resource calls through the owning feature public entry point.",
      ));
    }
    if (sourceLayer.kind === "shared" && targetLayer.kind !== "shared") {
      findings.push(finding(
        "CMP-FE-IMPORT-DIRECTION", path, line, `${path}->${targetPath}`,
        `shared/design module imports ${targetLayer.kind} module ${targetPath}`,
        "Move the dependency to shared, invert it through an app/feature boundary, or record an exact bounded exception.",
      ));
    }
    if (sourceLayer.kind === "feature" && targetLayer.kind === "app") {
      findings.push(finding(
        "CMP-FE-IMPORT-DIRECTION", path, line, `${path}->${targetPath}`,
        `feature module imports app module ${targetPath}`,
        "Keep dependencies app -> features -> shared; move orchestration to app or the shared contract downward.",
      ));
    }
    if (sourceLayer.kind === "feature" && targetLayer.kind === "feature" && sourceLayer.name !== targetLayer.name) {
      const targetRelative = targetPath.replace(/^apps\/web\/src\/features\//, "");
      const publicEntry = targetRelative === `${targetLayer.name}/index.ts` || targetRelative === `${targetLayer.name}/index.tsx`;
      if (!publicEntry) {
        findings.push(finding(
          "CMP-FE-FEATURE-DEEP-IMPORT", path, line, `${path}->${targetPath}`,
          `feature ${sourceLayer.name} deep-imports ${targetLayer.name} internals`,
          `Import through features/${targetLayer.name}/index.ts or move cross-feature orchestration to app.`,
        ));
      }
    }
  }

  const tokenPattern = /\b(workbench-card|eyebrow|status-chip)\b/g;
  for (const match of stripCodeComments(source).matchAll(tokenPattern)) {
    const token = match[1];
    const ruleId = SEMANTIC_CLASS_RULES.get(token);
    findings.push(finding(
      ruleId, path, lineAt(source, match.index), token,
      `new ${token} usage requires an explicit semantic role`,
      token === "status-chip"
        ? "Use a neutral role unless this is an actual lifecycle/status value; otherwise record the exact semantic exception."
        : "Use alignment, spacing, divider, or an owned primitive; otherwise record the exact semantic exception.",
    ));
  }
  const fillerPattern = /\b([\w-]*(?:filler|fake-data|decorative-spacer)[\w-]*)\b/gi;
  for (const match of stripCodeComments(source).matchAll(fillerPattern)) {
    const token = match[1];
    if (/placeholder/i.test(token)) continue;
    findings.push(finding(
      "CMP-FE-FABRICATED-FILLER", path, lineAt(source, match.index), token,
      `token ${token} signals fabricated filler content`,
      "Use truthful contract-backed companion data or balanced whitespace.",
    ));
  }

  if (hotspot && changedLines && changedLines.size > 0) {
    const lines = stripCodeComments(source).split(/\r?\n/);
    for (const line of [...changedLines].sort((left, right) => left - right)) {
      const text = lines[line - 1] ?? "";
      if (!HOTSPOT_DECLARATION.test(text)) continue;
      const kind = /^(?:import|export|function|class|interface|type|enum|namespace|const|let|var)\b/.exec(text)?.[0] ?? "declaration";
      findings.push(finding(
        "CMP-FE-HOTSPOT-RESPONSIBILITY", path, line, `${kind}:${normalizeSpace(text)}`,
        `registered hotspot adds a top-level ${kind} responsibility`,
        "Move the responsibility to its owned feature/shared module or add an issue-owned exact exception with an exit condition.",
      ));
    }
  }
  return { findings, edges };
}

function stripCssComments(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " "));
}

function scanCssBlocks(path, source) {
  const clean = stripCssComments(source);
  const selectors = [];
  const media = [];
  const stack = [];
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
      const prelude = clean.slice(tokenStart, index).trim();
      const startOffset = tokenStart + clean.slice(tokenStart, index).search(/\S|$/);
      const entry = prelude.startsWith("@media")
        ? { type: "media", prelude, line: lineAt(clean, startOffset) }
        : prelude.startsWith("@")
          ? { type: "at", prelude, line: lineAt(clean, startOffset) }
          : { type: "rule", prelude: normalizeSpace(prelude), line: lineAt(clean, startOffset) };
      stack.push(entry);
      if (entry.type === "rule" && entry.prelude) selectors.push(entry);
      if (entry.type === "media") media.push(entry);
      tokenStart = index + 1;
      continue;
    }
    if (character === "}") {
      stack.pop();
      tokenStart = index + 1;
    }
  }
  return { clean, selectors, media };
}

function cssLengthInPixels(value, unit) {
  const amount = Number(value);
  if (unit.toLowerCase() === "px") return amount;
  return amount * 16;
}

function wideMediaWidths(prelude) {
  const widths = [];
  const patterns = [
    /\bmin-width\s*:\s*(\d+(?:\.\d+)?)\s*(px|rem|em)\b/gi,
    /\bwidth\s*(?:>=|>)\s*(\d+(?:\.\d+)?)\s*(px|rem|em)\b/gi,
    /(\d+(?:\.\d+)?)\s*(px|rem|em)\s*(?:<=|<)\s*width\b/gi,
  ];
  for (const pattern of patterns) {
    for (const match of prelude.matchAll(pattern)) widths.push(cssLengthInPixels(match[1], match[2]));
  }
  return widths;
}

function hasRawColor(property, value) {
  const urlsRemoved = value.replace(/\burl\(\s*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^)])*\)/gi, " ");
  if (RAW_COLOR_LITERAL.test(urlsRemoved)) return true;
  if (!COLOR_VALUE_PROPERTY.test(property)) return false;
  const semanticReferencesRemoved = urlsRemoved.replace(/--[\w-]+/g, " ");
  return [...semanticReferencesRemoved.matchAll(/[a-z][a-z0-9-]*/gi)]
    .some((match) => CSS_NAMED_COLORS.has(match[0].toLowerCase()));
}

function scanCssFile(path, source) {
  const findings = [];
  const { clean, selectors, media } = scanCssBlocks(path, source);
  if (GLOBAL_CSS.has(path)) {
    for (const selector of selectors) {
      findings.push(finding(
        "CMP-FE-GLOBAL-CSS-SELECTOR", path, selector.line, selector.prelude,
        `legacy global stylesheet owns selector ${selector.prelude}`,
        "Place new feature arrangement in a feature-owned stylesheet; existing selectors remain warning-baselined.",
      ));
    }
  }
  for (const item of media) {
    if (wideMediaWidths(item.prelude).some((value) => value >= 1600)) {
      findings.push(finding(
        "CMP-FE-WIDE-MEDIA", path, item.line, item.prelude,
        `wide-screen media override uses ${item.prelude}`,
        "Use shared density/layout tokens; an exceptional shared policy needs an exact issue-owned allowance.",
      ));
    }
  }
  const declarations = /([\w-]+)\s*:\s*([^;{}]+)(?=;|})/g;
  for (const match of clean.matchAll(declarations)) {
    const property = match[1].toLowerCase();
    const value = normalizeSpace(match[2]);
    const line = lineAt(clean, match.index);
    const tokenDefinition = path === "apps/web/src/design/tokens.css" && property.startsWith("--");
    if (!tokenDefinition && hasRawColor(property, value)) {
      findings.push(finding(
        "CMP-FE-RAW-COLOR", path, line, `${property}:${value}`,
        `raw color in ${property}: ${value}`,
        "Use an existing semantic color token, or define a shared token in design/tokens.css under an approved primitive unit.",
      ));
    }
    if (property === "font-weight" && !value.includes("var(") && !/^(?:inherit|initial|unset|revert|revert-layer)$/.test(value)) {
      findings.push(finding(
        "CMP-FE-FONT-WEIGHT", path, line, value,
        `literal font-weight ${value} bypasses the typography role contract`,
        "Use an existing typography role/token; add a new role only in the approved semantic-primitives unit.",
      ));
    }
    if (property === "zoom" && value !== "normal") {
      findings.push(finding(
        "CMP-FE-CSS-ZOOM", path, line, value,
        `CSS zoom ${value} is a forbidden display shortcut`,
        "Use shared density, pane, control, typography, and plot tokens.",
      ));
    }
    if ((property === "transform" && /\bscale(?:3d|x|y)?\s*\(/i.test(value)) || (property === "scale" && value !== "none")) {
      findings.push(finding(
        "CMP-FE-BLANKET-SCALE", path, line, value,
        `scale transform requires proof that it is not blanket UI scaling: ${value}`,
        "Use shared density/layout tokens or record the exact bounded interaction exception.",
      ));
    }
  }
  for (const selector of selectors) {
    if (/(^|[-_.#])(?:filler|fake-data|decorative-spacer)(?:[-_.#]|$)/i.test(selector.prelude)) {
      findings.push(finding(
        "CMP-FE-FABRICATED-FILLER", path, selector.line, selector.prelude,
        `selector ${selector.prelude} signals fabricated filler content`,
        "Use truthful contract-backed companion data or balanced whitespace.",
      ));
    }
  }
  return findings;
}

function dependencyCycles(graph, changedLines) {
  const indexByPath = new Map();
  const lowByPath = new Map();
  const stack = [];
  const onStack = new Set();
  const components = [];
  let nextIndex = 0;
  function visit(path) {
    indexByPath.set(path, nextIndex);
    lowByPath.set(path, nextIndex);
    nextIndex += 1;
    stack.push(path);
    onStack.add(path);
    for (const edge of graph.get(path) ?? []) {
      if (!graph.has(edge.targetPath)) continue;
      if (!indexByPath.has(edge.targetPath)) {
        visit(edge.targetPath);
        lowByPath.set(path, Math.min(lowByPath.get(path), lowByPath.get(edge.targetPath)));
      } else if (onStack.has(edge.targetPath)) {
        lowByPath.set(path, Math.min(lowByPath.get(path), indexByPath.get(edge.targetPath)));
      }
    }
    if (lowByPath.get(path) !== indexByPath.get(path)) return;
    const component = [];
    while (stack.length) {
      const member = stack.pop();
      onStack.delete(member);
      component.push(member);
      if (member === path) break;
    }
    const selfCycle = component.length === 1 && (graph.get(component[0]) ?? []).some((edge) => edge.targetPath === component[0]);
    if (component.length > 1 || selfCycle) components.push(component.sort());
  }
  for (const path of [...graph.keys()].sort()) if (!indexByPath.has(path)) visit(path);
  return components.map((component) => finding(
    "CMP-FE-DEPENDENCY-CYCLE", component[0], 1, component.join("->"),
    `local dependency cycle: ${component.join(" -> ")}`,
    "Break the cycle by moving the shared contract downward or orchestration upward.",
    { changed: component.some((path) => (changedLines.get(path)?.size ?? 0) > 0) },
  ));
}

export async function scanProject({ projectRoot, baseline, changedLines = new Map() }) {
  const root = resolve(projectRoot);
  const absoluteFiles = await collectSourceFiles(root);
  const fileSet = new Set(absoluteFiles.map((path) => resolve(path)));
  const findings = [];
  const graph = new Map();
  const lineCounts = new Map();
  const hotspotByPath = new Map((baseline.hotspots ?? []).map((item) => [item.path, item]));
  for (const absolute of absoluteFiles) {
    const path = posix(relative(root, absolute));
    const source = await readFile(absolute, "utf8");
    lineCounts.set(path, source.split(/\r?\n/).length - (source.endsWith("\n") ? 1 : 0));
    if (path.endsWith(".css")) {
      findings.push(...scanCssFile(path, source));
      continue;
    }
    const result = scanCodeFile({ absolute, path, source, fileSet, projectRoot: root, changedLines: changedLines.get(path), hotspot: hotspotByPath.has(path) });
    findings.push(...result.findings);
    graph.set(path, result.edges);
  }
  findings.push(...dependencyCycles(graph, changedLines));
  for (const [path, hotspot] of hotspotByPath) {
    const currentLines = lineCounts.get(path);
    if (currentLines === undefined) continue;
    if (currentLines > hotspot.baselineLines) {
      findings.push(finding(
        "CMP-FE-HOTSPOT-GROWTH", path, hotspot.baselineLines + 1,
        `${hotspot.baselineLines}->${currentLines}`,
        `registered hotspot grew from ${hotspot.baselineLines} to ${currentLines} lines`,
        `Line count is a review signal, not a split target; use ${hotspot.followUpIssue} extraction or record an exact bounded exception.`,
        { changed: true },
      ));
    }
  }
  return findings.sort((left, right) => left.path.localeCompare(right.path) || left.line - right.line || left.ruleId.localeCompare(right.ruleId) || left.signature.localeCompare(right.signature));
}

async function scanBaseFindings({ projectRoot, baseline, mergeBase, changedLines }) {
  const root = resolve(projectRoot);
  const absoluteFiles = await collectSourceFiles(root);
  const fileSet = new Set(absoluteFiles.map((path) => resolve(path)));
  const findings = [];
  for (const path of [...changedLines.keys()].sort()) {
    if (!path.startsWith(`${SOURCE_ROOT}/`) || !SOURCE_EXTENSIONS.has(extname(path)) || EXCLUDED_SOURCE.test(path)) continue;
    let source;
    try {
      source = execFileSync("git", ["show", `${mergeBase}:${path}`], {
        cwd: root,
        encoding: "utf8",
        maxBuffer: 16 * 1024 * 1024,
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch {
      continue;
    }
    if (path.endsWith(".css")) findings.push(...scanCssFile(path, source));
    else {
      const result = scanCodeFile({
        absolute: resolve(root, path),
        path,
        source,
        fileSet,
        projectRoot: root,
        changedLines: undefined,
        hotspot: false,
      });
      findings.push(...result.findings);
    }
  }
  return findings;
}

function scopeContains(scope, path) {
  return path === scope || path.startsWith(`${scope}/`);
}

function debtForFinding(baseline, item) {
  const matches = baseline.debt.filter((debt) => debt.ruleId === item.ruleId && scopeContains(debt.scope, item.path));
  matches.sort((left, right) => right.scope.length - left.scope.length);
  return matches[0] ?? null;
}

function occurrenceKey(item) {
  return `${item.ruleId}\0${item.path}\0${item.signature}`;
}

export async function evaluateGuard({ projectRoot, baseline, changedLines = new Map(), baseFindings = null }) {
  const validationErrors = validateBaseline(baseline);
  if (validationErrors.length) throw new FrontendGuardError("INVALID_BASELINE", validationErrors.join("; "));
  const findings = await scanProject({ projectRoot, baseline, changedLines });
  const observedCounts = new Map();
  for (const item of findings) {
    const debt = debtForFinding(baseline, item);
    const key = debt ? `${debt.ruleId}\0${debt.scope}` : `${item.ruleId}\0${item.path}`;
    observedCounts.set(key, (observedCounts.get(key) ?? 0) + 1);
  }
  const candidateFingerprints = new Set();
  if (baseFindings === null) {
    for (const item of findings) if (changedLines.get(item.path)?.has(item.line) || item.changed) candidateFingerprints.add(item.fingerprint);
  } else {
    const baseOccurrenceCounts = new Map();
    for (const item of baseFindings) baseOccurrenceCounts.set(occurrenceKey(item), (baseOccurrenceCounts.get(occurrenceKey(item)) ?? 0) + 1);
    const currentOccurrences = new Map();
    for (const item of findings) {
      const key = occurrenceKey(item);
      if (!currentOccurrences.has(key)) currentOccurrences.set(key, []);
      currentOccurrences.get(key).push(item);
    }
    for (const [key, items] of currentOccurrences) {
      if (!items.some((item) => changedLines.has(item.path) || item.changed)) continue;
      const added = Math.max(0, items.length - (baseOccurrenceCounts.get(key) ?? 0));
      const choices = [...items].sort((left, right) => Number(changedLines.get(right.path)?.has(right.line) ?? false) - Number(changedLines.get(left.path)?.has(left.line) ?? false) || right.line - left.line);
      for (const item of choices.slice(0, added)) candidateFingerprints.add(item.fingerprint);
    }
  }
  const grouped = new Map();
  for (const item of findings) {
    const debt = debtForFinding(baseline, item);
    const key = debt ? `${debt.ruleId}\0${debt.scope}` : `${item.ruleId}\0${item.path}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  }
  for (const items of grouped.values()) {
    const debt = debtForFinding(baseline, items[0]);
    const allowance = debt?.count ?? 0;
    const overflow = Math.max(0, items.length - allowance);
    if (overflow === 0) continue;
    const choices = [...items].sort((left, right) => Number(changedLines.get(right.path)?.has(right.line) ?? false) - Number(changedLines.get(left.path)?.has(left.line) ?? false) || right.line - left.line);
    for (const item of choices.slice(0, overflow)) candidateFingerprints.add(item.fingerprint);
  }

  const exceptionUsage = new Map();
  const violations = [];
  for (const item of findings) {
    if (!candidateFingerprints.has(item.fingerprint)) continue;
    const exception = baseline.exceptions.find((entry) => entry.ruleId === item.ruleId && entry.path === item.path && entry.fingerprint === item.fingerprint);
    if (exception) {
      const used = exceptionUsage.get(exception) ?? 0;
      if (used < exception.maxOccurrences) {
        exceptionUsage.set(exception, used + 1);
        continue;
      }
    }
    violations.push(item);
  }
  const staleExceptions = baseline.exceptions.filter((entry) => !findings.some((item) => item.ruleId === entry.ruleId && item.path === entry.path && item.fingerprint === entry.fingerprint));
  for (const entry of staleExceptions) {
    violations.push(finding(
      "CMP-FE-STALE-EXCEPTION", entry.path, 1, `${entry.ruleId}:${entry.fingerprint}`,
      `allowlist exception no longer matches a finding for ${entry.ruleId}`,
      "Remove the stale exception so resolved debt cannot silently return.",
    ));
  }
  const warnings = [];
  for (const debt of baseline.debt) {
    const key = `${debt.ruleId}\0${debt.scope}`;
    const count = observedCounts.get(key) ?? 0;
    if (count > 0) warnings.push({ ruleId: debt.ruleId, scope: debt.scope, count, baselineCount: debt.count, message: debt.reason, followUpIssue: debt.followUpIssue });
    else if (debt.count > 0) warnings.push({ ruleId: debt.ruleId, scope: debt.scope, count: 0, baselineCount: debt.count, message: "Baseline debt is gone; lower or remove this entry.", followUpIssue: debt.followUpIssue });
  }
  for (const hotspot of baseline.hotspots) {
    warnings.push({
      ruleId: "CMP-FE-HOTSPOT-BASELINE",
      scope: hotspot.path,
      count: hotspot.baselineLines,
      baselineCount: hotspot.baselineLines,
      message: `Registered responsibilities: ${hotspot.responsibilities.join(", ")}`,
      followUpIssue: hotspot.followUpIssue,
    });
  }
  warnings.sort((left, right) => left.scope.localeCompare(right.scope) || left.ruleId.localeCompare(right.ruleId));
  violations.sort((left, right) => left.path.localeCompare(right.path) || left.line - right.line || left.ruleId.localeCompare(right.ruleId));
  return { passed: violations.length === 0, violations, warnings, findings };
}

function parseDiff(output) {
  const changed = new Map();
  let path = null;
  let newLine = 0;
  for (const line of output.split(/\r?\n/)) {
    if (line.startsWith("+++ ")) {
      const value = line.slice(4).trim();
      path = value === "/dev/null" ? null : value.replace(/^b\//, "");
      continue;
    }
    const hunk = /^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@/.exec(line);
    if (hunk) {
      newLine = Number(hunk[1]);
      continue;
    }
    if (!path || line.startsWith("--- ")) continue;
    if (line.startsWith("+") && !line.startsWith("+++")) {
      if (!changed.has(path)) changed.set(path, new Set());
      changed.get(path).add(newLine);
      newLine += 1;
    } else if (!line.startsWith("-")) {
      newLine += 1;
    }
  }
  return changed;
}

async function collectGitChangeContext(projectRoot) {
  const root = resolve(projectRoot);
  let mergeBase;
  try {
    mergeBase = execFileSync("git", ["merge-base", "origin/main", "HEAD"], { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
  } catch (error) {
    throw new FrontendGuardError("GIT_BASELINE", `cannot resolve origin/main merge-base: ${error.message}`);
  }
  const diff = execFileSync("git", ["diff", "--unified=0", "--no-ext-diff", "--find-renames", mergeBase], { cwd: root, encoding: "utf8", maxBuffer: 32 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"] });
  const changed = parseDiff(diff);
  const changedPaths = new Set(
    execFileSync("git", ["diff", "--name-only", "-z", "--no-renames", mergeBase], {
      cwd: root,
      encoding: "utf8",
      maxBuffer: 32 * 1024 * 1024,
      stdio: ["ignore", "pipe", "pipe"],
    }).split("\0").filter(Boolean),
  );
  const untracked = execFileSync("git", ["ls-files", "--others", "--exclude-standard"], { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).split(/\r?\n/).filter(Boolean);
  for (const path of untracked) {
    changedPaths.add(path);
    if (!path.startsWith(`${SOURCE_ROOT}/`) || !SOURCE_EXTENSIONS.has(extname(path)) || EXCLUDED_SOURCE.test(path)) continue;
    const source = await readFile(resolve(root, path), "utf8");
    changed.set(path, new Set(source.split(/\r?\n/).map((_line, index) => index + 1)));
  }
  return { changedLines: changed, changedPaths, mergeBase };
}

export async function collectChangedLines(projectRoot) {
  return (await collectGitChangeContext(projectRoot)).changedLines;
}

export async function runFrontendGuardCli({
  projectRoot = REPOSITORY_ROOT,
  baselinePath = DEFAULT_BASELINE,
  json = false,
  stdout = process.stdout,
  stderr = process.stderr,
} = {}) {
  try {
    const baseline = JSON.parse(await readFile(resolve(projectRoot, baselinePath), "utf8"));
    const { changedLines, changedPaths, mergeBase } = await collectGitChangeContext(projectRoot);
    if (requiresBaselineProvenance(changedPaths)) assertBaselineProvenance(baseline, mergeBase);
    const baseFindings = await scanBaseFindings({ projectRoot, baseline, mergeBase, changedLines });
    const report = await evaluateGuard({ projectRoot, baseline, changedLines, baseFindings });
    if (json) stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    else {
      for (const warning of report.warnings) stdout.write(`warning ${warning.ruleId} ${warning.scope}: ${warning.count}/${warning.baselineCount} - ${warning.message} (${warning.followUpIssue})\n`);
      for (const violation of report.violations) stderr.write(`error ${violation.ruleId} ${violation.path}:${violation.line} - ${violation.message}\n  ${violation.remediation}\n  fingerprint: ${violation.fingerprint}\n`);
      stdout.write(`Frontend guard ${report.passed ? "PASS" : "FAIL"}: ${report.violations.length} violation(s), ${report.warnings.length} baseline warning(s).\n`);
    }
    return { exitCode: report.passed ? 0 : 1, report };
  } catch (error) {
    const code = error instanceof FrontendGuardError ? error.code : "UNEXPECTED";
    stderr.write(`FrontendGuardError[${code}]: ${error.message}\n`);
    return { exitCode: 1, error };
  }
}

function invokedDirectly() {
  return process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url;
}

if (invokedDirectly()) {
  const json = process.argv.includes("--json");
  const result = await runFrontendGuardCli({ json });
  process.exitCode = result.exitCode;
}

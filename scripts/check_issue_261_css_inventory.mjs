import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(SCRIPT_DIR, "..");
const OUTPUT = join(
  ROOT,
  "docs",
  "17-evidence",
  "issue-261-css-selector-inventory.json",
);

const LEGACY_CSS = [
  "apps/web/src/styles.css",
  "apps/web/src/design/layout.css",
];

const COMPLETED_M1A0 = {
  id: "M1A0-modeling-data-same-selector-overlap",
  historicalMemberIds: [
    "CSS-0979",
    "CSS-0997",
    "CSS-0998",
    "CSS-1041",
    "CSS-1052",
    "CSS-1053",
    "CSS-1054",
    "CSS-1055",
    "CSS-1081",
    "CSS-1207",
    "CSS-1495",
    "CSS-1499",
  ],
  exactLegacySelectors: [
    ".data-mapping-resolved",
    ".data-source-decision-grid",
    ".data-mapping-decision .data-mapping-table",
    ".data-mapping-decision .data-mapping-table table",
    ".data-mapping-decision .data-mapping-table th",
    ".data-mapping-decision .data-mapping-table td",
    ".data-source-advanced > summary",
    ".modeling-data-plot-panel",
  ],
};

const COMPLETED_M1A1 = {
  id: "M1A1-modeling-data-source-tabs",
  historicalMemberIds: [
    "CSS-0971",
    "CSS-0972",
    "CSS-0973",
    "CSS-0974",
    "CSS-0975",
  ],
  exactLegacySelectors: [
    ".data-source-tabs",
    ".data-source-tabs button",
    ".data-source-tabs button[aria-selected=\"true\"]",
    ".data-source-tabs button:hover",
    ".data-source-tabs button:focus-visible",
  ],
};

const COMPLETED_M1A2 = {
  id: "M1A2-modeling-data-component-region",
  historicalMemberIds: [
    "CSS-1060",
    "CSS-1068",
    "CSS-1069",
  ],
  exactLegacySelectors: [
    ".data-source-advanced",
    ".data-source-advanced > div",
    ".data-source-advanced code",
  ],
};

const MAIN_CSS_ORDER = [
  "apps/web/src/styles.css",
  "apps/web/src/design/tokens.css",
  "apps/web/src/design/typography.css",
  "apps/web/src/design/primitives.css",
  "apps/web/src/design/layout.css",
  "apps/web/src/design/shell.css",
];

const OWNER_TARGET = {
  "shared-token-density-typography": "apps/web/src/design/tokens.css or typography.css",
  "shared-application-shell": "apps/web/src/design/shell.css",
  "shared-pane-split-layout": "apps/web/src/design/layout.css",
  "shared-form-table-plot-primitive": "apps/web/src/design/primitives.css",
  "modeling-specific": "apps/web/src/features/modeling/ui (stage-owned CSS)",
  "materials-specific": "apps/web/src/features/materials/ui/materials.css (planned)",
  "administration-specific": "apps/web/src/features/administration/ui/administration.css (planned)",
  "activity-specific": "apps/web/src/features/activity/ui/activity.css (planned)",
  "legacy-cross-feature": "split by proven consumer; never copy the selector",
  "unresolved-legacy": "hold until live consumer proof identifies an owner",
};

const ROUTES = {
  shared: ["all authenticated routes"],
  modeling: ["/modeling?stage=data|process|fit|export", "/datasets/processing"],
  modelingData: ["/modeling?stage=data", "/datasets/processing?stage=data"],
  modelingProcess: ["/modeling?stage=process", "/datasets/processing?stage=process"],
  modelingFit: ["/modeling?stage=fit", "/datasets/processing?stage=fit"],
  modelingExport: ["/modeling?stage=export", "/datasets/processing?stage=export"],
  materials: [
    "/materials",
    "/materials/:material[/overview|properties|curves|cards|evidence]",
    "/materials/records/:record/revisions/:revision",
    "/materials/:material/cards/:card",
  ],
  administration: [
    "/administration[/database|schema-bundles|records|access]",
    "/catalog/schema",
    "/catalog/records",
    "/catalog/explorer[/records/:record/revisions/:revision]",
  ],
  activity: ["/activity", "/jobs-reviews"],
};

const STATE_WORDS = [
  "active",
  "blocked",
  "calculating",
  "checked",
  "closed",
  "collapsed",
  "current",
  "danger",
  "delivered",
  "denied",
  "disabled",
  "draft",
  "empty",
  "error",
  "expanded",
  "failed",
  "focus",
  "hover",
  "invalid",
  "loading",
  "normal",
  "open",
  "pending",
  "pressed",
  "preview",
  "ready",
  "recovery",
  "released",
  "review",
  "saved",
  "selected",
  "stale",
  "success",
  "unsupported",
  "visible",
  "hidden",
  "warning",
];

const RAW_COLOR = /(?:#[0-9a-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)\s*\()/i;
const SOURCE_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".html"]);

function posix(path) {
  return path.split(sep).join("/");
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function normalizeSpace(value) {
  return value.replace(/\s+/g, " ").trim();
}

function lineAt(source, offset) {
  let line = 1;
  for (let index = 0; index < offset; index += 1) {
    if (source[index] === "\n") line += 1;
  }
  return line;
}

function stripCommentsPreserveLines(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, (comment) =>
    comment.replace(/[^\n]/g, " "),
  );
}

function splitTopLevel(value, delimiter = ",") {
  const parts = [];
  let start = 0;
  let quote = null;
  let round = 0;
  let square = 0;
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index];
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
  parts.push(value.slice(start).trim());
  return parts.filter(Boolean);
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
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if (character === "(") round += 1;
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

function parseCss(path, source, loadRank) {
  const clean = stripCommentsPreserveLines(source);
  const rules = [];
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
      const rawPrelude = clean.slice(tokenStart, index);
      const prelude = rawPrelude.trim();
      const leading = rawPrelude.search(/\S|$/);
      const atContext = stack
        .filter((entry) => entry.type === "at")
        .map((entry) => normalizeSpace(entry.prelude));
      stack.push({
        type: prelude.startsWith("@") ? "at" : "rule",
        prelude,
        atContext,
        line: lineAt(clean, tokenStart + leading),
        bodyStart: index + 1,
      });
      tokenStart = index + 1;
      continue;
    }
    if (character === "}") {
      const entry = stack.pop();
      if (entry?.type === "rule" && entry.prelude) {
        const declarations = parseDeclarations(clean.slice(entry.bodyStart, index));
        const ruleIndex = rules.length + 1;
        for (const [selectorIndex, selector] of splitTopLevel(entry.prelude).entries()) {
          rules.push({
            path,
            line: entry.line,
            ruleIndex,
            selectorIndex: selectorIndex + 1,
            selector: normalizeSpace(selector),
            atContext: entry.atContext,
            declarations,
            loadRank,
          });
        }
      }
      tokenStart = index + 1;
    }
  }
  if (stack.length) throw new Error(`${path}: unclosed CSS block`);
  return rules;
}

function balancedFunction(selector, start) {
  let depth = 0;
  let quote = null;
  for (let index = start; index < selector.length; index += 1) {
    const character = selector[index];
    if (quote) {
      if (character === "\\") index += 1;
      else if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'") quote = character;
    else if (character === "(") depth += 1;
    else if (character === ")") {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  return selector.length - 1;
}

function addSpecificity(left, right) {
  return [left[0] + right[0], left[1] + right[1], left[2] + right[2]];
}

function compareSpecificity(left, right) {
  return left[0] - right[0] || left[1] - right[1] || left[2] - right[2];
}

function specificity(selector) {
  let result = [0, 0, 0];
  let cleaned = "";
  for (let index = 0; index < selector.length; index += 1) {
    const functional = /^:(where|is|not|has)\(/i.exec(selector.slice(index));
    if (functional) {
      const open = index + functional[0].length - 1;
      const close = balancedFunction(selector, open);
      const args = splitTopLevel(selector.slice(open + 1, close));
      if (functional[1].toLowerCase() !== "where") {
        const argSpecificities = args.map(specificity);
        const maximum = argSpecificities.sort(compareSpecificity).at(-1) ?? [0, 0, 0];
        result = addSpecificity(result, maximum);
      }
      index = close;
      cleaned += " ";
      continue;
    }
    cleaned += selector[index];
  }
  const attributesRemoved = cleaned.replace(/\[[^\]]*\]/g, (match) => {
    result[1] += 1;
    return " ";
  });
  const idsRemoved = attributesRemoved.replace(/#[a-z_-][\w-]*/gi, (match) => {
    result[0] += 1;
    return " ";
  });
  const classesRemoved = idsRemoved.replace(/\.[a-z_-][\w-]*/gi, (match) => {
    result[1] += 1;
    return " ";
  });
  const pseudoElementsRemoved = classesRemoved.replace(/::[a-z_-][\w-]*/gi, (match) => {
    result[2] += 1;
    return " ";
  });
  const pseudoClassesRemoved = pseudoElementsRemoved.replace(/:(?!:)[a-z_-][\w-]*(?:\([^)]*\))?/gi, (match) => {
    result[1] += 1;
    return " ";
  });
  const typeCandidates = pseudoClassesRemoved
    .replace(/[>+~*,|]/g, " ")
    .split(/\s+/)
    .filter((token) => /^(?:[a-z][\w-]*|\*)$/i.test(token) && token !== "*");
  result[2] += typeCandidates.length;
  return result;
}

function selectorClasses(selector) {
  return [...selector.matchAll(/\.([a-z_-][\w-]*)/gi)].map((match) => match[1]);
}

function selectorIds(selector) {
  return [...selector.matchAll(/#([a-z_-][\w-]*)/gi)].map((match) => match[1]);
}

function subjectSelector(selector) {
  let result = "";
  for (let index = 0; index < selector.length; index += 1) {
    const functional = /^:(?:where|is|not|has)\(/i.exec(selector.slice(index));
    if (functional) {
      const open = index + functional[0].length - 1;
      index = balancedFunction(selector, open);
      continue;
    }
    result += selector[index];
  }
  return result;
}

function targetKey(selector) {
  const subject = subjectSelector(selector);
  const ids = selectorIds(subject);
  if (ids.length) return `#${ids.at(-1)}`;
  const classes = selectorClasses(subject);
  if (classes.length) return `.${classes.at(-1)}`;
  if (/:root\b/.test(subject)) return ":root";
  const type = /(?:^|[>+~\s])([a-z][\w-]*)\s*(?::[-\w]+(?:\([^)]*\))?)*\s*$/i.exec(subject);
  return type ? type[1].toLowerCase() : normalizeSpace(subject);
}

function collectFiles(directory) {
  const files = [];
  for (const name of readdirSync(directory)) {
    const absolute = join(directory, name);
    const stats = statSync(absolute);
    if (stats.isDirectory()) files.push(...collectFiles(absolute));
    else files.push(absolute);
  }
  return files;
}

export function quotedLiterals(source) {
  const values = [];
  const patterns = [
    /"((?:\\.|[^"\\])*)"/g,
    /'((?:\\.|[^'\\])*)'/g,
    /`((?:\\.|[^`\\])*)`/g,
  ];
  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) values.push(match[1]);
  }
  return values;
}

function staticTemplateText(value) {
  return value.replace(/\$\{[\s\S]*?\}/g, " ");
}

function whitespaceClassTokens(value) {
  const tokens = new Set();
  const staticValue = staticTemplateText(value);
  for (const match of staticValue.matchAll(/(?:^|\s)([a-z_](?:[\w-]*[a-z0-9_])?)(?=\s|$)/gi)) {
    tokens.add(match[1]);
  }
  return tokens;
}

function selectorReferenceTokens(value) {
  const tokens = whitespaceClassTokens(value);
  for (const match of value.matchAll(/\.([a-z_-][\w-]*)/gi)) tokens.add(match[1]);
  return tokens;
}

function assignmentValue(source, start) {
  let index = start;
  while (/\s/.test(source[index] ?? "")) index += 1;
  const first = source[index];
  if (first === '"' || first === "'" || first === "`") {
    const quote = first;
    for (let cursor = index + 1; cursor < source.length; cursor += 1) {
      if (source[cursor] === "\\") cursor += 1;
      else if (source[cursor] === quote) return source.slice(index, cursor + 1);
    }
    return source.slice(index);
  }
  if (first !== "{") return "";
  let depth = 0;
  let quote = null;
  for (let cursor = index; cursor < source.length; cursor += 1) {
    const character = source[cursor];
    if (quote) {
      if (character === "\\") cursor += 1;
      else if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'" || character === "`") {
      quote = character;
      continue;
    }
    if (character === "{") depth += 1;
    else if (character === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(index, cursor + 1);
    }
  }
  return source.slice(index);
}

export function sourceClassEvidence(source) {
  const producerTokens = new Set();
  const referenceTokens = new Set();
  for (const literal of quotedLiterals(source)) {
    for (const token of selectorReferenceTokens(literal)) referenceTokens.add(token);
  }
  const assignment = /\b(?:className|[a-z_][\w]*ClassName)\s*=/gi;
  for (const match of source.matchAll(assignment)) {
    const expression = assignmentValue(source, match.index + match[0].length);
    for (const literal of quotedLiterals(expression)) {
      for (const token of whitespaceClassTokens(literal)) producerTokens.add(token);
    }
  }
  return { producerTokens, referenceTokens };
}

export function isZeroProductionConsumerCandidate(subjectToken, consumers) {
  return Boolean(subjectToken)
    && consumers.productionProducers.length === 0
    && consumers.productionReferences.length === 0;
}

function classLiteralIndex() {
  const sourceRoot = join(ROOT, "apps", "web", "src");
  const index = new Map();
  const files = collectFiles(sourceRoot)
    .filter((path) => SOURCE_EXTENSIONS.has(extname(path)))
    .sort();
  for (const absolute of files) {
    const path = posix(relative(ROOT, absolute));
    const kind = /\.(?:test|stories)\.[^.]+$/.test(path) ? "test" : "production";
    const evidence = sourceClassEvidence(readFileSync(absolute, "utf8"));
    for (const token of evidence.producerTokens) {
      if (!index.has(token)) index.set(token, { productionProducers: [], productionReferences: [], testProducers: [], testReferences: [] });
      index.get(token)[kind === "production" ? "productionProducers" : "testProducers"].push(path);
    }
    for (const token of evidence.referenceTokens) {
      if (!index.has(token)) index.set(token, { productionProducers: [], productionReferences: [], testProducers: [], testReferences: [] });
      index.get(token)[kind === "production" ? "productionReferences" : "testReferences"].push(path);
    }
  }
  for (const consumers of index.values()) {
    for (const key of Object.keys(consumers)) consumers[key] = [...new Set(consumers[key])].sort();
  }
  return index;
}

function fileOwner(path) {
  if (path.includes("/design/")) return "shared";
  if (/modeling|processing|fit-|curve-plot|calibration|viscoelastic|ogden|elastoplastic|hyperelastic|tensile|shear-relaxation/.test(path)) return "modeling";
  if (/material-library|materials-|material-datasheet|exact-domain|solver-card-delivery|domain-workflow/.test(path)) return "materials";
  if (/activity|review-request|release-workbench|governance-evidence|operations-dashboard/.test(path)) return "activity";
  if (/administration|catalog|schema-definition|configurable|product-access/.test(path)) return "administration";
  return "unresolved";
}

function keywordOwner(selector) {
  const value = selector.toLowerCase();
  if (/modeling|processing|process-|fit-|export-|curve-|data-intake|data-source|workflow-step|calibration|viscoelastic|ogden|elastoplastic|hyperelastic/.test(value)) return "modeling";
  if (/activity|review-|release-|operation-|job-|approval/.test(value)) return "activity";
  if (/administration|admin-|catalog-schema|schema-|attribute-|subset-|link-type|access-|permission/.test(value)) return "administration";
  if (/materials|material-|datasheet|browse-|card-preview|solver-card-preview|record-result/.test(value)) return "materials";
  return "unresolved";
}

function sharedOwner(selector) {
  const value = selector.toLowerCase();
  if (/^:root$|data-density|density-|typography|ux-(?:meta|kicker|label|value)|semantic-text/.test(value)) return "shared-token-density-typography";
  if (/application-(?:shell|workspace|navigation)|primary-navigation|command-bar|status-bar|session-shell|shell-/.test(value)) return "shared-application-shell";
  if (/^\.ux-page\b|resizable|resize-handle|split-pane|pane-divider|workspace-layout|engineering-pane|column-resize/.test(value)) return "shared-pane-split-layout";
  if (/^(?:html|body|button|input|select|textarea|table|thead|tbody|tr|th|td|label|form|main)(?:\b|:)|\.(?:button|form-grid|field|table|plot|content-card|loading-state|empty-state|error-banner|success-banner|engineering-section|engineering-plot)/.test(value)) return "shared-form-table-plot-primitive";
  return null;
}

function classifyOwner(selector, productionConsumerFiles) {
  const shared = sharedOwner(selector);
  if (shared) return shared;
  const owners = new Set(productionConsumerFiles.map(fileOwner).filter((owner) => owner !== "unresolved"));
  const keyword = keywordOwner(selector);
  if (keyword !== "unresolved" && (owners.size === 0 || (owners.size === 1 && owners.has("shared")))) {
    owners.clear();
    owners.add(keyword);
  }
  if (owners.size > 1) return "legacy-cross-feature";
  const only = [...owners][0] ?? "unresolved";
  if (only === "modeling") return "modeling-specific";
  if (only === "materials") return "materials-specific";
  if (only === "administration") return "administration-specific";
  if (only === "activity") return "activity-specific";
  if (only === "shared") return "shared-form-table-plot-primitive";
  return "unresolved-legacy";
}

function routesForFeatureOwner(owner) {
  if (owner === "modeling") return ROUTES.modeling;
  if (owner === "materials") return ROUTES.materials;
  if (owner === "administration") return ROUTES.administration;
  if (owner === "activity") return ROUTES.activity;
  return [];
}

function ownerRoutes(owner, productionConsumerFiles, selector) {
  if (owner.startsWith("shared-")) return ROUTES.shared;
  if (owner === "modeling-specific") {
    const value = selector.toLowerCase();
    if (/data-|data\b|intake|library/.test(value)) return ROUTES.modelingData;
    if (/process/.test(value)) return ROUTES.modelingProcess;
    if (/fit/.test(value)) return ROUTES.modelingFit;
    if (/export|solver|target-preview/.test(value)) return ROUTES.modelingExport;
    return ROUTES.modeling;
  }
  if (owner === "materials-specific") return ROUTES.materials;
  if (owner === "administration-specific") return ROUTES.administration;
  if (owner === "activity-specific") return ROUTES.activity;
  const featureOwners = new Set(
    productionConsumerFiles
      .map(fileOwner)
      .filter((candidate) => !["shared", "unresolved"].includes(candidate)),
  );
  const keyword = keywordOwner(selector);
  if (keyword !== "unresolved") featureOwners.add(keyword);
  if (featureOwners.size) {
    return [...new Set([...featureOwners].sort().flatMap(routesForFeatureOwner))];
  }
  return ["unresolved until live consumer characterization"];
}

function selectorStates(selector) {
  const lower = selector.toLowerCase();
  const states = new Set();
  for (const word of STATE_WORDS) {
    if (new RegExp(`(?:^|[-_.:#\\[=\"'])${word}(?:$|[-_.:#\\]=\"'])`).test(lower)) states.add(word);
  }
  for (const match of lower.matchAll(/:(hover|focus|focus-visible|focus-within|checked|disabled|active|open|invalid|required|empty|target)\b/g)) states.add(match[1]);
  if (lower.includes(".modeling-data-plot-panel")) {
    states.add("dataLayoutMode=compact|content-fit");
    states.add("ResizeObserver available");
  }
  if (states.size === 0) states.add("normal/base");
  return [...states].sort();
}

function migrationBatch(owner, selector, deadCandidate) {
  if (deadCandidate) return "M6-zero-consumer-removal-candidate";
  if (owner === "modeling-specific") {
    if (/data-|data\b|intake|library/.test(selector)) return "M1A-modeling-data";
    if (/process/.test(selector)) return "M1B-modeling-process";
    if (/fit/.test(selector)) return "M1C-modeling-fit";
    if (/export|solver|target-preview/.test(selector)) return "M1D-modeling-export";
    return "M1E-modeling-shell-and-family";
  }
  if (owner === "materials-specific") return "M2-materials";
  if (owner === "administration-specific") return "M3A-administration";
  if (owner === "activity-specific") return "M3B-activity";
  if (owner.startsWith("shared-")) return "M4-shared-cleanup";
  return "HOLD-owner-or-cross-feature-split";
}

function makeInventory() {
  const sourceRoot = join(ROOT, "apps", "web", "src");
  const cssFiles = collectFiles(join(ROOT, "apps", "web", "src"))
    .filter((path) => extname(path) === ".css")
    .map((absolute) => posix(relative(ROOT, absolute)))
    .sort();
  const allRules = [];
  for (const path of cssFiles) {
    const source = readFileSync(join(ROOT, path), "utf8");
    const loadRank = MAIN_CSS_ORDER.indexOf(path);
    allRules.push(...parseCss(path, source, loadRank < 0 ? null : loadRank));
  }
  const legacyRules = allRules.filter((rule) => LEGACY_CSS.includes(rule.path));
  const literalIndex = classLiteralIndex();
  const emptyConsumerEvidence = {
    productionProducers: [],
    productionReferences: [],
    testProducers: [],
    testReferences: [],
  };
  const rows = legacyRules.map((rule, index) => {
    const classes = selectorClasses(rule.selector);
    const ids = selectorIds(rule.selector);
    const subject = targetKey(rule.selector);
    const subjectToken = /^[.#]/.test(subject) ? subject.slice(1) : null;
    const subjectConsumers = subjectToken
      ? literalIndex.get(subjectToken) ?? emptyConsumerEvidence
      : emptyConsumerEvidence;
    const allTokenProductionFiles = [...new Set(
      [...classes, ...ids].flatMap((token) => {
        const evidence = literalIndex.get(token) ?? emptyConsumerEvidence;
        return [...evidence.productionProducers, ...evidence.productionReferences];
      }),
    )].sort();
    const productionConsumerFiles = subjectConsumers.productionProducers.length
      ? subjectConsumers.productionProducers
      : subjectConsumers.productionReferences.length
        ? subjectConsumers.productionReferences
        : allTokenProductionFiles;
    const owner = classifyOwner(rule.selector, productionConsumerFiles);
    const declarationSignature = sha256(
      JSON.stringify(rule.declarations.map(({ property, value, important }) => [property, value, important])),
    );
    const deadCandidate = isZeroProductionConsumerCandidate(subjectToken, subjectConsumers);
    const atText = rule.atContext.join(" | ");
    const wideRouteOverride = /@(?:media|container)[^{]*(?:min-width\s*:\s*(?:1[6-9]\d\d|[2-9]\d{3})px|width\s*>?=\s*(?:1[6-9]\d\d|[2-9]\d{3})px)/i.test(atText);
    return {
      id: `CSS-${String(index + 1).padStart(4, "0")}`,
      source: {
        path: rule.path,
        line: rule.line,
        ruleIndex: rule.ruleIndex,
        selectorIndex: rule.selectorIndex,
        mainImportRank: rule.loadRank,
        atContext: rule.atContext,
      },
      selector: rule.selector,
      specificity: specificity(rule.selector).join("-"),
      targetKey: subject,
      declarations: {
        properties: [...new Set(rule.declarations.map((item) => item.property))].sort(),
        importantProperties: rule.declarations.filter((item) => item.important).map((item) => item.property),
        signatureSha256: declarationSignature,
      },
      owner: {
        category: owner,
        proposedTarget: OWNER_TARGET[owner],
        migrationBatch: migrationBatch(owner, rule.selector.toLowerCase(), deadCandidate),
      },
      consumers: {
        status: subjectToken
          ? subjectConsumers.productionProducers.length
            ? "production-subject-class-producer-observed"
            : subjectConsumers.productionReferences.length
              ? "production-subject-reference-only"
              : subjectConsumers.testProducers.length
                ? "test-only-subject-class-producer"
                : subjectConsumers.testReferences.length
                  ? "test-only-subject-reference"
                  : "no-subject-class-evidence-observed"
          : "global-or-type-selector",
        subjectToken,
        productionProducerFiles: subjectConsumers.productionProducers,
        productionReferenceFiles: subjectConsumers.productionReferences,
        testProducerFiles: subjectConsumers.testProducers,
        testReferenceFiles: subjectConsumers.testReferences,
        productionFiles: productionConsumerFiles,
        testFiles: [...new Set([
          ...subjectConsumers.testProducers,
          ...subjectConsumers.testReferences,
        ])].sort(),
        routes: ownerRoutes(owner, productionConsumerFiles, rule.selector),
        states: selectorStates(rule.selector),
      },
      flags: {
        legacyGlobal: true,
        deepDescendant: /\s[>+~]?\s*[^,]+\s[>+~]?\s*[^,]+/.test(rule.selector),
        hasPseudo: /:has\(/i.test(rule.selector),
        important: rule.declarations.some((item) => item.important),
        rawColor: rule.declarations.some((item) => RAW_COLOR.test(item.value)),
        literalFontWeight: rule.declarations.some((item) => item.property === "font-weight" && !item.value.includes("var(")),
        deadCandidate,
        routeShellCoupling: /\.application-(?:shell|workspace)[^,{]*:has\(/.test(rule.selector),
        routeSpecificWideWorkaroundCandidate: wideRouteOverride && keywordOwner(rule.selector) !== "unresolved",
        exactSelectorRepeated: false,
        sameContextSelectorConsolidationCandidate: false,
        crossLegacyFileSameSelector: false,
        duplicateCandidate: false,
        crossCssDuplicate: false,
      },
      cascade: {
        exactSelectorGroupIds: [],
        targetPropertyGroupIds: [],
        duplicateOwnedStylePeers: [],
      },
    };
  });

  const wideContextFeature = new Set(
    rows
      .filter((row) => row.flags.routeSpecificWideWorkaroundCandidate)
      .map((row) => `${row.source.path}\0${row.source.atContext.join(" | ")}`),
  );
  for (const row of rows) {
    const contextKey = `${row.source.path}\0${row.source.atContext.join(" | ")}`;
    if (wideContextFeature.has(contextKey)) row.flags.routeSpecificWideWorkaroundCandidate = true;
  }

  const exactGroups = new Map();
  for (const row of rows) {
    const key = normalizeSpace(row.selector);
    if (!exactGroups.has(key)) exactGroups.set(key, []);
    exactGroups.get(key).push(row);
  }
  const exactSelectorGroups = [];
  for (const [selector, members] of exactGroups) {
    if (members.length < 2) continue;
    const id = `EXACT-${String(exactSelectorGroups.length + 1).padStart(4, "0")}`;
    const signatures = new Set(members.map((row) => row.declarations.signatureSha256));
    const contexts = new Set(members.map((row) => row.source.atContext.join(" | ")));
    exactSelectorGroups.push({
      id,
      selector,
      memberIds: members.map((row) => row.id),
      crossLegacyFile: new Set(members.map((row) => row.source.path)).size > 1,
      identicalDeclarations: signatures.size === 1,
      identicalAtContext: contexts.size === 1,
    });
    for (const row of members) {
      row.cascade.exactSelectorGroupIds.push(id);
      row.flags.exactSelectorRepeated = true;
      if (contexts.size === 1) row.flags.sameContextSelectorConsolidationCandidate = true;
      if (new Set(members.map((member) => member.source.path)).size > 1) row.flags.crossLegacyFileSameSelector = true;
      if (signatures.size === 1 && contexts.size === 1) row.flags.duplicateCandidate = true;
    }
  }

  const targetPropertyMap = new Map();
  for (const row of rows) {
    if (!/^[.#]/.test(row.targetKey)) continue;
    for (const property of row.declarations.properties) {
      const key = `${row.targetKey}\0${property}`;
      if (!targetPropertyMap.has(key)) targetPropertyMap.set(key, []);
      targetPropertyMap.get(key).push(row.id);
    }
  }
  const targetPropertyGroups = [];
  for (const [key, memberIds] of targetPropertyMap) {
    if (memberIds.length < 2) continue;
    const [target, property] = key.split("\0");
    const id = `TARGET-${String(targetPropertyGroups.length + 1).padStart(4, "0")}`;
    targetPropertyGroups.push({ id, targetKey: target, property, memberIds });
    for (const memberId of memberIds) rows[Number(memberId.slice(4)) - 1].cascade.targetPropertyGroupIds.push(id);
  }

  const nonLegacyRules = allRules.filter((rule) => !LEGACY_CSS.includes(rule.path));
  const nonLegacyBySelector = new Map();
  for (const rule of nonLegacyRules) {
    const key = normalizeSpace(rule.selector);
    if (!nonLegacyBySelector.has(key)) nonLegacyBySelector.set(key, []);
    nonLegacyBySelector.get(key).push(rule);
  }
  for (const row of rows) {
    const peers = nonLegacyBySelector.get(normalizeSpace(row.selector)) ?? [];
    row.cascade.duplicateOwnedStylePeers = peers
      .map((peer) => ({
        path: peer.path,
        line: peer.line,
        mainImportRank: peer.loadRank,
        atContext: peer.atContext,
        properties: [...new Set(peer.declarations.map((item) => item.property))].sort(),
        importantProperties: peer.declarations.filter((item) => item.important).map((item) => item.property),
        declarationSignatureSha256: sha256(JSON.stringify(peer.declarations.map(({ property, value, important }) => [property, value, important]))),
      }))
      .sort((left, right) => left.path.localeCompare(right.path) || left.line - right.line);
    row.flags.crossCssDuplicate = peers.length > 0;
  }

  const countBy = (items, getKey) => Object.fromEntries(
    [...items.reduce((map, item) => {
      const key = getKey(item);
      map.set(key, (map.get(key) ?? 0) + 1);
      return map;
    }, new Map())].sort(([left], [right]) => left.localeCompare(right)),
  );
  const flagCounts = {};
  for (const name of Object.keys(rows[0].flags)) flagCounts[name] = rows.filter((row) => row.flags[name]).length;
  const sourceCodeFiles = collectFiles(sourceRoot).filter((path) => SOURCE_EXTENSIONS.has(extname(path)));
  const stylesheetImporters = new Map(cssFiles.map((path) => [path, []]));
  for (const absolute of sourceCodeFiles) {
    const importer = posix(relative(ROOT, absolute));
    const source = readFileSync(absolute, "utf8");
    for (const match of source.matchAll(/import\s+["']([^"']+\.css)["']/g)) {
      const imported = posix(relative(ROOT, resolve(dirname(absolute), match[1])));
      if (stylesheetImporters.has(imported)) stylesheetImporters.get(imported).push(importer);
    }
  }
  const allStylesheets = Object.fromEntries(cssFiles.map((path) => {
    const source = readFileSync(join(ROOT, path), "utf8");
    const fileRules = allRules.filter((rule) => rule.path === path);
    return [path, {
      legacyGlobal: LEGACY_CSS.includes(path),
      mainImportRank: MAIN_CSS_ORDER.indexOf(path) < 0 ? null : MAIN_CSS_ORDER.indexOf(path),
      importers: [...new Set(stylesheetImporters.get(path))].sort(),
      bytes: Buffer.byteLength(source),
      lines: source.split(/\r?\n/).length - (source.endsWith("\n") ? 1 : 0),
      cssRuleGroups: new Set(fileRules.map((rule) => rule.ruleIndex)).size,
      selectorRows: fileRules.length,
      sha256: sha256(source),
    }];
  }));
  const sourceFiles = Object.fromEntries(
    LEGACY_CSS.map((path) => {
      const source = readFileSync(join(ROOT, path), "utf8");
      return [path, { bytes: Buffer.byteLength(source), lines: source.split(/\r?\n/).length - (source.endsWith("\n") ? 1 : 0), sha256: sha256(source) }];
    }),
  );
  const sourceSha = execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
  const mergeBaseSha = execFileSync("git", ["merge-base", "origin/main", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
  const cssRuleGroupCount = legacyRules.reduce(
    (set, rule) => set.add(`${rule.path}:${rule.ruleIndex}`),
    new Set(),
  ).size;
  const completedPacketResidualRows = new Map([
    [
      COMPLETED_M1A0.id,
      rows.filter((row) => COMPLETED_M1A0.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A1.id,
      rows.filter((row) => COMPLETED_M1A1.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A2.id,
      rows.filter((row) => COMPLETED_M1A2.exactLegacySelectors.includes(row.selector)),
    ],
  ]);
  return {
    schemaVersion: "cmp.issue-261.css-selector-inventory.v1",
    sourceSha,
    mergeBaseSha,
    branch: execFileSync("git", ["branch", "--show-current"], { cwd: ROOT, encoding: "utf8" }).trim(),
    scope: {
      legacyStylesheets: LEGACY_CSS,
      mainCssImportOrder: MAIN_CSS_ORDER,
      sourceFiles,
      allStylesheets,
      method: "Static CSS parse plus production/test class-producer and reference search across quoted JSX/TS literals, including template and conditional branches. Zero-producer entries remain candidates until a migration unit supplies live DOM and bundle zero-consumer proof.",
    },
    summary: {
      selectorRows: rows.length,
      cssRuleGroups: cssRuleGroupCount,
      bySourceFile: countBy(rows, (row) => row.source.path),
      ruleGroupsBySourceFile: Object.fromEntries(LEGACY_CSS.map((path) => [path, allStylesheets[path].cssRuleGroups])),
      byOwner: countBy(rows, (row) => row.owner.category),
      byMigrationBatch: countBy(rows, (row) => row.owner.migrationBatch),
      byConsumerStatus: countBy(rows, (row) => row.consumers.status),
      flags: flagCounts,
      exactSelectorCascadeGroups: exactSelectorGroups.length,
      targetPropertyCascadeGroups: targetPropertyGroups.length,
    },
    selectors: rows,
    cascadeGroups: {
      exactSelector: exactSelectorGroups,
      targetProperty: targetPropertyGroups,
    },
    migrationPlan: {
      completedBoundedUnits: [
        {
          id: COMPLETED_M1A0.id,
          historicalMemberIds: COMPLETED_M1A0.historicalMemberIds,
          selectorRowsRemoved: 12,
          touchedRuleGroups: 11,
          fullyRemovedRuleGroups: 8,
          partiallyShrunkRuleGroups: 3,
          exactLegacySelectors: COMPLETED_M1A0.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A0.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2826,
            selectorRows: 3573,
            crossCssDuplicateRows: 13,
          },
        },
        {
          id: COMPLETED_M1A1.id,
          historicalMemberIds: COMPLETED_M1A1.historicalMemberIds,
          selectorRowsRemoved: 5,
          touchedRuleGroups: 5,
          fullyRemovedRuleGroups: 5,
          partiallyShrunkRuleGroups: 0,
          exactLegacySelectors: COMPLETED_M1A1.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A1.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2821,
            selectorRows: 3568,
            crossCssDuplicateRows: 13,
          },
        },
        {
          id: COMPLETED_M1A2.id,
          historicalMemberIds: COMPLETED_M1A2.historicalMemberIds,
          selectorRowsRemoved: 3,
          touchedRuleGroups: 3,
          fullyRemovedRuleGroups: 3,
          partiallyShrunkRuleGroups: 0,
          exactLegacySelectors: COMPLETED_M1A2.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A2.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: cssRuleGroupCount,
            selectorRows: rows.length,
            crossCssDuplicateRows: flagCounts.crossCssDuplicate,
          },
        },
      ],
      nextBoundedUnit: {
        id: "M1A3-modeling-data-component-region",
        status: "owner-packet-required",
        scope: "Select one remaining M1A Data component region from the regenerated inventory; do not migrate all remaining M1A rows together.",
      },
    },
  };
}

function validateInventory(inventory) {
  const errors = [];
  const rows = inventory.selectors;
  const rowById = new Map(rows.map((row) => [row.id, row]));
  if (rowById.size !== rows.length) errors.push("selector ids are not unique");
  const ownerTotal = Object.values(inventory.summary.byOwner).reduce((total, count) => total + count, 0);
  const batchTotal = Object.values(inventory.summary.byMigrationBatch).reduce((total, count) => total + count, 0);
  if (ownerTotal !== rows.length) errors.push(`owner total ${ownerTotal} != ${rows.length}`);
  if (batchTotal !== rows.length) errors.push(`batch total ${batchTotal} != ${rows.length}`);
  for (const row of rows) {
    const expectedDeadCandidate = isZeroProductionConsumerCandidate(
      row.consumers.subjectToken,
      {
        productionProducers: row.consumers.productionProducerFiles,
        productionReferences: row.consumers.productionReferenceFiles,
      },
    );
    if (row.flags.deadCandidate !== expectedDeadCandidate) {
      errors.push(`${row.id} dead-candidate flag disagrees with production evidence`);
    }
    if (row.flags.deadCandidate !== (row.owner.migrationBatch === "M6-zero-consumer-removal-candidate")) {
      errors.push(`${row.id} dead-candidate flag disagrees with migration batch`);
    }
  }
  const completed = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A0.id,
  );
  if (!completed) {
    errors.push("completed M1A0 packet is missing");
  } else {
    if (completed.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A0 selectors remain in legacy CSS: ${completed.residualExactSelectorRows.join(", ")}`);
    }
    if (completed.selectorRowsRemoved !== 12
        || completed.touchedRuleGroups !== 11
        || completed.fullyRemovedRuleGroups !== 8
        || completed.partiallyShrunkRuleGroups !== 3) {
      errors.push("completed M1A0 structural delta does not match the approved 12/11/8/3 packet");
    }
    if (completed.actualAfter.cssRuleGroups !== 2826
        || completed.actualAfter.selectorRows !== 3573
        || completed.actualAfter.crossCssDuplicateRows !== 13) {
      errors.push(`completed M1A0 actual delta is ${JSON.stringify(completed.actualAfter)}`);
    }
  }
  const completedM1A1 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A1.id,
  );
  if (!completedM1A1) {
    errors.push("completed M1A1 packet is missing");
  } else {
    if (completedM1A1.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A1 selectors remain in legacy CSS: ${completedM1A1.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A1.selectorRowsRemoved !== 5
        || completedM1A1.touchedRuleGroups !== 5
        || completedM1A1.fullyRemovedRuleGroups !== 5
        || completedM1A1.partiallyShrunkRuleGroups !== 0) {
      errors.push("completed M1A1 structural delta does not match the approved 5/5/5/0 packet");
    }
    if (completedM1A1.actualAfter.cssRuleGroups !== 2821
        || completedM1A1.actualAfter.selectorRows !== 3568
        || completedM1A1.actualAfter.crossCssDuplicateRows !== 13) {
      errors.push(`completed M1A1 actual delta is ${JSON.stringify(completedM1A1.actualAfter)}`);
    }
  }
  const completedM1A2 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A2.id,
  );
  if (!completedM1A2) {
    errors.push("completed M1A2 packet is missing");
  } else {
    if (completedM1A2.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A2 selectors remain in legacy CSS: ${completedM1A2.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A2.selectorRowsRemoved !== 3
        || completedM1A2.touchedRuleGroups !== 3
        || completedM1A2.fullyRemovedRuleGroups !== 3
        || completedM1A2.partiallyShrunkRuleGroups !== 0) {
      errors.push("completed M1A2 structural delta does not match the approved 3/3/3/0 packet");
    }
    if (completedM1A2.actualAfter.cssRuleGroups !== 2818
        || completedM1A2.actualAfter.selectorRows !== 3565
        || completedM1A2.actualAfter.crossCssDuplicateRows !== 13) {
      errors.push(`completed M1A2 actual delta is ${JSON.stringify(completedM1A2.actualAfter)}`);
    }
  }
  for (const group of inventory.cascadeGroups.exactSelector) {
    const members = group.memberIds.map((id) => rowById.get(id));
    if (members.some((member) => !member)) errors.push(`${group.id} references a missing selector`);
    else if (members.some((member) => member.selector !== group.selector)) errors.push(`${group.id} mixes selectors`);
  }
  for (const group of inventory.cascadeGroups.targetProperty) {
    const members = group.memberIds.map((id) => rowById.get(id));
    if (members.some((member) => !member)) errors.push(`${group.id} references a missing selector`);
    else if (members.some((member) => member.targetKey !== group.targetKey || !member.declarations.properties.includes(group.property))) {
      errors.push(`${group.id} mixes target/property members`);
    }
  }
  const baseline = JSON.parse(readFileSync(join(ROOT, "apps", "web", "frontend-guard-baseline.json"), "utf8"));
  const globalDebt = baseline.debt.find((item) => item.ruleId === "CMP-FE-GLOBAL-CSS-SELECTOR" && item.scope === "apps/web/src");
  if (!globalDebt || globalDebt.count !== inventory.summary.cssRuleGroups) {
    errors.push(`guard global debt ${globalDebt?.count ?? "missing"} != inventory rule groups ${inventory.summary.cssRuleGroups}`);
  }
  if (baseline.sourceSha !== inventory.mergeBaseSha) {
    errors.push(`guard sourceSha ${baseline.sourceSha} != merge base ${inventory.mergeBaseSha}`);
  }
  for (const path of LEGACY_CSS) {
    const hotspot = baseline.hotspots.find((item) => item.path === path);
    const lines = inventory.scope.allStylesheets[path].lines;
    if (!hotspot || hotspot.baselineLines !== lines) {
      errors.push(`${path} hotspot lines ${hotspot?.baselineLines ?? "missing"} != source lines ${lines}`);
    }
  }
  if (errors.length) throw new Error(`inventory validation failed: ${errors.join("; ")}`);
}

function serialize(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function runCli() {
  const inventory = makeInventory();
  validateInventory(inventory);
  const rendered = serialize(inventory);
  if (process.argv.includes("--write")) {
    writeFileSync(OUTPUT, rendered, "utf8");
    console.log(`WROTE ${posix(relative(ROOT, OUTPUT))}`);
    console.log(JSON.stringify(inventory.summary, null, 2));
    return;
  }

  if (!existsSync(OUTPUT)) {
    throw new Error(`MISSING ${posix(relative(ROOT, OUTPUT))}; run with --write`);
  }
  const current = readFileSync(OUTPUT, "utf8");
  if (current !== rendered) {
    throw new Error(`STALE ${posix(relative(ROOT, OUTPUT))}; rerun with --write and inspect the source/candidate delta`);
  }
  console.log(`PASS ${posix(relative(ROOT, OUTPUT))}`);
  console.log(JSON.stringify(inventory.summary, null, 2));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  runCli();
}

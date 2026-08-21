import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const FROZEN_BASE = "4d53d95ce926b96b84e47f9d942127f0853d8ed2";
const B1_SOURCE = "a26649ec9d7e689cf773ccad9dedfcb985d9ea62";
const M2_SOURCE = "be5538ec57efdd65f4104fffa733f134b3d42d87";
const M3_SOURCE = "dfc3bf00b5aafac2ac466d662f07ee4be88421eb";
const LEGACY = ["apps/web/src/styles.css", "apps/web/src/design/layout.css"];
const ADMIN_OWNER = "apps/web/src/features/administration/ui/administration.css";
const ACTIVITY_OWNER = "apps/web/src/features/activity/ui/activity.css";

function gitShow(path) {
  return execFileSync("git", ["show", FROZEN_BASE + ":" + path], { cwd: ROOT, encoding: "utf8", maxBuffer: 32 * 1024 * 1024 });
}
function gitShowAt(sourceSha, path) {
  return execFileSync("git", ["show", sourceSha + ":" + path], { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
}
function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}
function normalizeSpace(value) {
  return value.replace(/\s+/g, " ").trim();
}
function splitTopLevel(value, delimiter = ",") {
  const parts = [];
  let from = 0;
  let quote = null;
  let round = 0;
  let square = 0;
  for (let i = 0; i < value.length; i += 1) {
    const c = value[i];
    if (quote) {
      if (c === "\\") i += 1;
      else if (c === quote) quote = null;
      continue;
    }
    if (c === '"' || c === "'") { quote = c; continue; }
    if (c === "(") round += 1;
    else if (c === ")") round = Math.max(0, round - 1);
    else if (c === "[") square += 1;
    else if (c === "]") square = Math.max(0, square - 1);
    else if (c === delimiter && round === 0 && square === 0) {
      parts.push(value.slice(from, i).trim());
      from = i + 1;
    }
  }
  parts.push(value.slice(from).trim());
  return parts.filter(Boolean);
}
function parseDeclarations(body) {
  const declarations = [];
  let from = 0;
  let quote = null;
  let round = 0;
  for (let i = 0; i <= body.length; i += 1) {
    const c = body[i] ?? ";";
    if (quote) {
      if (c === "\\") i += 1;
      else if (c === quote) quote = null;
      continue;
    }
    if (c === '"' || c === "'") { quote = c; continue; }
    if (c === "(") round += 1;
    else if (c === ")") round = Math.max(0, round - 1);
    else if (c === ";" && round === 0) {
      const declaration = body.slice(from, i).trim();
      from = i + 1;
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
function parseCss(path, source) {
  const clean = source.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " "));
  const groups = [];
  const stack = [];
  let tokenStart = 0;
  let quote = null;
  let rowCount = 0;
  for (let i = 0; i < clean.length; i += 1) {
    const c = clean[i];
    if (quote) {
      if (c === "\\") i += 1;
      else if (c === quote) quote = null;
      continue;
    }
    if (c === '"' || c === "'") { quote = c; continue; }
    if (c === ";") { tokenStart = i + 1; continue; }
    if (c === "{") {
      const rawPrelude = clean.slice(tokenStart, i);
      const prelude = rawPrelude.trim();
      const leading = rawPrelude.search(/\S|$/);
      stack.push({
        type: prelude.startsWith("@") ? "at" : "rule",
        prelude,
        atContext: stack.filter((entry) => entry.type === "at").map((entry) => normalizeSpace(entry.prelude)),
        open: i,
        start: tokenStart + leading,
      });
      tokenStart = i + 1;
      continue;
    }
    if (c === "}") {
      const entry = stack.pop();
      if (entry?.type === "rule" && entry.prelude) {
        const selectors = splitTopLevel(entry.prelude);
        const declarations = parseDeclarations(source.slice(entry.open + 1, i));
        const declarationSignature = sha256(JSON.stringify(
          declarations.map(({ property, value, important }) => [property, value, important]),
        ));
        const ruleIndex = rowCount + 1;
        groups.push({
          path,
          ruleIndex,
          selectors: selectors.map((selector, selectorIndex) => ({
            selector: normalizeSpace(selector),
            ruleIndex,
            selectorIndex: selectorIndex + 1,
            atContext: [...entry.atContext],
            declarations,
            declarationSignature,
          })),
        });
        rowCount += selectors.length;
      }
      tokenStart = i + 1;
    }
  }
  return groups;
}
function descriptor(row, path) {
  const sourcePath = path ?? row.path;
  return [sourcePath, normalizeSpace(row.selector), (row.atContext ?? []).join(" | "),
    row.declarationSignature ?? row.declarations?.signatureSha256 ?? ""].join("\0");
}
function selectorDescriptor(row) {
  return [
    row.source?.path ?? row.path,
    normalizeSpace(row.selector),
    (row.source?.atContext ?? row.atContext ?? []).join(" | "),
    row.declarations?.signatureSha256 ?? row.declarationSignature ?? "",
  ].join("\0");
}
function ownerDescriptor(row) {
  return [normalizeSpace(row.selector), (row.atContext ?? []).join(" | "),
    row.declarationSignature ?? row.declarations?.signatureSha256 ?? ""].join("\0");
}
function multiset(rows, key) {
  const result = new Map();
  for (const row of rows) {
    const value = key(row);
    result.set(value, (result.get(value) ?? 0) + 1);
  }
  return result;
}
function equalMultiset(expected, actual, label, errors) {
  const keys = new Set([...expected.keys(), ...actual.keys()]);
  for (const key of keys) {
    const wanted = expected.get(key) ?? 0;
    const found = actual.get(key) ?? 0;
    if (wanted !== found) {
      errors.push(label + ": " + key + " expected " + wanted + ", found " + found);
      if (errors.length > 20) break;
    }
  }
}
function removedDescriptorMultiset(baselineRows, standaloneRows) {
  const baseline = multiset(baselineRows, (row) => selectorDescriptor(row));
  const standalone = multiset(standaloneRows, (row) => selectorDescriptor(row));
  const removed = new Map();
  for (const [key, count] of baseline) {
    const delta = count - (standalone.get(key) ?? 0);
    if (delta > 0) removed.set(key, delta);
  }
  return removed;
}
function addAcceptedDescriptors(target, source, label, errors) {
  for (const [key, count] of source) {
    if (target.has(key)) errors.push(`ownership descriptor overlap between handoffs at ${label}: ${key}`);
    target.set(key, count);
  }
}
function currentRows(path) {
  const groups = parseCss(path, readFileSync(join(ROOT, path), "utf8"));
  return {
    groups,
    rows: groups.flatMap((group) => group.selectors.map((row) => ({ ...row, path }))),
  };
}
function baselineTarget(row) {
  return row.owner.migrationBatch === "M3A-administration" ||
    row.owner.migrationBatch === "M3B-activity" ||
    (row.source.path === "apps/web/src/design/layout.css" &&
      row.owner.migrationBatch === "M2-materials" && /activity/i.test(row.selector));
}
function evaluate() {
  const errors = [];
  const baselineInventory = JSON.parse(gitShow("docs/17-evidence/issue-261-css-selector-inventory.json"));
  const b1Inventory = JSON.parse(gitShowAt(B1_SOURCE, "docs/17-evidence/issue-261-css-selector-inventory.json"));
  const m2Inventory = JSON.parse(gitShowAt(M2_SOURCE, "docs/17-evidence/issue-261-css-selector-inventory.json"));
  const m3Inventory = JSON.parse(gitShowAt(M3_SOURCE, "docs/17-evidence/issue-261-css-selector-inventory.json"));
  const currentInventory = JSON.parse(readFileSync(join(ROOT, "docs/17-evidence/issue-261-css-selector-inventory.json"), "utf8"));
  const baselineRows = baselineInventory.selectors;
  const targetRows = baselineRows.filter(baselineTarget);
  const adminRows = targetRows.filter((row) => row.owner.migrationBatch === "M3A-administration" && row.id !== "CSS-0725");
  const activityRows = targetRows.filter((row) => row.owner.migrationBatch === "M3B-activity" ||
    (row.source.path === "apps/web/src/design/layout.css" && row.owner.migrationBatch === "M2-materials" && /activity/i.test(row.selector)));
  const frozenRowsByKey = new Map();
  for (const path of LEGACY) {
    const parsed = parseCss(path, gitShow(path));
    for (const group of parsed) {
      for (const row of group.selectors) {
        frozenRowsByKey.set([path, row.ruleIndex, row.selectorIndex].join("\0"), {
          path,
          selector: row.selector,
          atContext: row.atContext,
          declarationSignature: row.declarationSignature,
        });
      }
    }
  }
  const parsedBaselineRows = baselineRows.map((row) => {
    const parsed = frozenRowsByKey.get([row.source.path, row.source.ruleIndex, row.source.selectorIndex].join("\0"));
    if (!parsed) errors.push("frozen source row missing for " + row.id);
    return parsed ?? {
      path: row.source.path,
      selector: row.selector,
      atContext: row.source.atContext,
      declarationSignature: row.declarations.signatureSha256,
    };
  });
  const parsedTargetRows = targetRows.map((row) => frozenRowsByKey.get([row.source.path, row.source.ruleIndex, row.source.selectorIndex].join("\0")) ?? {
    path: row.source.path,
    selector: row.selector,
    atContext: row.source.atContext,
    declarationSignature: row.declarations.signatureSha256,
  });
  const parsedById = new Map(baselineRows.map((row, index) => [row.id, parsedBaselineRows[index]]));
  const baselineDescriptors = baselineRows.map((row) => ({
    path: row.source.path,
    selector: row.selector,
    atContext: row.source.atContext,
    declarationSignature: row.declarations.signatureSha256,
  }));
  const baselineKeys = multiset(baselineDescriptors, (row) => descriptor(row));
  const acceptedDescriptors = new Map();
  addAcceptedDescriptors(acceptedDescriptors, removedDescriptorMultiset(baselineRows, b1Inventory.selectors), "B1", errors);
  addAcceptedDescriptors(acceptedDescriptors, removedDescriptorMultiset(baselineRows, m2Inventory.selectors), "M2", errors);
  addAcceptedDescriptors(acceptedDescriptors, removedDescriptorMultiset(baselineRows, m3Inventory.selectors), "M3", errors);
  for (const [key, count] of acceptedDescriptors) baselineKeys.set(key, (baselineKeys.get(key) ?? 0) - count);
  const currentLegacy = LEGACY.flatMap((path) => currentRows(path).rows);
  const currentInventoryRows = currentInventory.selectors.map((row) => ({
    path: row.source.path,
    selector: row.selector,
    atContext: row.source.atContext,
    declarationSignature: row.declarations.signatureSha256,
  }));
  equalMultiset(baselineKeys, multiset(currentInventoryRows, (row) => descriptor(row)), "retained legacy semantics", errors);

  const ownerAdmin = currentRows(ADMIN_OWNER);
  const ownerActivity = currentRows(ACTIVITY_OWNER);
  equalMultiset(
    multiset(adminRows.map((row) => parsedById.get(row.id)), ownerDescriptor),
    multiset(ownerAdmin.rows, ownerDescriptor), "administration owner roster", errors,
  );
  equalMultiset(
    multiset(activityRows.map((row) => parsedById.get(row.id)), ownerDescriptor),
    multiset(ownerActivity.rows, ownerDescriptor), "activity owner roster", errors,
  );

  const groups = new Map();
  const touched = new Map();
  for (const row of baselineRows) {
    const key = [row.source.path, row.source.ruleIndex].join("\0");
    const all = groups.get(key) ?? [];
    all.push(row); groups.set(key, all);
  }
  for (const row of targetRows) {
    const key = [row.source.path, row.source.ruleIndex].join("\0");
    const selected = touched.get(key) ?? [];
    selected.push(row); touched.set(key, selected);
  }
  const fullGroups = [...touched.entries()].filter(([key, selected]) => selected.length === groups.get(key).length);
  const partialGroups = [...touched.entries()].filter(([key, selected]) => selected.length < groups.get(key).length);
  const currentStats = Object.fromEntries(LEGACY.map((path) => {
    const parsed = currentRows(path);
    return [path, { rows: parsed.rows.length, groups: parsed.groups.length }];
  }));
  const targetPropertyGroups = baselineInventory.cascadeGroups.targetProperty.filter((group) => group.memberIds.some((id) => targetRows.some((row) => row.id === id)));
  const cascadeTargetRows = new Set(targetPropertyGroups.flatMap((group) => group.memberIds.filter((id) => targetRows.some((row) => row.id === id))));
  const exactGroups = baselineInventory.cascadeGroups.exactSelector.filter((group) => group.memberIds.some((id) => targetRows.some((row) => row.id === id)));
  const cascadeExactRows = new Set(exactGroups.flatMap((group) => group.memberIds.filter((id) => targetRows.some((row) => row.id === id))));
  const metrics = {
    targetRows: targetRows.length, targetGroups: touched.size, fullyRemovedGroups: fullGroups.length, partiallyShrunkGroups: partialGroups.length,
    administration: { rows: adminRows.length, groups: ownerAdmin.groups.length, rawColorRows: adminRows.filter((row) => row.flags.rawColor).length, literalFontWeightRows: adminRows.filter((row) => row.flags.literalFontWeight).length },
    activity: { rows: activityRows.length, groups: ownerActivity.groups.length, rawColorRows: activityRows.filter((row) => row.flags.rawColor).length, literalFontWeightRows: activityRows.filter((row) => row.flags.literalFontWeight).length },
    legacy: { rows: currentLegacy.length, groups: currentStats[LEGACY[0]].groups + currentStats[LEGACY[1]].groups, bySourceFile: currentStats },
    cascade: { targetSelectorIds: targetRows.length, targetPropertyCount: targetRows.reduce((total, row) => total + row.declarations.properties.length, 0), targetPropertyRows: cascadeTargetRows.size, targetPropertyGroups: targetPropertyGroups.length, exactSelectorRows: cascadeExactRows.size, exactSelectorGroups: exactGroups.length, unknownIds: 0 },
  };
  if (metrics.targetRows !== 506) errors.push("target rows " + metrics.targetRows + " != 506");
  if (metrics.targetGroups !== 377) errors.push("target groups " + metrics.targetGroups + " != 377");
  if (metrics.fullyRemovedGroups !== 356) errors.push("full groups " + metrics.fullyRemovedGroups + " != 356");
  if (metrics.partiallyShrunkGroups !== 21) errors.push("partial groups " + metrics.partiallyShrunkGroups + " != 21");
  if (adminRows.length !== 381 || ownerAdmin.groups.length !== 275) errors.push("administration owner count mismatch");
  if (activityRows.length !== 124 || ownerActivity.groups.length !== 102) errors.push("activity owner count mismatch");
  if (metrics.administration.rawColorRows !== 38 || metrics.administration.literalFontWeightRows !== 40) errors.push("administration flag counts mismatch");
  if (metrics.activity.rawColorRows !== 20 || metrics.activity.literalFontWeightRows !== 10) errors.push("activity flag counts mismatch");
  if (currentStats[LEGACY[0]].rows !== 1121 || currentStats[LEGACY[0]].groups !== 983) errors.push("styles.css combined post count mismatch");
  if (currentStats[LEGACY[1]].rows !== 985 || currentStats[LEGACY[1]].groups !== 794) errors.push("layout.css combined post count mismatch");
  if (currentInventory.summary.selectorRows !== 2106 || currentInventory.summary.cssRuleGroups !== 1777) errors.push("inventory combined post count mismatch");
  if (currentInventory.summary.byMigrationBatch["M2-materials"] !== undefined) errors.push("M2 residual should be reclassified into frozen HOLD/M4 batches");
  if (currentInventory.summary.byMigrationBatch["HOLD-owner-or-cross-feature-split"] !== 504) errors.push("combined HOLD residual mismatch");
  if (currentInventory.summary.byMigrationBatch["M4-shared-cleanup"] !== 314) errors.push("combined M4 residual mismatch");
  if (currentInventory.summary.flags.crossCssDuplicate !== 6) errors.push("combined cross-CSS duplicate count mismatch");

  const imports = readFileSync(join(ROOT, "apps/web/src/main.tsx"), "utf8");
  const importPositions = [
    imports.indexOf('import "./styles.css";'),
    imports.indexOf('import "./features/administration/ui/administration.css";'),
    imports.indexOf('import "./features/activity/ui/activity.css";'),
  ];
  if (importPositions.some((position) => position < 0) || importPositions[0] > importPositions[1] || importPositions[1] > importPositions[2]) errors.push("main CSS import order mismatch");

  const currentDescriptorCounts = multiset(currentLegacy, (row) => descriptor(row));
  const protectedIds = ["CSS-0213", "CSS-0222", "CSS-0223", "CSS-1381", "CSS-0013", "CSS-0014", "CSS-0334", "CSS-0384", "CSS-0407", "CSS-0397", "CSS-2470", "CSS-2471", "CSS-2474", "CSS-2475", "CSS-2477"];
  for (const id of protectedIds) {
    const baseline = baselineRows.find((row) => row.id === id);
    if (!baseline) { errors.push("protected row " + id + " missing from frozen inventory"); continue; }
    const key = descriptor(parsedById.get(id));
    const baselineCount = baselineDescriptors.filter((row) => descriptor(row) === key).length;
    if ((currentDescriptorCounts.get(key) ?? 0) !== baselineCount) errors.push("protected row " + id + " semantic signature changed");
  }
  const movedContextIds = ["CSS-0396", "CSS-1382", "CSS-2472", "CSS-2473", "CSS-2476"];
  const adminOwnerKeys = multiset(ownerAdmin.rows, ownerDescriptor);
  const activityOwnerKeys = multiset(ownerActivity.rows, ownerDescriptor);
  for (const id of movedContextIds) {
    const parsed = parsedById.get(id);
    const destination = id === "CSS-2472" || id === "CSS-2473" ? adminOwnerKeys : activityOwnerKeys;
    if (!parsed || (destination.get(ownerDescriptor(parsed)) ?? 0) < 1) errors.push("moved context row " + id + " missing from owner CSS");
  }
  const css0725 = baselineRows.find((row) => row.id === "CSS-0725");
  if (css0725) {
    const key = descriptor(parsedById.get("CSS-0725"));
    if (currentDescriptorCounts.has(key)) errors.push("CSS-0725 remained in legacy CSS");
    if (multiset(ownerAdmin.rows, ownerDescriptor).has(ownerDescriptor(parsedById.get("CSS-0725"))) ) errors.push("CSS-0725 was copied into administration owner");
    const peerRows = parseCss("apps/web/src/features/administration/database-design/database-design.css", readFileSync(join(ROOT, "apps/web/src/features/administration/database-design/database-design.css"), "utf8")).flatMap((group) => group.selectors);
    if (!peerRows.some((row) => row.selector === css0725.selector)) errors.push("CSS-0725 database-design peer is missing");
  }

  const allCascadeIds = new Set(baselineInventory.cascadeGroups.exactSelector.flatMap((group) => group.memberIds).concat(baselineInventory.cascadeGroups.targetProperty.flatMap((group) => group.memberIds)));
  if ([...allCascadeIds].some((id) => !baselineRows.some((row) => row.id === id))) errors.push("cascade oracle contains unknown selector IDs");
  if (metrics.cascade.targetPropertyCount !== 1638 || metrics.cascade.targetPropertyRows !== 302 || metrics.cascade.targetPropertyGroups !== 245 || metrics.cascade.exactSelectorRows !== 152 || metrics.cascade.exactSelectorGroups !== 66) errors.push("cascade accounting mismatch");

  const report = {
    issue: "#261", unit: "FE-06/M3 governance CSS ownership", frozenBase: FROZEN_BASE, status: errors.length ? "FAIL" : "PASS",
    roster: { targetRows: targetRows.length, targetGroups: touched.size, fullyRemovedGroups: fullGroups.length, partiallyShrunkGroups: partialGroups.length, administrationRows: adminRows.length, activityRows: activityRows.length },
    ownerFiles: { administration: { path: ADMIN_OWNER, rows: adminRows.length, groups: ownerAdmin.groups.length }, activity: { path: ACTIVITY_OWNER, rows: activityRows.length, groups: ownerActivity.groups.length } },
    legacyPostState: { selectorRows: currentLegacy.length, cssRuleGroups: currentStats[LEGACY[0]].groups + currentStats[LEGACY[1]].groups, bySourceFile: currentStats, acceptedHandoffRows: [...acceptedDescriptors.values()].reduce((total, count) => total + count, 0), m2ResidualRows: currentInventory.summary.byMigrationBatch["M2-materials"] ?? 0, holdResidualRows: currentInventory.summary.byMigrationBatch["HOLD-owner-or-cross-feature-split"], m4ResidualRows: currentInventory.summary.byMigrationBatch["M4-shared-cleanup"], crossCssDuplicateRows: currentInventory.summary.flags.crossCssDuplicate },
    cascadeOracle: metrics.cascade,
    preserved: { exactMaterialsPeers: ["CSS-0213", "CSS-0222", "CSS-0223", "CSS-1381"], m2MovedMaterialPeer: "CSS-0212", reducedMotion: "CSS-0396 moved with @media (prefers-reduced-motion: reduce)", maxWidth: "CSS-1382 moved with @media (max-width: 760px)", mixedSplitResidual: ["CSS-2470", "CSS-2471", "CSS-2472", "CSS-2473", "CSS-2474", "CSS-2475", "CSS-2476", "CSS-2477"], forbiddenResidual: ["CSS-0013", "CSS-0014", "CSS-0334", "CSS-0384", "CSS-0407", "CSS-0397"], css0725Peer: "apps/web/src/features/administration/database-design/database-design.css" },
    routeState: { administration: ["/administration/database", "/administration/schema-bundles", "/administration/records", "/administration/access"], activity: ["/activity", "/jobs-reviews"], note: "Routes/states are source-inventory evidence; live DOM/cascade behavior remains a Main acceptance boundary." },
    runtimeBoundary: { liveDom: "MAIN-REQUIRED", browserEvidence: "DEFERRED", physicalReadability: "N/A for source-only unit" },
    errors,
  };
  return { errors, report };
}
export { evaluate, parseCss };
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = evaluate();
  process.stdout.write(JSON.stringify(result.report, null, 2) + "\n");
  if (result.errors.length) process.exitCode = 1;
}

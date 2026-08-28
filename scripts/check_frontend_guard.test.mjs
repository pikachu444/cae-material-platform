import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";

import {
  BASELINE_SCHEMA,
  FrontendGuardError,
  assertBaselineProvenance,
  evaluateGuard,
  requiresBaselineProvenance,
  scanProject,
  validateBaseline,
} from "./check_frontend_guard.mjs";

function debt(ruleId, scope, count) {
  return {
    ruleId,
    scope,
    count,
    reason: "Known debt owned by the bounded follow-up.",
    followUpIssue: "#999",
    removalCondition: "Remove after the owned migration proves zero consumers.",
  };
}

function hotspot(path, baselineLines = 1) {
  return {
    path,
    baselineLines,
    responsibilities: ["legacy composition"],
    followUpIssue: "#999",
    removalCondition: "Remove after the owned extraction leaves composition only.",
  };
}

function baseline(overrides = {}) {
  return {
    schemaVersion: BASELINE_SCHEMA,
    sourceSha: "a".repeat(40),
    ownerIssue: "#256",
    hotspots: [],
    debt: [],
    exceptions: [],
    ...overrides,
  };
}

async function fixture(files) {
  const root = await mkdtemp(join(tmpdir(), "cmp-frontend-guard-"));
  for (const [path, content] of Object.entries(files)) {
    const target = join(root, path);
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, content, "utf8");
  }
  return root;
}

function changed(path, ...lines) {
  return new Map([[path, new Set(lines)]]);
}

test("allows public feature and downward shared imports", async () => {
  const root = await fixture({
    "apps/web/src/shared/value.ts": "export const value = 1;\n",
    "apps/web/src/features/b/index.ts": "export { value } from '../../shared/value';\n",
    "apps/web/src/features/a/view.ts": "import { value } from '../b';\nexport const view = value;\n",
    "apps/web/src/app/main.ts": "import { view } from '../features/a/view';\nvoid view;\n",
  });
  const report = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(report.passed, true);
  assert.deepEqual(report.violations, []);
});

test("rejects reverse imports, feature deep imports, and dependency cycles", async () => {
  const root = await fixture({
    "apps/web/src/shared/bad.ts": "import { a } from '../features/a';\nexport const shared = a;\n",
    "apps/web/src/features/a/index.ts": "export { a } from './one';\n",
    "apps/web/src/features/a/one.ts": "import { b } from '../b/two';\nexport const a = b;\n",
    "apps/web/src/features/b/two.ts": "import { a } from '../a/one';\nexport const b = a;\n",
  });
  const report = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(report.passed, false);
  assert.deepEqual(new Set(report.violations.map((item) => item.ruleId)), new Set([
    "CMP-FE-IMPORT-DIRECTION",
    "CMP-FE-FEATURE-DEEP-IMPORT",
    "CMP-FE-DEPENDENCY-CYCLE",
  ]));
});

test("caps root API compatibility at the recorded legacy consumers", async () => {
  const root = await fixture({
    "apps/web/src/api.ts": "export const legacy = 1;\n",
    "apps/web/src/legacy.ts": "import { legacy } from './api';\nvoid legacy;\n",
  });
  const rejected = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(rejected.passed, false);
  assert.equal(rejected.violations[0].ruleId, "CMP-FE-ROOT-API-COMPATIBILITY");

  const allowed = await evaluateGuard({
    projectRoot: root,
    baseline: baseline({
      debt: [debt("CMP-FE-ROOT-API-COMPATIBILITY", "apps/web/src", 1)],
    }),
  });
  assert.equal(allowed.passed, true);
  assert.equal(allowed.warnings[0].count, 1);
});

test("treats hotspot growth as a review signal and top-level additions as responsibility", async () => {
  const path = "apps/web/src/app.tsx";
  const root = await fixture({ [path]: "const first = 1;\nconst second = 2;\n" });
  const report = await evaluateGuard({
    projectRoot: root,
    baseline: baseline({ hotspots: [hotspot(path)] }),
    changedLines: changed(path, 2),
  });
  assert.equal(report.passed, false);
  assert.deepEqual(new Set(report.violations.map((item) => item.ruleId)), new Set([
    "CMP-FE-HOTSPOT-GROWTH",
    "CMP-FE-HOTSPOT-RESPONSIBILITY",
  ]));
});

test("allows only an exact issue-owned exception and rejects it after the finding disappears", async () => {
  const path = "apps/web/src/app.tsx";
  const root = await fixture({ [path]: "const added = 1;\n" });
  const initialBaseline = baseline({ hotspots: [hotspot(path)] });
  const initial = await evaluateGuard({ projectRoot: root, baseline: initialBaseline, changedLines: changed(path, 1) });
  const target = initial.violations.find((item) => item.ruleId === "CMP-FE-HOTSPOT-RESPONSIBILITY");
  const exception = {
    ruleId: target.ruleId,
    path: target.path,
    fingerprint: target.fingerprint,
    maxOccurrences: 1,
    reason: "Bounded compatibility entry approved in the issue.",
    ownerIssue: "#256",
    removalCondition: "Remove when the compatibility consumer reaches zero.",
  };
  const allowed = await evaluateGuard({
    projectRoot: root,
    baseline: { ...initialBaseline, exceptions: [exception] },
    changedLines: changed(path, 1),
  });
  assert.equal(allowed.passed, true);

  const cleanRoot = await fixture({ [path]: "void 0;\n" });
  const stale = await evaluateGuard({
    projectRoot: cleanRoot,
    baseline: { ...initialBaseline, exceptions: [exception] },
  });
  assert.equal(stale.passed, false);
  assert.equal(stale.violations[0].ruleId, "CMP-FE-STALE-EXCEPTION");
});

test("blocks a new legacy global selector even when the baseline count is unchanged", async () => {
  const path = "apps/web/src/styles.css";
  const root = await fixture({ [path]: ".new-feature { color: var(--ux-text); }\n" });
  const report = await evaluateGuard({
    projectRoot: root,
    baseline: baseline({ debt: [debt("CMP-FE-GLOBAL-CSS-SELECTOR", path, 1)] }),
    changedLines: changed(path, 1),
  });
  assert.equal(report.passed, false);
  assert.equal(report.violations[0].ruleId, "CMP-FE-GLOBAL-CSS-SELECTOR");
});

test("does not relabel unchanged baseline syntax on an otherwise edited line as new debt", async () => {
  const path = "apps/web/src/features/modeling/view.tsx";
  const accepted = baseline({ debt: [debt("CMP-FE-EYEBROW", "apps/web/src", 1)] });
  const baseRoot = await fixture({ [path]: "export const View = () => <div className=\"eyebrow\">Before</div>;\n" });
  const currentRoot = await fixture({ [path]: "export const View = () => <div className=\"eyebrow\">After</div>;\n" });
  const baseFindings = await scanProject({ projectRoot: baseRoot, baseline: accepted });
  const report = await evaluateGuard({
    projectRoot: currentRoot,
    baseline: accepted,
    changedLines: changed(path, 1),
    baseFindings,
  });
  assert.equal(report.passed, true);
});

test("allows token definitions and rejects raw feature colors and literal font weights", async () => {
  const root = await fixture({
    "apps/web/src/design/tokens.css": ":root { --ux-new: #ffffff; }\n",
    "apps/web/src/features/materials/view.css": ".value { color: #ffffff; font-weight: 700; }\n",
  });
  const report = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(report.passed, false);
  assert.deepEqual(report.violations.map((item) => item.ruleId), ["CMP-FE-FONT-WEIGHT", "CMP-FE-RAW-COLOR"]);
  assert.equal(report.findings.some((item) => item.path.endsWith("tokens.css")), false);
});

test("allows owned feature CSS that uses tokens and a bounded responsive rule", async () => {
  const root = await fixture({
    "apps/web/src/features/materials/view.css": [
      ".result-row { color: var(--ux-text); font-weight: var(--ux-weight-body); }",
      "@media (min-width: 1200px) { .result-row { grid-template-columns: 1fr 2fr; } }",
      "",
    ].join("\n"),
  });
  const report = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(report.passed, true);
  assert.deepEqual(report.violations, []);
});

test("does not treat color-like URL fragments as raw colors", async () => {
  const root = await fixture({
    "apps/web/src/features/materials/icons.css": ".icon { background-image: url(\"asset.svg#fff\"); filter: url('filters.svg#red'); }\n",
  });
  const report = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(report.passed, true);
  assert.deepEqual(report.violations, []);
});

test("rejects new generic semantic classes", async () => {
  const root = await fixture({
    "apps/web/src/features/modeling/view.tsx": "export const View = () => <div className=\"workbench-card eyebrow status-chip\" />;\n",
  });
  const report = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(report.passed, false);
  assert.deepEqual(report.violations.map((item) => item.ruleId), [
    "CMP-FE-EYEBROW",
    "CMP-FE-STATUS-CHIP",
    "CMP-FE-WORKBENCH-CARD",
  ]);
});

test("rejects wide-screen shortcuts, zoom, scale, and fabricated filler", async () => {
  const root = await fixture({
    "apps/web/src/features/modeling/view.css": "@media (min-width: 2560px) { .route-filler { zoom: 2; transform: scale(2); } }\n",
  });
  const report = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(report.passed, false);
  assert.deepEqual(new Set(report.violations.map((item) => item.ruleId)), new Set([
    "CMP-FE-WIDE-MEDIA",
    "CMP-FE-CSS-ZOOM",
    "CMP-FE-BLANKET-SCALE",
    "CMP-FE-FABRICATED-FILLER",
  ]));
});

test("rejects named colors, relative-unit wide media, and the scale property", async () => {
  const root = await fixture({
    "apps/web/src/features/modeling/view.css": "@media (width >= 100rem) { .workspace { background: rebeccapurple; scale: 2; } }\n",
  });
  const report = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(report.passed, false);
  assert.deepEqual(new Set(report.violations.map((item) => item.ruleId)), new Set([
    "CMP-FE-WIDE-MEDIA",
    "CMP-FE-RAW-COLOR",
    "CMP-FE-BLANKET-SCALE",
  ]));
});

test("rejects named colors inside filter functions", async () => {
  const root = await fixture({
    "apps/web/src/features/materials/icons.css": ".icon { filter: drop-shadow(0 0 2px rebeccapurple); }\n",
  });
  const report = await evaluateGuard({ projectRoot: root, baseline: baseline() });
  assert.equal(report.passed, false);
  assert.equal(report.violations.length, 1);
  assert.equal(report.violations[0].ruleId, "CMP-FE-RAW-COLOR");
});

test("allows debt reduction, reports the remaining baseline, and sorts diagnostics", async () => {
  const root = await fixture({
    "apps/web/src/z.css": ".z { color: #fff; }\n",
    "apps/web/src/a.css": ".a { color: #000; }\n",
  });
  const report = await evaluateGuard({
    projectRoot: root,
    baseline: baseline({ debt: [debt("CMP-FE-RAW-COLOR", "apps/web/src", 3)] }),
  });
  assert.equal(report.passed, true);
  assert.equal(report.warnings[0].count, 2);
  assert.deepEqual(report.findings.map((item) => item.path), ["apps/web/src/a.css", "apps/web/src/z.css"]);
});

test("rejects debt above the baseline even without changed-line metadata", async () => {
  const root = await fixture({
    "apps/web/src/a.css": ".a { color: #000; }\n",
    "apps/web/src/b.css": ".b { color: #fff; }\n",
  });
  const report = await evaluateGuard({
    projectRoot: root,
    baseline: baseline({ debt: [debt("CMP-FE-RAW-COLOR", "apps/web/src", 1)] }),
  });
  assert.equal(report.passed, false);
  assert.equal(report.violations.length, 1);
  assert.equal(report.violations[0].ruleId, "CMP-FE-RAW-COLOR");
});

test("rejects malformed, duplicate, and unowned baseline entries", async () => {
  const invalid = baseline({
    sourceSha: "bad",
    debt: [debt("CMP-FE-RAW-COLOR", "apps/web/src", 1), debt("CMP-FE-RAW-COLOR", "apps/web/src", 1)],
    exceptions: [{ ruleId: "CMP-FE-RAW-COLOR", path: "x", fingerprint: "bad", maxOccurrences: 0, reason: "", ownerIssue: "owner", removalCondition: "" }],
  });
  const errors = validateBaseline(invalid);
  assert.equal(errors.some((message) => message.includes("sourceSha")), true);
  assert.equal(errors.some((message) => message.includes("duplicated")), true);
  const root = await fixture({ "apps/web/src/empty.ts": "export {};\n" });
  await assert.rejects(
    () => evaluateGuard({ projectRoot: root, baseline: invalid }),
    (error) => error instanceof FrontendGuardError && error.code === "INVALID_BASELINE",
  );
});

test("rejects a well-formed baseline whose source SHA is not the merge base", () => {
  assert.throws(
    () => assertBaselineProvenance(baseline({ sourceSha: "b".repeat(40) }), "a".repeat(40)),
    (error) => error instanceof FrontendGuardError && error.code === "BASELINE_PROVENANCE",
  );
});

test("requires baseline provenance only for frontend guard relevant changes", () => {
  assert.equal(requiresBaselineProvenance(new Set(["IMPLEMENTATION_STATUS.md", "docs/guide.md"])), false);
  assert.equal(requiresBaselineProvenance(new Set(["backend/src/example.py"])), false);
  assert.equal(requiresBaselineProvenance(new Set(["apps/web/src/app.tsx"])), true);
  assert.equal(requiresBaselineProvenance(new Set(["apps/web/frontend-guard-baseline.json"])), true);
  assert.equal(requiresBaselineProvenance(new Set(["scripts/check_frontend_guard.mjs"])), true);
  assert.equal(requiresBaselineProvenance(new Set(["scripts/check_frontend_guard.test.mjs"])), true);
});

import { expect, test, type APIRequestContext, type BrowserContext, type Locator, type Page } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Issue #261 M1E5's bounded browser oracle. Main runs this spec twice with the
 * frozen producer and candidate source, setting CMP_ISSUE_261_M1E5_E2E=1 and
 * CMP_ISSUE_261_EVIDENCE_PHASE=before|after. The app/API fixture is deliberately
 * supplied by Main; this spec never invents catalog or Modeling records.
 */
const enabled = process.env.CMP_ISSUE_261_M1E5_E2E === "1";
const phase = process.env.CMP_ISSUE_261_EVIDENCE_PHASE === "before" ? "before" : "after";
const evidenceRoot = process.env.CMP_ISSUE_261_EVIDENCE_DIR;
const materialCurveRoute = process.env.CMP_ISSUE_261_M1E5_MATERIAL_ROUTE;
const recoveryRoute = process.env.CMP_ISSUE_261_M1E5_RECOVERY_ROUTE;
const demoWebUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const selectorFixturePath = [
  join(process.cwd(), "scripts/fixtures/issue-261-m1e5-producer-routed-residual.json"),
  join(process.cwd(), "..", "..", "scripts/fixtures/issue-261-m1e5-producer-routed-residual.json"),
].find((candidate) => existsSync(candidate));
if (!selectorFixturePath) throw new Error("M1E5 selector fixture is required for the browser oracle");
const selectorFixture = JSON.parse(
  readFileSync(selectorFixturePath, "utf8"),
) as {
  approvedIds: string[];
  targetTuples: [string, string, number, number, number, string, string[], string, string[], string[], string][];
};
const intendedPropertiesById = new Map(
  selectorFixture.targetTuples.map((tuple) => [tuple[0], tuple[8]]),
);

const viewports = [
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1920x1080", width: 1920, height: 1080 },
  { name: "2560x1440", width: 2560, height: 1440 },
  { name: "3840x2160", width: 3840, height: 2160 },
] as const;

type RouteCase = {
  id: string;
  route: string;
  root: string;
  selectors: string[];
  crops: Record<string, string>;
  identity: RegExp;
  classification?: "primary" | "technical" | "negative";
  renderedSelectors?: string[];
  open?: (page: Page) => Promise<void>;
  applicationContracts?: SelectorApplicationContract[];
  captureDisposition?: "canonical" | "collapsed-equivalence" | "no-screenshot-technical";
  equivalenceGroup?: string;
  equivalentTo?: string;
};

type SelectorApplicationContract = {
  id: string;
  routeId: string;
  locator: string;
  baseSelector: string;
  matchSelector?: string;
  pseudoElement?: "::before" | "::after";
  preparation?: "curve-interaction";
};

type SelectorApplicationRecord = {
  id: string;
  locator: string;
  baseSelector: string;
  matchSelector: string;
  pseudoElement: string | null;
  computed: Record<string, string>;
  geometry: { x: number; y: number; width: number; height: number };
};

async function bootstrapDemoSession(page: Page, request: APIRequestContext): Promise<void> {
  const response = await request.get(`${demoWebUrl}/api/v1/demo-identity/token?persona=administrator`);
  expect(response.ok(), "administrator demo token request").toBeTruthy();
  const payload = await response.json() as { access_token?: unknown };
  expect(typeof payload.access_token, "demo token payload").toBe("string");
  await page.addInitScript(({ accessToken }) => {
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken }),
    );
  }, { accessToken: payload.access_token as string });
}

async function openFreshDemoPage(
  context: BrowserContext,
  request: APIRequestContext,
  viewport: typeof viewports[number],
): Promise<Page> {
  const freshPage = await context.newPage();
  try {
    await freshPage.setViewportSize({ width: viewport.width, height: viewport.height });
    await bootstrapDemoSession(freshPage, request);
    return freshPage;
  } catch (error) {
    await freshPage.close().catch(() => undefined);
    throw error;
  }
}

async function waitForMaterialsReady(page: Page): Promise<void> {
  const results = page.locator(".materials-results");
  await expect(results).toBeVisible({ timeout: 30_000 });
  await expect.poll(
    async () => (await results.getAttribute("aria-busy")) ?? "false",
    { timeout: 30_000 },
  ).toBe("false");
  await expect(results.getByText("Loading…", { exact: true })).toHaveCount(0, { timeout: 30_000 });
}

async function openMaterialsCurves(page: Page): Promise<void> {
  if (materialCurveRoute) {
    await page.goto(materialCurveRoute, { waitUntil: "domcontentloaded" });
    return;
  }
  // The exact material id is disposable fixture state. Resolve it through the
  // existing Materials controls instead of inventing a route or slug.
  await page.goto("/materials", { waitUntil: "domcontentloaded" });
  const search = page.getByRole("textbox", { name: "Search materials" });
  if ((await search.count()) === 0) {
    await page.getByRole("button", { name: "Filters", exact: true }).click();
  }
  await expect(search).toBeVisible({ timeout: 30_000 });
  await waitForMaterialsReady(page);
  await search.fill("CMP-DEMO-DP780");
  await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "CMP-DEMO-DP780" });
  await expect(row).toHaveCount(1, { timeout: 30_000 });
  await row.getByRole("button").click();
  await expect(page).toHaveURL(/\/materials\/[^/?]+/);
  const curves = page.getByRole("tab", { name: "Curves", exact: true });
  await expect(curves).toBeVisible({ timeout: 30_000 });
  await curves.click();
  await expect(page).toHaveURL(/\/materials\/[^/]+\/curves/);
}

/*
 * These are the browser-facing half of the frozen 58-row fixture.  The
 * declaration properties are read from targetTuples below, so this table only
 * records the truthful producer route, intended DOM locator, selector match,
 * and any interaction required to materialize a stateful rule.  The source
 * validator checks that this covers every LIVE row exactly once.
 */
const selectorApplicationContracts: SelectorApplicationContract[] = [
  { id: "CSS-0160", routeId: "materials-curves", locator: ".contract-curve-heading", baseSelector: ".contract-curve-heading" },
  { id: "CSS-0161", routeId: "materials-curves", locator: ".contract-curve-heading h3", baseSelector: ".contract-curve-heading h3" },
  { id: "CSS-0162", routeId: "materials-curves", locator: ".contract-curve-heading p", baseSelector: ".contract-curve-heading p" },
  { id: "CSS-0164", routeId: "materials-curves", locator: ".contract-curve-heading p", baseSelector: ".contract-curve-heading p" },
  { id: "CSS-0165", routeId: "materials-curves", locator: ".contract-curve-heading > span", baseSelector: ".contract-curve-heading > span" },
  { id: "CSS-0167", routeId: "materials-curves", locator: ".contract-curve-actions > span", baseSelector: ".contract-curve-actions > span" },
  { id: "CSS-0168", routeId: "materials-curves", locator: ".curve-channel-summary", baseSelector: ".curve-channel-summary" },
  { id: "CSS-0169", routeId: "materials-curves", locator: ".contract-curve-frame", baseSelector: ".contract-curve-frame" },
  { id: "CSS-0170", routeId: "materials-curves", locator: ".contract-curve-svg", baseSelector: ".contract-curve-svg" },
  { id: "CSS-0171", routeId: "materials-curves", locator: ".contract-curve-line", baseSelector: ".contract-curve-line" },
  { id: "CSS-0178", routeId: "materials-curves", locator: ".contract-curve .curve-legend", baseSelector: ".contract-curve .curve-legend" },
  { id: "CSS-0179", routeId: "materials-curves", locator: ".curve-legend i.contract-line", baseSelector: ".curve-legend i.contract-line" },
  { id: "CSS-0180", routeId: "materials-curves", locator: ".contract-curve-actions", baseSelector: ".contract-curve-actions" },
  { id: "CSS-0181", routeId: "materials-curves", locator: ".curve-evidence dl", baseSelector: ".curve-evidence dl", preparation: "curve-interaction" },
  { id: "CSS-0182", routeId: "materials-curves", locator: ".curve-evidence dt", baseSelector: ".curve-evidence dt", preparation: "curve-interaction" },
  { id: "CSS-0183", routeId: "materials-curves", locator: ".curve-evidence dd", baseSelector: ".curve-evidence dd", preparation: "curve-interaction" },
  { id: "CSS-0455", routeId: "canonical-test-json", locator: ".test-json-page .workbench-card", baseSelector: ".test-json-page .workbench-card" },
  { id: "CSS-0886", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .curve-legend", baseSelector: ".curve-legend", pseudoElement: "::before" },
  { id: "CSS-0897", routeId: "modeling-fit-elastomer", locator: 'section.neutral-solver-export[aria-label="Reviewed Neutral Material and solver card delivery"] .mapping-report-heading', baseSelector: ".mapping-report-heading" },
  { id: "CSS-0898", routeId: "exports", locator: ".bulk-export-center .card-actions", baseSelector: ".card-actions" },
  { id: "CSS-0961", routeId: "exports", locator: ".bulk-export-center .card-actions", baseSelector: ".card-actions" },
  { id: "CSS-1008", routeId: "governed-import", locator: ".governed-import-route .workflow-card", baseSelector: ".governed-import-route .workflow-card" },
  { id: "CSS-1009", routeId: "governed-import", locator: ".governed-import-route .workflow-card:last-child", baseSelector: ".governed-import-route .workflow-card:last-child" },
  { id: "CSS-1010", routeId: "governed-import", locator: ".governed-import-route .workflow-card h4", baseSelector: ".governed-import-route .workflow-card h4" },
  { id: "CSS-1011", routeId: "governed-import", locator: ".governed-import-route .workflow-card label", baseSelector: ".governed-import-route .workflow-card label" },
  { id: "CSS-1012", routeId: "governed-import", locator: ".governed-import-route .workflow-card input", baseSelector: ".governed-import-route .workflow-card input" },
  { id: "CSS-1013", routeId: "governed-import", locator: ".governed-import-route .workflow-card select", baseSelector: ".governed-import-route .workflow-card select" },
  { id: "CSS-1014", routeId: "governed-import", locator: ".governed-import-route .workflow-card button", baseSelector: ".governed-import-route .workflow-card button" },
  { id: "CSS-1114", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .chart-axis", baseSelector: ".chart-axis" },
  { id: "CSS-1115", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .chart-grid", baseSelector: ".chart-grid" },
  { id: "CSS-1116", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .chart-tick", baseSelector: ".chart-tick" },
  { id: "CSS-1117", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .chart-axis-label", baseSelector: ".chart-axis-label" },
  { id: "CSS-1118", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .chart-axis-label", baseSelector: ".chart-axis-label" },
  { id: "CSS-1120", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .curve-legend", baseSelector: ".curve-legend" },
  { id: "CSS-1122", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .curve-legend i", baseSelector: ".curve-legend i" },
  { id: "CSS-1123", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .curve-legend.interactive", baseSelector: ".curve-legend.interactive" },
  { id: "CSS-1124", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .curve-legend.interactive button", baseSelector: ".curve-legend.interactive button" },
  { id: "CSS-1126", routeId: "modeling-data-metal", locator: ".modeling-workspace-stage-data .curve-legend.interactive i", baseSelector: ".curve-legend.interactive i" },
];

const liveSelectorIds = selectorApplicationContracts.map((contract) => contract.id);
const naSourceTestSelectorIds = [
  "CSS-0158", "CSS-0163", "CSS-0166", "CSS-0172", "CSS-0173", "CSS-0174", "CSS-0175", "CSS-0176", "CSS-0887", "CSS-0984", "CSS-0985", "CSS-1019", "CSS-1020",
  "CSS-1057", "CSS-1058", "CSS-1059", "CSS-1121", "CSS-1125", "CSS-1157", "CSS-1158",
];
const selectorPartition = new Set([...liveSelectorIds, ...naSourceTestSelectorIds]);
if (selectorPartition.size !== selectorFixture.approvedIds.length
  || selectorFixture.approvedIds.some((id) => !selectorPartition.has(id))) {
  throw new Error("M1E5 LIVE/N_A_SOURCE_TEST selector partition must cover the frozen 58 approved rows exactly");
}

const routeCases: RouteCase[] = [
  {
    id: "modeling-data-metal",
    classification: "primary",
    route: "/modeling?stage=data&family=metal",
    root: ".modeling-main-surface, .modeling-workspace, main",
    selectors: [".curve-legend"],
    identity: /(?:Modeling|Test Data|Data)/i,
    crops: {
      header: "header",
      navigator: ".modeling-stage-navigator, nav",
      "table-form": "form, table, .data-mapping-table",
      "stage-controls": ".modeling-task-ribbon, .modeling-stage-controls",
      "engineering-graph": ".engineering-plot-frame, svg[role=img]",
    },
  },
  {
    id: "modeling-process-metal",
    classification: "technical",
    captureDisposition: "no-screenshot-technical",
    route: "/modeling?stage=process&family=metal",
    root: ".modeling-main-surface, .modeling-workspace, main",
    selectors: [".curve-legend"],
    identity: /(?:Process|Recipe|Load data)/i,
    crops: {
      header: "header",
      navigator: ".modeling-stage-navigator, nav",
      "stage-controls": ".process-stage-options, .modeling-task-ribbon",
      "engineering-graph": ".engineering-plot-frame, .contract-curve-frame, svg[role=img]",
    },
  },
  {
    id: "modeling-process-elastomer-hold",
    classification: "negative",
    route: "/modeling?stage=process&family=elastomer",
    root: ".modeling-main-surface, .modeling-workspace, main",
    selectors: [".hyperelastic-response-plot .chart-axis", ".hyperelastic-response-plot .chart-tick"],
    identity: /(?:Process|Ogden|Elastomer)/i,
    crops: {
      header: "header",
      navigator: ".modeling-stage-navigator, nav",
      "stage-controls": ".process-stage-options, .modeling-task-ribbon",
      "engineering-graph": ".engineering-plot-frame, .hyperelastic-response-plot, svg[role=img]",
    },
  },
  {
    id: "modeling-alias-process",
    captureDisposition: "collapsed-equivalence",
    equivalenceGroup: "modeling-process-metal",
    equivalentTo: "modeling-process-metal",
    route: "/datasets/processing?stage=process&family=metal",
    root: ".modeling-main-surface, .modeling-workspace, main",
    selectors: [".curve-legend"],
    identity: /(?:Process|Recipe|Load data)/i,
    crops: {
      header: "header",
      navigator: ".modeling-stage-navigator, nav",
      "stage-controls": ".process-stage-options, .modeling-task-ribbon",
      "engineering-graph": ".engineering-plot-frame, .contract-curve-frame, svg[role=img]",
    },
  },
  {
    id: "materials-curves",
    route: materialCurveRoute ?? "/materials/<exact-material-id>/curves",
    root: ".material-detail-shell, .ux-page, main",
    selectors: [".contract-curve-frame", ".contract-curve-heading"],
    identity: /(?:DP780|CMP-DEMO-DP780)/i,
    open: openMaterialsCurves,
    crops: {
      header: "header",
      navigator: ".material-context-tabs, nav",
      "table-form": ".material-detail-header, table, form",
      "engineering-graph": ".contract-curve-frame, svg[role=img]",
    },
  },
  {
    id: "governed-import",
    route: "/datasets/import",
    root: ".governed-import-route",
    selectors: [".governed-import-route .workflow-card", ".governed-import-route .workflow-card label"],
    identity: /(?:Governed|Import|CSV|TSV|XLSX)/i,
    crops: {
      header: "header",
      navigator: "nav, .governed-import-route-header",
      "table-form": ".governed-import, form",
      "stage-controls": ".governed-import-route .workflow-grid, .governed-import-actions",
    },
  },
  {
    id: "canonical-test-json",
    route: "/datasets/test-json",
    root: ".test-json-page",
    selectors: [".test-json-page .workbench-card"],
    identity: /(?:Test Data|JSON|canonical)/i,
    crops: {
      header: "header",
      navigator: "nav, .page-hero",
      "table-form": ".test-json-grid, form, table",
      "stage-controls": ".test-json-actions, .workbench-card",
    },
  },
  {
    id: "exports",
    route: "/exports",
    root: ".bulk-export-center",
    selectors: [".card-actions"],
    identity: /(?:Export|Solver|Governed transfer)/i,
    crops: {
      header: "header",
      navigator: "nav, .export-hero",
      "table-form": ".export-builder, form, table",
      "stage-controls": ".export-toolbar, .export-groups",
      "native-preview": ".bundle-row, .export-builder",
    },
  },
  {
    id: "modeling-fit-polymer",
    classification: "negative",
    captureDisposition: "no-screenshot-technical",
    route: "/modeling?stage=fit&family=polymer",
    root: ".modeling-main-surface, .modeling-workspace, main",
    selectors: [".curve-legend"],
    identity: /(?:Fit|Prony|Polymer)/i,
    crops: {
      header: "header",
      navigator: ".modeling-stage-navigator, nav",
      "table-form": "form, table, .fit-candidate-table",
      "stage-controls": ".modeling-task-ribbon, .fit-stage-options",
      "engineering-graph": ".engineering-plot-frame, svg[role=img]",
    },
  },
  {
    id: "modeling-export-polymer",
    classification: "negative",
    captureDisposition: "no-screenshot-technical",
    route: "/modeling?stage=export&family=polymer",
    root: ".modeling-target-preview, .modeling-main-surface, main",
    selectors: [".mapping-report-heading", ".card-actions"],
    identity: /(?:Export|Solver|Polymer)/i,
    crops: {
      header: "header",
      navigator: ".modeling-stage-navigator, nav",
      "stage-controls": ".export-toolbar, .modeling-task-ribbon",
      "engineering-graph": ".engineering-plot-frame, .fit-source-plot, svg[role=img]",
      "native-preview": ".native-preview, .export-native-preview-shell, .modeling-target-preview",
    },
  },
  {
    id: "modeling-fit-elastomer",
    classification: "primary",
    renderedSelectors: [
      'section.neutral-solver-export[aria-label="Reviewed Neutral Material and solver card delivery"] .mapping-report-heading',
      'section.neutral-solver-export[aria-label="Reviewed Neutral Material and solver card delivery"] .mapping-list',
    ],
    route: "/modeling?stage=fit&family=elastomer",
    root: ".neutral-solver-export, .reference-calibration-workbench, main",
    selectors: [".mapping-report-heading", ".mapping-list"],
    identity: /(?:Neutral Material|mapping|Ogden|Elastomer)/i,
    open: openElastomerMappingReport,
    crops: {
      header: "header",
      navigator: ".modeling-stage-navigator, nav",
      "table-form": ".neutral-solver-export .form-grid, .neutral-solver-export .delivery-evidence",
      "stage-controls": ".neutral-solver-export .mapping-report, .neutral-solver-export .button-row",
      "engineering-graph": ".reference-calibration-workbench .elastomer-candidate-rail, .reference-calibration-workbench",
      "native-preview": ".neutral-solver-export .mapping-report, .neutral-solver-export .mapping-list",
    },
  },
  {
    id: "modeling-export-elastomer",
    classification: "negative",
    captureDisposition: "no-screenshot-technical",
    route: "/modeling?stage=export&family=elastomer",
    root: ".modeling-target-preview, .modeling-main-surface, main",
    selectors: [".mapping-report-heading", ".card-actions"],
    identity: /(?:Export|Solver|Ogden|Elastomer)/i,
    crops: {
      header: "header",
      navigator: ".modeling-stage-navigator, nav",
      "stage-controls": ".export-toolbar, .modeling-task-ribbon",
      "engineering-graph": ".engineering-plot-frame, .fit-source-plot, .hyperelastic-response-plot, svg[role=img]",
      "native-preview": ".native-preview, .export-native-preview-shell, .modeling-target-preview",
    },
  },
  {
    id: "modeling-alias-data",
    captureDisposition: "collapsed-equivalence",
    equivalenceGroup: "modeling-data-metal",
    equivalentTo: "modeling-data-metal",
    route: "/datasets/processing?stage=data&family=metal",
    root: ".modeling-main-surface, .modeling-workspace, main",
    selectors: [".curve-legend"],
    identity: /(?:Data|Test Data|Modeling)/i,
    crops: {
      header: "header",
      navigator: ".modeling-stage-navigator, nav",
      "table-form": "form, table, .data-mapping-table",
      "stage-controls": ".modeling-task-ribbon, .modeling-stage-controls",
      "engineering-graph": ".engineering-plot-frame, svg[role=img]",
    },
  },
].map((routeCase) => ({
  ...routeCase,
  classification: routeCase.classification ?? "technical",
  captureDisposition: routeCase.captureDisposition ?? "canonical",
  applicationContracts: selectorApplicationContracts.filter((contract) => contract.routeId === routeCase.id),
}));

type RenderedElementSnapshot = { index: number; ariaPressed: string | null };

async function renderedElementSnapshot(page: Page, selector: string): Promise<RenderedElementSnapshot | null> {
  try {
    const snapshots = await page.locator(selector).evaluateAll((elements) => elements.map((element, index) => {
      const style = getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") return null;
      const opacity = Number.parseFloat(style.opacity);
      if (Number.isFinite(opacity) && opacity <= 0) return null;
      const rect = element.getBoundingClientRect();
      let rendered = rect.width > 0 || rect.height > 0;
      if (!rendered && element instanceof SVGGeometryElement) {
        try {
          rendered = element.getTotalLength() > 0;
        } catch {
          rendered = false;
        }
      }
      return rendered ? { index, ariaPressed: element.getAttribute("aria-pressed") } : null;
    }).filter((snapshot): snapshot is RenderedElementSnapshot => snapshot !== null));
    return snapshots[0] ?? null;
  } catch {
    return null;
  }
}

async function firstVisible(page: Page, selector: string): Promise<Locator> {
  await expect.poll(
    async () => (await renderedElementSnapshot(page, selector))?.index ?? -1,
    { timeout: 30_000 },
  ).toBeGreaterThanOrEqual(0);
  const snapshot = await renderedElementSnapshot(page, selector);
  if (snapshot) return page.locator(selector).nth(snapshot.index);
  // A responsive render can replace the snapshot between the poll and this
  // return. The locator remains lazy and resolves the current matching node.
  return page.locator(selector).first();
}

function splitSelectorList(selectorText: string): string[] {
  const members: string[] = [];
  let start = 0;
  let parentheses = 0;
  let brackets = 0;
  let quote: "'" | '"' | null = null;
  let escaped = false;
  for (let index = 0; index < selectorText.length; index += 1) {
    const character = selectorText[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === "\\") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (character === quote) quote = null;
      continue;
    }
    if (character === "'" || character === '"') {
      quote = character;
      continue;
    }
    if (character === "(") parentheses += 1;
    else if (character === ")") parentheses = Math.max(0, parentheses - 1);
    else if (character === "[") brackets += 1;
    else if (character === "]") brackets = Math.max(0, brackets - 1);
    else if (character === "," && parentheses === 0 && brackets === 0) {
      members.push(selectorText.slice(start, index).trim());
      start = index + 1;
    }
  }
  const finalMember = selectorText.slice(start).trim();
  if (finalMember) members.push(finalMember);
  return members;
}

function normalizeSelector(selector: string): string {
  return selector
    .trim()
    .replace(/\s+/g, " ")
    .replace(/\s*([>+~])\s*/g, "$1")
    .replace(/::(before|after|first-line|first-letter|selection|backdrop|placeholder|marker|file-selector-button)/g, ":$1");
}

function hasExactSelectorMembership(emitted: string[], wanted: string): boolean {
  const expected = normalizeSelector(wanted);
  return emitted.some((rule) => splitSelectorList(rule).some((member) => normalizeSelector(member) === expected));
}

async function waitForRoute(page: Page, routeCase: RouteCase): Promise<void> {
  if (routeCase.open) await routeCase.open(page);
  else await page.goto(routeCase.route, { waitUntil: "domcontentloaded" });
  await expect(await firstVisible(page, routeCase.root), `${routeCase.id}: route root`).toBeVisible({ timeout: 30_000 });
  await page.waitForLoadState("networkidle").catch(() => undefined);
}

async function cssomSelectors(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const selectors: string[] = [];
    const visit = (rules: CSSRuleList) => {
      for (const rule of Array.from(rules)) {
        if (rule instanceof CSSStyleRule) selectors.push(rule.selectorText);
        if ("cssRules" in rule && rule.cssRules) visit(rule.cssRules);
      }
    };
    for (const sheet of Array.from(document.styleSheets)) {
      try {
        if (sheet.cssRules) visit(sheet.cssRules);
      } catch {
        // Cross-origin sheets are outside this local CSSOM oracle.
      }
    }
    return selectors;
  });
}

async function prepareSelectorApplicationState(page: Page, routeCase: RouteCase): Promise<void> {
  if (routeCase.id === "materials-curves") {
    const evidence = page.locator("details.curve-evidence");
    if ((await evidence.getAttribute("open")) === null) await evidence.locator("summary").click();
  }
}

async function assertSelectorApplications(page: Page, routeCase: RouteCase): Promise<SelectorApplicationRecord[]> {
  const contracts = routeCase.applicationContracts ?? [];
  if (!contracts.length) return [];
  await prepareSelectorApplicationState(page, routeCase);
  const records: SelectorApplicationRecord[] = [];
  for (const contract of contracts) {
    let locator: Locator;
    try {
      locator = await firstVisible(page, contract.locator);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      throw new Error(`${routeCase.id}/${contract.id}: rendered locator ${contract.locator} unavailable (${detail})`);
    }
    const properties = intendedPropertiesById.get(contract.id);
    expect(properties, `${contract.id}: frozen declaration properties`).toBeTruthy();
    const result = await locator.evaluate((element, input) => {
      const matchSelector = input.matchSelector || input.baseSelector;
      const style = getComputedStyle(element, input.pseudoElement || undefined);
      const rect = element.getBoundingClientRect();
      const svgGeometryReachable = element instanceof SVGGeometryElement
        ? (() => {
          try {
            return element.getTotalLength() > 0;
          } catch {
            return false;
          }
        })()
        : false;
      return {
        baseMatches: element.matches(input.baseSelector),
        stateMatches: element.matches(matchSelector),
        visible: (Boolean(rect.width || rect.height) || svgGeometryReachable)
          && getComputedStyle(element).display !== "none"
          && getComputedStyle(element).visibility !== "hidden"
          && Number.parseFloat(getComputedStyle(element).opacity) > 0,
        computed: Object.fromEntries(input.properties.map((property) => [property, style.getPropertyValue(property)])),
        geometry: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
      };
    }, {
      baseSelector: contract.baseSelector,
      matchSelector: contract.matchSelector ?? contract.baseSelector,
      pseudoElement: contract.pseudoElement ?? null,
      properties: properties ?? [],
    });
    expect(result.baseMatches, `${routeCase.id}/${contract.id}: element.matches(baseSelector)`).toBeTruthy();
    expect(result.stateMatches, `${routeCase.id}/${contract.id}: intended selector state`).toBeTruthy();
    expect(result.visible, `${routeCase.id}/${contract.id}: intended locator is visible/reachable`).toBeTruthy();
    expect(result.geometry.width || result.geometry.height, `${routeCase.id}/${contract.id}: intended geometry`).toBeGreaterThan(0);
    for (const property of properties ?? []) {
      expect(result.computed[property], `${routeCase.id}/${contract.id}: computed ${property}`).not.toBe("");
    }
    records.push({
      id: contract.id,
      locator: contract.locator,
      baseSelector: contract.baseSelector,
      matchSelector: contract.matchSelector ?? contract.baseSelector,
      pseudoElement: contract.pseudoElement ?? null,
      computed: result.computed,
      geometry: result.geometry,
    });
  }
  return records;
}

async function topologySignature(page: Page): Promise<Record<string, unknown>> {
  return page.evaluate(() => ({
    mainClass: document.querySelector("main")?.className ?? "",
    modelingClass: document.querySelector(".modeling-workspace")?.className ?? "",
    stageClasses: Array.from(document.querySelectorAll("[class*='modeling-workspace-stage']"))
      .map((element) => element.className)
      .sort(),
    producerCounts: [
      ".modeling-data-plot",
      ".persistent-modeling-plot",
      ".curve-legend",
      ".engineering-plot-frame",
      ".modeling-task-ribbon",
    ].map((selector) => [selector, document.querySelectorAll(selector).length]),
  }));
}

async function assertGeometryAndIdentity(page: Page, routeCase: RouteCase, viewport: typeof viewports[number]): Promise<Record<string, unknown>> {
  const geometry = await page.evaluate(() => {
    const root = document.querySelector("main") ?? document.body;
    const rect = root.getBoundingClientRect();
    return {
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
      rootWidth: rect.width,
      rootHeight: rect.height,
      bodyText: document.body.innerText.slice(0, 1200),
    };
  });
  expect(geometry.scrollWidth as number, `${routeCase.id}@${viewport.name}: page horizontal overflow`).toBeLessThanOrEqual((geometry.innerWidth as number) + 1);
  expect((geometry.rootWidth as number), `${routeCase.id}@${viewport.name}: empty root geometry`).toBeGreaterThan(0);
  const identityText = await page.locator("body").innerText();
  expect(identityText, `${routeCase.id}@${viewport.name}: route identity`).toMatch(routeCase.identity);
  return geometry;
}

async function captureRoute(
  page: Page,
  routeCase: RouteCase,
  viewport: typeof viewports[number],
  selectorApplications: SelectorApplicationRecord[] = [],
): Promise<void> {
  if (!evidenceRoot) return;
  const root = join(evidenceRoot, phase, routeCase.id, viewport.name);
  await mkdir(root, { recursive: true });
  // The acceptance original is the exact CSS viewport. Full-page diagnostics,
  // if needed, belong outside this evidence contract.
  await page.screenshot({ path: join(root, "original.png") });
  const computed: Record<string, unknown> = {};
  for (const [crop, selector] of Object.entries(routeCase.crops)) {
    const locator = await firstVisible(page, selector);
    await expect(locator, `${routeCase.id}@${viewport.name}: ${crop} crop source`).toBeVisible();
    await locator.screenshot({ path: join(root, `${crop}.png`) });
    computed[crop] = await locator.evaluate((element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return {
        width: rect.width,
        height: rect.height,
        display: style.display,
        overflow: style.overflow,
        text: element.textContent?.slice(0, 240) ?? "",
      };
    });
  }
  const geometry = await assertGeometryAndIdentity(page, routeCase, viewport);
  await writeFile(join(root, "computed.json"), JSON.stringify({
    phase,
    route: routeCase.route,
    viewport,
    geometry,
    crops: computed,
    selectorApplications,
  }, null, 2));
}

async function assertRenderedProducers(page: Page, routeCase: RouteCase): Promise<void> {
  for (const selector of routeCase.renderedSelectors ?? []) {
    await expect(await firstVisible(page, selector), `${routeCase.id}: rendered producer ${selector}`).toBeVisible({ timeout: 30_000 });
  }
}

async function waitForModelingData(page: Page): Promise<void> {
  await expect(page.locator(".data-source-tabs")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".modeling-data-workspace")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".persistent-modeling-plot")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("region", { name: "Test Data results" })).toBeVisible({ timeout: 30_000 });
}

async function selectExactPrimaryTestData(page: Page): Promise<void> {
  const row = page.locator('.modeling-data-results tbody tr[data-document-key="CMP-DEMO-DP780-TEST-JSON"]');
  await expect(row).toHaveCount(1, { timeout: 30_000 });
  const record = row.locator(".modeling-data-record-button");
  await record.click();
  await expect(record).toHaveAttribute("aria-current", "true", { timeout: 30_000 });
  await expect(record).toHaveText("Tensile test 0001", { exact: true });
  await expect(page.locator(".modeling-workspace-stage-data polyline.data-observed")).toHaveCount(1, { timeout: 60_000 });
  await expect(page.locator(".modeling-workspace-stage-data .curve-legend")).toBeVisible({ timeout: 30_000 });
}

async function openElastomerMappingReport(page: Page): Promise<void> {
  await page.goto("/modeling?stage=fit&family=elastomer", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".family-modeling-panel")).toBeVisible({ timeout: 30_000 });
  await expect(
    page.locator('section.reference-linear-viscoelastic-workbench[aria-label="Ogden Prony card workflow"]'),
  ).toBeVisible({ timeout: 90_000 });

  // The clean synthetic fixture pre-seeds the elastomer model and reviewed
  // Neutral Material revision. The calibration workbench reads that exact
  // revision back and mounts the Neutral export producer on the Fit route.
  const exportSurface = page.locator(
    'section.neutral-solver-export[aria-label="Reviewed Neutral Material and solver card delivery"]',
  );
  await expect(exportSurface).toBeVisible({ timeout: 90_000 });
  const preflight = exportSurface.getByRole("button", { name: "Run mapping preflight", exact: true });
  await expect(preflight).toBeVisible({ timeout: 30_000 });
  await preflight.click();
  const report = exportSurface.locator(
    'section.mapping-report[aria-label="Neutral Material solver mapping report"]',
  );
  await expect(report).toBeVisible({ timeout: 90_000 });
  await expect(report.locator(".mapping-report-heading")).toBeVisible({ timeout: 30_000 });
  await expect(report.locator(".mapping-list")).toBeVisible({ timeout: 30_000 });
}

async function capturePrimaryStage(page: Page, routeCase: RouteCase, viewport: typeof viewports[number]): Promise<void> {
  await assertRenderedProducers(page, routeCase);
  const selectorApplications = await assertSelectorApplications(page, routeCase);
  const selectors = await cssomSelectors(page);
  for (const selector of routeCase.selectors) {
    expect(hasExactSelectorMembership(selectors, selector), `${routeCase.id}: CSSOM selector ${selector}`).toBeTruthy();
  }
  await assertGeometryAndIdentity(page, routeCase, viewport);
  await captureRoute(page, routeCase, viewport, selectorApplications);
}

test.describe("Issue #261 M1E5 producer-routed residual", () => {
  // Each evidence case drives five CSS viewports and writes original/crop
  // captures. Match the repository's guided-demo evidence budget; semantic
  // per-action waits remain bounded below and are intentionally unchanged.
  test.describe.configure({ mode: "serial", timeout: 180_000 });
  test.skip(!enabled, "Main-owned disposable runtime gate; set CMP_ISSUE_261_M1E5_E2E=1");

  test("authenticated Modeling Data surface renders the exact Test Data producer at five CSS viewports", async ({ context, request }) => {
    const dataRoute = routeCases.find((routeCase) => routeCase.id === "modeling-data-metal")!;
    for (const viewport of viewports) {
      const page = await openFreshDemoPage(context, request, viewport);
      try {
        await page.goto("/modeling?stage=data&family=metal", { waitUntil: "domcontentloaded" });
        await waitForModelingData(page);
        await selectExactPrimaryTestData(page);
        await capturePrimaryStage(page, dataRoute, viewport);
        if (viewport.name === "1440x900") {
          const continueToProcess = page.getByRole("button", { name: "Continue to Process", exact: true });
          await expect(continueToProcess).toBeVisible({ timeout: 30_000 });
          await continueToProcess.click();
          await expect(page.locator(".modeling-work-title h1")).toHaveText("Process Test Data", { timeout: 30_000 });
          await expect(page.locator(".modeling-work-title > span")).toHaveText("DP780 / Tensile test 0001", { exact: true });
          await expect(page.locator(".process-band-source")).toHaveText("Tensile test 0001", { exact: true });
          const currentProcessInput = page.locator(".current-process-input");
          await expect(currentProcessInput).toContainText("Tensile test 0001", { timeout: 30_000 });
          await expect(currentProcessInput.locator(".process-input-role")).toHaveText("Current", { exact: true });
          await expect(page.getByText("Blocked · choose Test Data in Data", { exact: true })).toBeVisible({ timeout: 30_000 });
          await expect(page.getByLabel("Elastic range end", { exact: true })).toBeDisabled({ timeout: 30_000 });
          await expect(page.getByRole("button", { name: "Preview changes", exact: true })).toBeDisabled({ timeout: 30_000 });
        }
      } finally {
        await page.close();
      }
    }
  });

  test("authenticated elastomer Fit journey renders the Neutral mapping producer", async ({ context, request }) => {
    const route = routeCases.find((routeCase) => routeCase.id === "modeling-fit-elastomer")!;
    for (const viewport of viewports) {
      const page = await openFreshDemoPage(context, request, viewport);
      try {
        await waitForRoute(page, route);
        await capturePrimaryStage(page, route, viewport);
      } finally {
        await page.close();
      }
    }
  });

  for (const routeCase of routeCases) {
    if (routeCase.classification === "primary" || routeCase.captureDisposition === "collapsed-equivalence" || routeCase.captureDisposition === "no-screenshot-technical") continue;
    test(`${routeCase.id} reaches its producer surface at five CSS viewports`, async ({ context, request }) => {
      for (const viewport of viewports) {
        const page = await openFreshDemoPage(context, request, viewport);
        try {
          await waitForRoute(page, routeCase);
          const selectors = await cssomSelectors(page);
          if (routeCase.classification === "negative") {
            await expect(page.locator("body")).toContainText(/Complete Data, Process, and Fit first|No saved Process Output is bound|cannot be prepared for Export|No Test Data selected|Restore inputs/i);
          } else {
            const selectorApplications = await assertSelectorApplications(page, routeCase);
            for (const selector of routeCase.selectors) {
              expect(hasExactSelectorMembership(selectors, selector), `${routeCase.id}: CSSOM selector ${selector}`).toBeTruthy();
            }
            await assertRenderedProducers(page, routeCase);
            await assertGeometryAndIdentity(page, routeCase, viewport);
            await captureRoute(page, routeCase, viewport, selectorApplications);
            continue;
          }
          await assertGeometryAndIdentity(page, routeCase, viewport);
          await captureRoute(page, routeCase, viewport);
        } finally {
          await page.close();
        }
      }
    });
  }

  for (const routeCase of routeCases.filter((candidate) => candidate.captureDisposition === "collapsed-equivalence")) {
    test(`${routeCase.id} is a durable direct-route equivalence of ${routeCase.equivalentTo}`, async ({ context, request }) => {
      const page = await openFreshDemoPage(context, request, viewports[1]);
      try {
        await waitForRoute(page, routeCase);
        const aliasSignature = await topologySignature(page);
        const canonical = routeCases.find((candidate) => candidate.id === routeCase.equivalentTo);
        expect(canonical, `${routeCase.id}: canonical equivalence target`).toBeTruthy();
        await waitForRoute(page, canonical!);
        const canonicalSignature = await topologySignature(page);
        expect(aliasSignature, `${routeCase.id}: direct route topology`).toEqual(canonicalSignature);
      } finally {
        await page.close();
      }
    });
  }

  test("1440 recovery state preserves supplied route behavior", async ({ context, request }) => {
    test.skip(!recoveryRoute, "Server-dependent exact-revision recovery is source-tested; manifest records N/A_SOURCE_TEST");
    const page = await openFreshDemoPage(context, request, viewports[1]);
    try {
      await page.goto(recoveryRoute!, { waitUntil: "domcontentloaded" });
      await expect(page.locator("body")).toBeVisible();
      const expectedPath = new URL(recoveryRoute!, page.url()).pathname;
      expect(new URL(page.url()).pathname).toBe(expectedPath);
      const recoverySurface = page.locator("[role=alert], main").first();
      await expect(recoverySurface).toBeVisible();
    } finally {
      await page.close();
    }
  });
});

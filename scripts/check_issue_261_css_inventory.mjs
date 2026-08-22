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

const FROZEN_BASE = "4d53d95ce926b96b84e47f9d942127f0853d8ed2";
const B1_SOURCE = "a26649ec9d7e689cf773ccad9dedfcb985d9ea62";
const M2_SOURCE = "be5538ec57efdd65f4104fffa733f134b3d42d87";
const M3_SOURCE = "dfc3bf00b5aafac2ac466d662f07ee4be88421eb";
const M2_FIXTURE = JSON.parse(readFileSync(
  join(ROOT, "scripts", "fixtures", "issue-261-m2-materials-css-ownership.json"),
  "utf8",
));

function historicalInventory(sourceSha) {
  return JSON.parse(execFileSync(
    "git",
    ["show", `${sourceSha}:docs/17-evidence/issue-261-css-selector-inventory.json`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
  ));
}

function selectorDescriptor(row) {
  return [
    row.source?.path ?? row.path,
    normalizeSpace(row.selector),
    (row.source?.atContext ?? row.atContext ?? []).join(" | "),
    row.declarations?.signatureSha256 ?? row.declarationSignature ?? "",
  ].join("\0");
}

function m2ResidualBatches() {
  const baseline = historicalInventory(FROZEN_BASE);
  const byId = new Map(baseline.selectors.map((row) => [row.id, row]));
  const byDescriptor = new Map();
  for (const [batch, ids] of [["M4-shared-cleanup", M2_FIXTURE.ids.m4], ["HOLD-owner-or-cross-feature-split", M2_FIXTURE.ids.hold]]) {
    for (const id of ids) {
      const row = byId.get(id);
      if (!row) continue;
      byDescriptor.set(selectorDescriptor(row), batch);
    }
  }
  return byDescriptor;
}

const M2_RESIDUAL_BATCHES = m2ResidualBatches();

const OWNERSHIP_CHECKPOINTS = [
  {
    unit: "B1-modeling-stage-css-ownership",
    sourceCommit: B1_SOURCE,
    frozenBase: FROZEN_BASE,
    evidence: "docs/17-evidence/issue-261-b1-modeling-stage-css-ownership.md",
    disposition: "APPROVE",
    standalone: {
      selectorRows: 2869,
      cssRuleGroups: 2332,
      crossCssDuplicateRows: 7,
      movedRows: 505,
      deferredRows: 38,
      normalizationPeers: 7,
    },
  },
  {
    unit: "M2-materials-css-ownership",
    sourceCommit: M2_SOURCE,
    frozenBase: FROZEN_BASE,
    evidence: "docs/17-evidence/issue-261-m2-materials-css-ownership.md",
    disposition: "APPROVE",
    standalone: {
      selectorRows: M2_FIXTURE.expected.postLegacyRows,
      cssRuleGroups: M2_FIXTURE.expected.postLegacyRuleGroups,
      movedRows: M2_FIXTURE.expected.materialsRows,
      movedGroups: M2_FIXTURE.expected.materialsRuleGroups,
      fullGroups: M2_FIXTURE.expected.materialsFullGroups,
      partialGroups: M2_FIXTURE.expected.materialsMixedGroups,
    },
  },
  {
    unit: "M3-governance-css-ownership",
    sourceCommit: M3_SOURCE,
    frozenBase: FROZEN_BASE,
    evidence: "docs/17-evidence/issue-261-m3-css-ownership-governance.json",
    disposition: "APPROVE",
    standalone: {
      selectorRows: 2868,
      cssRuleGroups: 2343,
      movedOwnerRows: 505,
      retainedPeerRows: 1,
      movedTargetRows: 506,
      fullGroups: 356,
      partialGroups: 21,
    },
  },
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

const COMPLETED_M1A3 = {
  id: "M1A3-modeling-data-import-diagnostics",
  historicalMemberIds: [
    "CSS-1060",
    "CSS-1061",
    "CSS-1062",
    "CSS-1063",
    "CSS-1064",
    "CSS-1065",
    "CSS-1066",
  ],
  exactLegacySelectors: [
    ".data-import-diagnostics",
    ".data-import-diagnostics header",
    ".data-import-diagnostics header strong",
    ".data-import-diagnostics > div",
    ".data-import-diagnostics table",
    ".data-import-diagnostics th",
    ".data-import-diagnostics td",
  ],
};

const COMPLETED_M1A4 = {
  id: "M1A4-modeling-data-raw-source-preview",
  historicalMemberIds: [
    "CSS-1009",
    "CSS-1011",
    "CSS-1013",
    "CSS-1014",
    "CSS-1017",
    "CSS-1019",
    "CSS-1044",
    "CSS-1045",
    "CSS-1046",
    "CSS-1047",
    "CSS-1504",
    "CSS-1505",
    "CSS-1615",
    "CSS-1617",
    "CSS-1624",
    "CSS-1632",
    "CSS-1633",
  ],
  exactLegacySelectors: [
    ".data-raw-table",
    ".data-raw-table table",
    ".data-raw-table th",
    ".data-raw-table td",
    ".data-source-decision-grid .data-raw-table",
    ".data-source-decision-grid .data-raw-table table",
    ".data-source-decision-grid .data-raw-table th",
    ".data-source-decision-grid .data-raw-table td",
    ".modeling-main-surface.has-data-split .data-source-decision-grid .data-raw-table th",
    ".modeling-main-surface.has-data-split .data-source-decision-grid .data-raw-table td",
  ],
};

const COMPLETED_M1A5 = {
  id: "M1A5-modeling-data-library-source-list",
  historicalMemberIds: [
    "CSS-0910",
    "CSS-1016",
    "CSS-1017",
    "CSS-1018",
    "CSS-1019",
    "CSS-1020",
    "CSS-1021",
    "CSS-1022",
    "CSS-1023",
    "CSS-1024",
    "CSS-1025",
    "CSS-1513",
    "CSS-1517",
    "CSS-1518",
    "CSS-1519",
    "CSS-1520",
    "CSS-1521",
    "CSS-1522",
    "CSS-1523",
    "CSS-1524",
    "CSS-1525",
    "CSS-1526",
    "CSS-1595",
    "CSS-1596",
    "CSS-1597",
    "CSS-1598",
    "CSS-1599",
    "CSS-1600",
    "CSS-1601",
  ],
  exactLegacySelectors: [
    ".modeling-task-ribbon:has(.data-library-list)",
    ".data-library-list",
    ".data-library-scroll-shell",
    ".data-library-list:focus-visible",
    ".data-library-list article",
    ".data-library-list article.active",
    ".data-library-row",
    ".data-library-row span",
    ".data-library-row small",
    ".data-library-row:hover",
    ".data-library-row:focus-visible",
    ".data-library-pane",
    ".data-library-pane .data-library-scroll-shell",
    ".data-library-pane .data-library-list",
    ".data-library-pane .data-library-row",
    ".data-library-pane .data-library-row > strong",
    ".data-library-pane .data-library-warning",
    ".data-library-pane .data-library-row > span",
    ".data-library-pane .data-library-row > small:not(.data-library-warning)",
    ".data-library-row :is(strong, td)",
    ".data-library-pane .data-library-row > :is(span, small)",
    ".data-library-row :is(span, small)",
  ],
};

const COMPLETED_M1A6 = {
  id: "M1A6-modeling-data-curve-row-label",
  historicalMemberIds: ["CSS-1497", "CSS-1498", "CSS-1499"],
  exactLegacySelectors: [
    ".modeling-data-curve-tree .curve-row-label",
    ".modeling-data-curve-tree .curve-row-label > span",
    ".modeling-data-curve-tree .curve-row-label strong",
  ],
};

const COMPLETED_M1A7 = {
  id: "M1A7-modeling-data-mapping-heading",
  historicalMemberIds: ["CSS-1019", "CSS-1020", "CSS-1021", "CSS-1579"],
  exactLegacySelectors: [
    ".data-mapping-heading",
    ".data-mapping-heading strong",
    ".data-mapping-heading span",
  ],
};

const COMPLETED_M1A8 = {
  id: "M1A8-modeling-data-optional-channel",
  historicalMemberIds: ["CSS-1021", "CSS-1022", "CSS-1460", "CSS-1461"],
  exactLegacySelectors: [
    ".data-mapping-decision .data-intake-attention > label.data-optional-channel",
    ".data-mapping-decision .data-intake-attention > label.data-optional-channel > input",
    ".modeling-main-surface:has(.data-source-decision-grid) .data-source-decision-grid .data-mapping-decision .data-intake-attention > label.data-optional-channel",
    ".modeling-main-surface:has(.data-source-decision-grid) .data-source-decision-grid .data-mapping-decision .data-intake-attention > label.data-optional-channel > input",
  ],
};

const COMPLETED_M1A9 = {
  id: "M1A9-modeling-data-mapping-table",
  historicalMemberIds: [
    "CSS-1001",
    "CSS-1008",
    "CSS-1009",
    "CSS-1010",
    "CSS-1011",
    "CSS-1012",
    "CSS-1013",
    "CSS-1014",
    "CSS-1021",
    "CSS-1036",
    "CSS-1461",
    "CSS-1474",
    "CSS-1475",
    "CSS-1564",
    "CSS-1565",
    "CSS-1571",
    "CSS-1577",
    "CSS-1578",
    "CSS-1584",
  ],
  exactLegacySelectors: [
    ".data-mapping-table",
    ".data-mapping-table table",
    ".data-mapping-table th",
    ".data-mapping-table td",
    ".data-mapping-table select",
    ".data-mapping-decision .data-mapping-table select",
    ".data-mapping-table td:last-child",
    ".modeling-main-surface.has-data-split .data-mapping-decision .data-mapping-table select",
    ".modeling-main-surface.has-data-split .data-mapping-decision .data-mapping-table th",
    ".modeling-main-surface.has-data-split .data-mapping-decision .data-mapping-table td",
  ],
};

const COMPLETED_M1A10 = {
  id: "M1A10-modeling-data-split-frame",
  historicalMemberIds: [
    "CSS-1431",
    "CSS-1432",
    "CSS-1433",
    "CSS-1434",
    "CSS-1435",
    "CSS-1436",
    "CSS-1437",
    "CSS-1438",
    "CSS-1439",
    "CSS-1440",
    "CSS-1441",
    "CSS-1442",
  ],
  exactLegacySelectors: [
    ".modeling-main-surface.has-data-split",
    ".modeling-data-split",
    ".modeling-data-ribbon-panel",
    ".modeling-data-ribbon-panel > .modeling-task-ribbon",
    ".modeling-data-ribbon-panel > .modeling-task-ribbon-scrollable",
    ".modeling-data-plot-panel > .persistent-modeling-plot",
    ".modeling-data-divider",
    ".modeling-data-divider:hover",
    ".modeling-data-divider:focus-visible",
    ".modeling-data-divider[data-separator=\"modeling-data-ribbon-plot-divider\"]:active",
  ],
};

const COMPLETED_M1A11 = {
  id: "M1A11-modeling-data-file-details",
  historicalMemberIds: [
    "CSS-1436",
    "CSS-1437",
    "CSS-1438",
    "CSS-1452",
    "CSS-1548",
  ],
  exactLegacySelectors: [
    ".modeling-main-surface:has(.data-source-decision-grid) .data-source-advanced:not([open])",
    ".modeling-main-surface:has(.data-source-decision-grid) .data-source-advanced:not([open]) > summary",
    ".modeling-main-surface:has(.data-source-decision-grid) .data-source-advanced:not([open]) > div",
    ".modeling-main-surface.has-data-split .data-source-advanced:not([open]) > summary",
    ".data-source-advanced > :is(summary, div)",
  ],
};

const COMPLETED_M1A12 = {
  id: "M1A12-modeling-data-mapping-change-actions",
  historicalMemberIds: [
    "CSS-1014",
    "CSS-1017",
    "CSS-1018",
    "CSS-1019",
    "CSS-1021",
    "CSS-1439",
    "CSS-1440",
    "CSS-1441",
    "CSS-1443",
    "CSS-1445",
    "CSS-1449",
    "CSS-1451",
    "CSS-1452",
    "CSS-1453",
    "CSS-1455",
    "CSS-1456",
    "CSS-1458",
    "CSS-1459",
    "CSS-1540",
    "CSS-1549",
    "CSS-1558",
  ],
  exactLegacySelectors: [
    ".data-mapping-recovery-row",
    ".data-mapping-recovery-detail",
    ".data-mapping-recovery-detail > label",
    ".data-mapping-recovery-detail input",
    ".data-mapping-actions",
    ".modeling-main-surface.has-data-split .data-mapping-recovery-detail",
    ".modeling-main-surface.has-data-split .data-mapping-recovery-detail > label",
    ".modeling-main-surface.has-data-split .data-mapping-recovery-detail > label > input",
    ".modeling-main-surface.has-data-split .data-mapping-actions",
    ".modeling-main-surface.has-data-split .data-mapping-recovery-row",
  ],
};

const COMPLETED_M1A13 = {
  id: "M1A13-modeling-data-local-scrollport",
  historicalMemberIds: [
    "CSS-0910",
    "CSS-0911",
    "CSS-0912",
    "CSS-0971",
    "CSS-0986",
    "CSS-1007",
  ],
  exactLegacySelectors: [
    ".modeling-task-ribbon:has(.data-intake-local)",
    ".modeling-task-ribbon:has(.data-intake-local) .modeling-data-intake",
    ".modeling-task-ribbon:has(.data-intake-local) .data-intake-local",
    ".data-intake-local",
  ],
};

const COMPLETED_M1A14 = {
  id: "M1A14-modeling-data-mapping-blocker",
  historicalMemberIds: [
    "CSS-1007",
    "CSS-1014",
    "CSS-1015",
    "CSS-1511",
  ],
  exactLegacySelectors: [
    ".data-mapping-decision .data-mapping-blockers",
    ".data-mapping-blockers",
    ".data-mapping-blockers strong",
  ],
};

const COMPLETED_M1A15 = {
  id: "M1A15-modeling-data-intake-surface",
  historicalMemberIds: [
    "CSS-0966",
    "CSS-0969",
    "CSS-1429",
    "CSS-1507",
  ],
  exactLegacySelectors: [
    ".modeling-data-intake",
    ".modeling-main-surface.has-data-split .modeling-data-intake",
  ],
};

const COMPLETED_M1A16 = {
  id: "M1A16-modeling-data-local-import-controls",
  historicalMemberIds: [
    "CSS-1416",
    "CSS-1418",
    "CSS-1420",
    "CSS-1436",
    "CSS-1437",
    "CSS-1438",
    "CSS-1439",
    "CSS-1440",
    "CSS-1441",
    "CSS-1442",
    "CSS-1443",
    "CSS-1445",
    "CSS-1520",
    "CSS-1521",
    "CSS-1522",
    "CSS-1523",
  ],
  exactLegacySelectors: [
    ".modeling-main-surface:has(.data-source-decision-grid) .data-intake-local > .data-intake-row > label",
    ".modeling-main-surface:has(.data-source-decision-grid) .data-intake-local > .data-intake-row > label > :is(input, select)",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row select[name=\"local-test-run\"]",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > label",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > button",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row input[type=\"file\"]",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row input[type=\"file\"]::file-selector-button",
    ".modeling-main-surface.has-data-split .data-intake-local > .data-intake-row > button:disabled",
  ],
};

const COMPLETED_M1A17 = {
  id: "M1A17-modeling-data-mapping-attention",
  historicalMemberIds: [
    "CSS-0967",
    "CSS-0970",
    "CSS-0974",
    "CSS-0975",
    "CSS-0982",
    "CSS-0984",
    "CSS-0986",
    "CSS-0988",
    "CSS-0999",
    "CSS-1002",
    "CSS-1003",
    "CSS-1004",
    "CSS-1416",
    "CSS-1417",
    "CSS-1419",
    "CSS-1494",
    "CSS-1502",
  ],
  exactLegacySelectors: [
    ".data-intake-attention",
    ".data-intake-attention label",
    ".data-intake-attention input",
    ".data-intake-attention select",
    ".data-intake-attention > strong",
    ".data-intake-attention label select:first-of-type",
    ".data-intake-attention > p",
    ".data-mapping-decision .data-intake-attention",
    ".data-mapping-decision .data-intake-attention > strong",
    ".data-mapping-decision .data-intake-attention > label",
    ".modeling-main-surface:has(.data-source-decision-grid) .data-source-decision-grid .data-mapping-decision .data-intake-attention > label",
    ".modeling-main-surface:has(.data-source-decision-grid) .data-source-decision-grid .data-mapping-decision .data-intake-attention > label > :is(input, select)",
    ".modeling-main-surface.has-data-split .data-source-decision-grid .data-mapping-decision .data-intake-attention > label > select[name=\"local-data-schema\"]",
    ".data-intake-attention :is(input, select)",
  ],
};

const COMPLETED_M1A18 = {
  id: "M1A18-modeling-data-mapping-resolved",
  historicalMemberIds: [
    "CSS-0969",
    "CSS-0972",
    "CSS-0973",
    "CSS-0978",
    "CSS-0979",
    "CSS-0980",
    "CSS-0981",
    "CSS-0998",
    "CSS-1479",
    "CSS-1486",
  ],
  exactLegacySelectors: [
    ".data-mapping-resolved label",
    ".data-mapping-resolved input",
    ".data-mapping-resolved select",
    ".data-mapping-resolved > span",
    ".data-mapping-resolved > strong",
    ".data-mapping-resolved label select:first-of-type",
    ".data-mapping-decision > .data-mapping-resolved",
    ".data-mapping-resolved :is(input, select)",
  ],
};

const COMPLETED_M1A19 = {
  id: "M1A19-modeling-data-intake-field-rows",
  historicalMemberIds: [
    "CSS-0966",
    "CSS-0967",
    "CSS-0968",
    "CSS-0969",
    "CSS-0970",
    "CSS-0971",
    "CSS-0975",
    "CSS-1470",
    "CSS-1476",
  ],
  exactLegacySelectors: [
    ".data-intake-row",
    ".data-intake-row label",
    ".data-intake-row input",
    ".data-intake-row select",
    ".data-intake-row p",
    ".data-intake-message",
    ".data-intake-row :is(input, select)",
  ],
};

const COMPLETED_M1A20 = {
  id: "M1A20-modeling-data-mapping-decision-frame",
  historicalMemberIds: [
    "CSS-0977",
    "CSS-0978",
    "CSS-1388",
    "CSS-1389",
  ],
  exactLegacySelectors: [
    ".data-mapping-decision",
    ".data-mapping-decision .mapping-context-row",
    ".modeling-main-surface:has(.data-intake-local) .data-source-decision-grid",
    ".modeling-main-surface.has-data-split .data-mapping-decision select[name=\"local-data-schema\"]",
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

export function parseCss(path, source, loadRank) {
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

  for (const row of rows) {
    const residualBatch = M2_RESIDUAL_BATCHES.get(selectorDescriptor(row));
    if (residualBatch) row.owner.migrationBatch = residualBatch;
  }

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
    [
      COMPLETED_M1A3.id,
      rows.filter((row) => COMPLETED_M1A3.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A4.id,
      rows.filter((row) => COMPLETED_M1A4.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A5.id,
      rows.filter((row) => COMPLETED_M1A5.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A6.id,
      rows.filter((row) => COMPLETED_M1A6.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A7.id,
      rows.filter((row) => COMPLETED_M1A7.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A8.id,
      rows.filter((row) => COMPLETED_M1A8.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A9.id,
      rows.filter((row) => COMPLETED_M1A9.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A10.id,
      rows.filter((row) => COMPLETED_M1A10.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A11.id,
      rows.filter((row) => COMPLETED_M1A11.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A12.id,
      rows.filter((row) => COMPLETED_M1A12.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A13.id,
      rows.filter((row) => COMPLETED_M1A13.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A14.id,
      rows.filter((row) => COMPLETED_M1A14.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A15.id,
      rows.filter((row) => COMPLETED_M1A15.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A16.id,
      rows.filter((row) => COMPLETED_M1A16.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A17.id,
      rows.filter((row) => COMPLETED_M1A17.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A18.id,
      rows.filter((row) => COMPLETED_M1A18.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A19.id,
      rows.filter((row) => COMPLETED_M1A19.exactLegacySelectors.includes(row.selector)),
    ],
    [
      COMPLETED_M1A20.id,
      rows.filter((row) => COMPLETED_M1A20.exactLegacySelectors.includes(row.selector)),
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
            cssRuleGroups: 2818,
            selectorRows: 3565,
            crossCssDuplicateRows: 13,
          },
        },
        {
          id: COMPLETED_M1A3.id,
          historicalMemberIds: COMPLETED_M1A3.historicalMemberIds,
          selectorRowsRemoved: 7,
          touchedRuleGroups: 6,
          fullyRemovedRuleGroups: 6,
          partiallyShrunkRuleGroups: 0,
          exactLegacySelectors: COMPLETED_M1A3.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A3.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2812,
            selectorRows: 3558,
            crossCssDuplicateRows: 13,
          },
        },
        {
          id: COMPLETED_M1A4.id,
          historicalMemberIds: COMPLETED_M1A4.historicalMemberIds,
          selectorRowsRemoved: 17,
          touchedRuleGroups: 12,
          fullyRemovedRuleGroups: 4,
          partiallyShrunkRuleGroups: 8,
          exactLegacySelectors: COMPLETED_M1A4.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A4.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2808,
            selectorRows: 3541,
            crossCssDuplicateRows: 13,
          },
        },
        {
          id: COMPLETED_M1A5.id,
          historicalMemberIds: COMPLETED_M1A5.historicalMemberIds,
          selectorRowsRemoved: 29,
          touchedRuleGroups: 21,
          fullyRemovedRuleGroups: 21,
          partiallyShrunkRuleGroups: 0,
          exactLegacySelectors: COMPLETED_M1A5.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A5.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2787,
            selectorRows: 3512,
            crossCssDuplicateRows: 13,
          },
        },
        {
          id: COMPLETED_M1A6.id,
          historicalMemberIds: COMPLETED_M1A6.historicalMemberIds,
          selectorRowsRemoved: 3,
          touchedRuleGroups: 3,
          fullyRemovedRuleGroups: 3,
          partiallyShrunkRuleGroups: 0,
          exactLegacySelectors: COMPLETED_M1A6.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A6.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2784,
            selectorRows: 3509,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A7.id,
          historicalMemberIds: COMPLETED_M1A7.historicalMemberIds,
          selectorRowsRemoved: 4,
          touchedRuleGroups: 4,
          fullyRemovedRuleGroups: 3,
          partiallyShrunkRuleGroups: 1,
          exactLegacySelectors: COMPLETED_M1A7.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A7.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2781,
            selectorRows: 3505,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A8.id,
          historicalMemberIds: COMPLETED_M1A8.historicalMemberIds,
          selectorRowsRemoved: 4,
          touchedRuleGroups: 4,
          fullyRemovedRuleGroups: 4,
          partiallyShrunkRuleGroups: 0,
          exactLegacySelectors: COMPLETED_M1A8.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A8.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2777,
            selectorRows: 3501,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A9.id,
          historicalMemberIds: COMPLETED_M1A9.historicalMemberIds,
          selectorRowsRemoved: 19,
          touchedRuleGroups: 15,
          fullyRemovedRuleGroups: 10,
          partiallyShrunkRuleGroups: 5,
          exactLegacySelectors: COMPLETED_M1A9.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A9.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2767,
            selectorRows: 3482,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A10.id,
          historicalMemberIds: COMPLETED_M1A10.historicalMemberIds,
          selectorRowsRemoved: 12,
          touchedRuleGroups: 10,
          fullyRemovedRuleGroups: 10,
          partiallyShrunkRuleGroups: 0,
          exactLegacySelectors: COMPLETED_M1A10.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A10.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2757,
            selectorRows: 3470,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A11.id,
          historicalMemberIds: COMPLETED_M1A11.historicalMemberIds,
          selectorRowsRemoved: 5,
          touchedRuleGroups: 5,
          fullyRemovedRuleGroups: 4,
          partiallyShrunkRuleGroups: 1,
          exactLegacySelectors: COMPLETED_M1A11.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A11.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2753,
            selectorRows: 3465,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A12.id,
          historicalMemberIds: COMPLETED_M1A12.historicalMemberIds,
          selectorRowsRemoved: 21,
          touchedRuleGroups: 20,
          fullyRemovedRuleGroups: 15,
          partiallyShrunkRuleGroups: 5,
          exactLegacySelectors: COMPLETED_M1A12.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A12.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2738,
            selectorRows: 3444,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A13.id,
          historicalMemberIds: COMPLETED_M1A13.historicalMemberIds,
          selectorRowsRemoved: 6,
          touchedRuleGroups: 5,
          fullyRemovedRuleGroups: 4,
          partiallyShrunkRuleGroups: 1,
          exactLegacySelectors: COMPLETED_M1A13.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A13.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2734,
            selectorRows: 3438,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A14.id,
          historicalMemberIds: COMPLETED_M1A14.historicalMemberIds,
          selectorRowsRemoved: 4,
          touchedRuleGroups: 4,
          fullyRemovedRuleGroups: 3,
          partiallyShrunkRuleGroups: 1,
          exactLegacySelectors: COMPLETED_M1A14.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A14.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2731,
            selectorRows: 3434,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A15.id,
          historicalMemberIds: COMPLETED_M1A15.historicalMemberIds,
          selectorRowsRemoved: 4,
          touchedRuleGroups: 4,
          fullyRemovedRuleGroups: 3,
          partiallyShrunkRuleGroups: 1,
          exactLegacySelectors: COMPLETED_M1A15.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A15.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2728,
            selectorRows: 3430,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A16.id,
          historicalMemberIds: COMPLETED_M1A16.historicalMemberIds,
          selectorRowsRemoved: 16,
          touchedRuleGroups: 13,
          fullyRemovedRuleGroups: 8,
          partiallyShrunkRuleGroups: 5,
          exactLegacySelectors: COMPLETED_M1A16.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A16.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2720,
            selectorRows: 3414,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A17.id,
          historicalMemberIds: COMPLETED_M1A17.historicalMemberIds,
          selectorRowsRemoved: 17,
          touchedRuleGroups: 16,
          fullyRemovedRuleGroups: 7,
          partiallyShrunkRuleGroups: 9,
          exactLegacySelectors: COMPLETED_M1A17.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A17.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2713,
            selectorRows: 3397,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A18.id,
          historicalMemberIds: COMPLETED_M1A18.historicalMemberIds,
          selectorRowsRemoved: 10,
          touchedRuleGroups: 9,
          fullyRemovedRuleGroups: 4,
          partiallyShrunkRuleGroups: 5,
          exactLegacySelectors: COMPLETED_M1A18.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A18.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2709,
            selectorRows: 3387,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A19.id,
          historicalMemberIds: COMPLETED_M1A19.historicalMemberIds,
          selectorRowsRemoved: 9,
          touchedRuleGroups: 8,
          fullyRemovedRuleGroups: 6,
          partiallyShrunkRuleGroups: 2,
          exactLegacySelectors: COMPLETED_M1A19.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A19.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2703,
            selectorRows: 3378,
            crossCssDuplicateRows: 14,
          },
        },
        {
          id: COMPLETED_M1A20.id,
          historicalMemberIds: COMPLETED_M1A20.historicalMemberIds,
          selectorRowsRemoved: 4,
          touchedRuleGroups: 4,
          fullyRemovedRuleGroups: 4,
          partiallyShrunkRuleGroups: 0,
          exactLegacySelectors: COMPLETED_M1A20.exactLegacySelectors,
          residualExactSelectorRows: completedPacketResidualRows
            .get(COMPLETED_M1A20.id)
            .map((row) => row.id),
          actualAfter: {
            cssRuleGroups: 2699,
            selectorRows: 3374,
            crossCssDuplicateRows: 14,
          },
        },
      ],
      checkpoints: OWNERSHIP_CHECKPOINTS,
      combinedB4: {
        unit: "B4-combined-css-ownership-integration",
        sourceCommit: sourceSha,
        frozenBase: FROZEN_BASE,
        status: "MAIN-REQUIRED",
        liveAcceptance: "pending Main live acceptance",
        handoffs: ["B1-modeling-stage-css-ownership", "M2-materials-css-ownership", "M3-governance-css-ownership"],
        current: {
          selectorRows: rows.length,
          cssRuleGroups: cssRuleGroupCount,
          crossCssDuplicateRows: flagCounts.crossCssDuplicate,
          byMigrationBatch: countBy(rows, (row) => row.owner.migrationBatch),
        },
        residualRouting: {
          "M1A-modeling-data": 9,
          "M1B-modeling-process": 29,
          "M1E-modeling-shell-and-family": 383,
          "HOLD-owner-or-cross-feature-split": 504,
          "M4-shared-cleanup": 314,
          "M6-zero-consumer-removal-candidate": 533,
        },
        note: "Combined source inventory only; no live DOM, viewport, or product-owner acceptance is asserted here.",
      },
      nextBoundedUnit: {
        id: "M1A21-modeling-data-component-region",
        status: "owner-packet-required",
        scope: "Select one remaining M1A Data component region from the regenerated inventory after M1A20; do not migrate all remaining M1A rows together.",
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
  const completedM1A3 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A3.id,
  );
  if (!completedM1A3) {
    errors.push("completed M1A3 packet is missing");
  } else {
    if (completedM1A3.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A3 selectors remain in legacy CSS: ${completedM1A3.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A3.selectorRowsRemoved !== 7
        || completedM1A3.touchedRuleGroups !== 6
        || completedM1A3.fullyRemovedRuleGroups !== 6
        || completedM1A3.partiallyShrunkRuleGroups !== 0) {
      errors.push("completed M1A3 structural delta does not match the approved 7/6/6/0 packet");
    }
    if (completedM1A3.actualAfter.cssRuleGroups !== 2812
        || completedM1A3.actualAfter.selectorRows !== 3558
        || completedM1A3.actualAfter.crossCssDuplicateRows !== 13) {
      errors.push(`completed M1A3 actual delta is ${JSON.stringify(completedM1A3.actualAfter)}`);
    }
  }
  const completedM1A4 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A4.id,
  );
  if (!completedM1A4) {
    errors.push("completed M1A4 packet is missing");
  } else {
    if (completedM1A4.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A4 selectors remain in legacy CSS: ${completedM1A4.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A4.selectorRowsRemoved !== 17
        || completedM1A4.touchedRuleGroups !== 12
        || completedM1A4.fullyRemovedRuleGroups !== 4
        || completedM1A4.partiallyShrunkRuleGroups !== 8) {
      errors.push("completed M1A4 structural delta does not match the approved 17/12/4/8 packet");
    }
    if (completedM1A4.actualAfter.cssRuleGroups !== 2808
        || completedM1A4.actualAfter.selectorRows !== 3541
        || completedM1A4.actualAfter.crossCssDuplicateRows !== 13) {
      errors.push(`completed M1A4 actual delta is ${JSON.stringify(completedM1A4.actualAfter)}`);
    }
  }
  const completedM1A5 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A5.id,
  );
  if (!completedM1A5) {
    errors.push("completed M1A5 packet is missing");
  } else {
    if (completedM1A5.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A5 selectors remain in legacy CSS: ${completedM1A5.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A5.selectorRowsRemoved !== 29
        || completedM1A5.touchedRuleGroups !== 21
        || completedM1A5.fullyRemovedRuleGroups !== 21
        || completedM1A5.partiallyShrunkRuleGroups !== 0) {
      errors.push("completed M1A5 structural delta does not match the approved 29/21/21/0 packet");
    }
    if (completedM1A5.actualAfter.cssRuleGroups !== 2787
        || completedM1A5.actualAfter.selectorRows !== 3512
        || completedM1A5.actualAfter.crossCssDuplicateRows !== 13) {
      errors.push(`completed M1A5 actual delta is ${JSON.stringify(completedM1A5.actualAfter)}`);
    }
  }
  const completedM1A6 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A6.id,
  );
  if (!completedM1A6) {
    errors.push("completed M1A6 packet is missing");
  } else {
    if (completedM1A6.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A6 selectors remain in legacy CSS: ${completedM1A6.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A6.selectorRowsRemoved !== 3
        || completedM1A6.touchedRuleGroups !== 3
        || completedM1A6.fullyRemovedRuleGroups !== 3
        || completedM1A6.partiallyShrunkRuleGroups !== 0) {
      errors.push("completed M1A6 structural delta does not match the approved 3/3/3/0 packet");
    }
    if (completedM1A6.actualAfter.cssRuleGroups !== 2784
        || completedM1A6.actualAfter.selectorRows !== 3509
        || completedM1A6.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A6 actual delta is ${JSON.stringify(completedM1A6.actualAfter)}`);
    }
  }
  const completedM1A7 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A7.id,
  );
  if (!completedM1A7) {
    errors.push("completed M1A7 packet is missing");
  } else {
    if (completedM1A7.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A7 selectors remain in legacy CSS: ${completedM1A7.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A7.selectorRowsRemoved !== 4
        || completedM1A7.touchedRuleGroups !== 4
        || completedM1A7.fullyRemovedRuleGroups !== 3
        || completedM1A7.partiallyShrunkRuleGroups !== 1) {
      errors.push("completed M1A7 structural delta does not match the approved 4/4/3/1 packet");
    }
    if (completedM1A7.actualAfter.cssRuleGroups !== 2781
        || completedM1A7.actualAfter.selectorRows !== 3505
        || completedM1A7.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A7 actual delta is ${JSON.stringify(completedM1A7.actualAfter)}`);
    }
  }
  const completedM1A8 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A8.id,
  );
  if (!completedM1A8) {
    errors.push("completed M1A8 packet is missing");
  } else {
    if (completedM1A8.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A8 selectors remain in legacy CSS: ${completedM1A8.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A8.selectorRowsRemoved !== 4
        || completedM1A8.touchedRuleGroups !== 4
        || completedM1A8.fullyRemovedRuleGroups !== 4
        || completedM1A8.partiallyShrunkRuleGroups !== 0) {
      errors.push("completed M1A8 structural delta does not match the approved 4/4/4/0 packet");
    }
    if (completedM1A8.actualAfter.cssRuleGroups !== 2777
        || completedM1A8.actualAfter.selectorRows !== 3501
        || completedM1A8.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A8 actual delta is ${JSON.stringify(completedM1A8.actualAfter)}`);
    }
  }
  const completedM1A9 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A9.id,
  );
  if (!completedM1A9) {
    errors.push("completed M1A9 packet is missing");
  } else {
    if (completedM1A9.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A9 selectors remain in legacy CSS: ${completedM1A9.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A9.selectorRowsRemoved !== 19
        || completedM1A9.touchedRuleGroups !== 15
        || completedM1A9.fullyRemovedRuleGroups !== 10
        || completedM1A9.partiallyShrunkRuleGroups !== 5) {
      errors.push("completed M1A9 structural delta does not match the approved 19/15/10/5 packet");
    }
    if (completedM1A9.actualAfter.cssRuleGroups !== 2767
        || completedM1A9.actualAfter.selectorRows !== 3482
        || completedM1A9.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A9 actual delta is ${JSON.stringify(completedM1A9.actualAfter)}`);
    }
  }
  const completedM1A10 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A10.id,
  );
  if (!completedM1A10) {
    errors.push("completed M1A10 packet is missing");
  } else {
    if (completedM1A10.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A10 selectors remain in legacy CSS: ${completedM1A10.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A10.selectorRowsRemoved !== 12
        || completedM1A10.touchedRuleGroups !== 10
        || completedM1A10.fullyRemovedRuleGroups !== 10
        || completedM1A10.partiallyShrunkRuleGroups !== 0) {
      errors.push("completed M1A10 structural delta does not match the approved 12/10/10/0 packet");
    }
    if (completedM1A10.actualAfter.cssRuleGroups !== 2757
        || completedM1A10.actualAfter.selectorRows !== 3470
        || completedM1A10.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A10 actual delta is ${JSON.stringify(completedM1A10.actualAfter)}`);
    }
  }
  const completedM1A11 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A11.id,
  );
  if (!completedM1A11) {
    errors.push("completed M1A11 packet is missing");
  } else {
    if (completedM1A11.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A11 selectors remain in legacy CSS: ${completedM1A11.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A11.selectorRowsRemoved !== 5
        || completedM1A11.touchedRuleGroups !== 5
        || completedM1A11.fullyRemovedRuleGroups !== 4
        || completedM1A11.partiallyShrunkRuleGroups !== 1) {
      errors.push("completed M1A11 structural delta does not match the approved 5/5/4/1 packet");
    }
    if (completedM1A11.actualAfter.cssRuleGroups !== 2753
        || completedM1A11.actualAfter.selectorRows !== 3465
        || completedM1A11.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A11 actual delta is ${JSON.stringify(completedM1A11.actualAfter)}`);
    }
  }
  const completedM1A12 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A12.id,
  );
  if (!completedM1A12) {
    errors.push("completed M1A12 packet is missing");
  } else {
    if (completedM1A12.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A12 selectors remain in legacy CSS: ${completedM1A12.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A12.selectorRowsRemoved !== 21
        || completedM1A12.touchedRuleGroups !== 20
        || completedM1A12.fullyRemovedRuleGroups !== 15
        || completedM1A12.partiallyShrunkRuleGroups !== 5) {
      errors.push("completed M1A12 structural delta does not match the approved 21/20/15/5 packet");
    }
    if (completedM1A12.actualAfter.cssRuleGroups !== 2738
        || completedM1A12.actualAfter.selectorRows !== 3444
        || completedM1A12.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A12 actual delta is ${JSON.stringify(completedM1A12.actualAfter)}`);
    }
  }
  const completedM1A13 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A13.id,
  );
  if (!completedM1A13) {
    errors.push("completed M1A13 packet is missing");
  } else {
    if (completedM1A13.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A13 selectors remain in legacy CSS: ${completedM1A13.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A13.selectorRowsRemoved !== 6
        || completedM1A13.touchedRuleGroups !== 5
        || completedM1A13.fullyRemovedRuleGroups !== 4
        || completedM1A13.partiallyShrunkRuleGroups !== 1) {
      errors.push("completed M1A13 structural delta does not match the approved 6/5/4/1 packet");
    }
    if (completedM1A13.actualAfter.cssRuleGroups !== 2734
        || completedM1A13.actualAfter.selectorRows !== 3438
        || completedM1A13.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A13 actual delta is ${JSON.stringify(completedM1A13.actualAfter)}`);
    }
  }
  const completedM1A14 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A14.id,
  );
  if (!completedM1A14) {
    errors.push("completed M1A14 packet is missing");
  } else {
    if (completedM1A14.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A14 selectors remain in legacy CSS: ${completedM1A14.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A14.selectorRowsRemoved !== 4
        || completedM1A14.touchedRuleGroups !== 4
        || completedM1A14.fullyRemovedRuleGroups !== 3
        || completedM1A14.partiallyShrunkRuleGroups !== 1) {
      errors.push("completed M1A14 structural delta does not match the approved 4/4/3/1 packet");
    }
    if (completedM1A14.actualAfter.cssRuleGroups !== 2731
        || completedM1A14.actualAfter.selectorRows !== 3434
        || completedM1A14.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A14 actual delta is ${JSON.stringify(completedM1A14.actualAfter)}`);
    }
  }
  const completedM1A15 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A15.id,
  );
  if (!completedM1A15) {
    errors.push("completed M1A15 packet is missing");
  } else {
    if (completedM1A15.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A15 selectors remain in legacy CSS: ${completedM1A15.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A15.selectorRowsRemoved !== 4
        || completedM1A15.touchedRuleGroups !== 4
        || completedM1A15.fullyRemovedRuleGroups !== 3
        || completedM1A15.partiallyShrunkRuleGroups !== 1) {
      errors.push("completed M1A15 structural delta does not match the approved 4/4/3/1 packet");
    }
    if (completedM1A15.actualAfter.cssRuleGroups !== 2728
        || completedM1A15.actualAfter.selectorRows !== 3430
        || completedM1A15.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A15 actual delta is ${JSON.stringify(completedM1A15.actualAfter)}`);
    }
  }
  const completedM1A16 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A16.id,
  );
  if (!completedM1A16) {
    errors.push("completed M1A16 packet is missing");
  } else {
    if (completedM1A16.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A16 selectors remain in legacy CSS: ${completedM1A16.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A16.selectorRowsRemoved !== 16
        || completedM1A16.touchedRuleGroups !== 13
        || completedM1A16.fullyRemovedRuleGroups !== 8
        || completedM1A16.partiallyShrunkRuleGroups !== 5) {
      errors.push("completed M1A16 structural delta does not match the approved 16/13/8/5 packet");
    }
    if (completedM1A16.actualAfter.cssRuleGroups !== 2720
        || completedM1A16.actualAfter.selectorRows !== 3414
        || completedM1A16.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A16 actual delta is ${JSON.stringify(completedM1A16.actualAfter)}`);
    }
  }
  const completedM1A17 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A17.id,
  );
  if (!completedM1A17) {
    errors.push("completed M1A17 packet is missing");
  } else {
    if (completedM1A17.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A17 selectors remain in legacy CSS: ${completedM1A17.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A17.selectorRowsRemoved !== 17
        || completedM1A17.touchedRuleGroups !== 16
        || completedM1A17.fullyRemovedRuleGroups !== 7
        || completedM1A17.partiallyShrunkRuleGroups !== 9) {
      errors.push("completed M1A17 structural delta does not match the approved 17/16/7/9 packet");
    }
    if (completedM1A17.actualAfter.cssRuleGroups !== 2713
        || completedM1A17.actualAfter.selectorRows !== 3397
        || completedM1A17.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A17 actual delta is ${JSON.stringify(completedM1A17.actualAfter)}`);
    }
  }
  const completedM1A18 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A18.id,
  );
  if (!completedM1A18) {
    errors.push("completed M1A18 packet is missing");
  } else {
    if (completedM1A18.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A18 selectors remain in legacy CSS: ${completedM1A18.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A18.selectorRowsRemoved !== 10
        || completedM1A18.touchedRuleGroups !== 9
        || completedM1A18.fullyRemovedRuleGroups !== 4
        || completedM1A18.partiallyShrunkRuleGroups !== 5) {
      errors.push("completed M1A18 structural delta does not match the approved 10/9/4/5 packet");
    }
    if (completedM1A18.actualAfter.cssRuleGroups !== 2709
        || completedM1A18.actualAfter.selectorRows !== 3387
        || completedM1A18.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A18 actual delta is ${JSON.stringify(completedM1A18.actualAfter)}`);
    }
  }
  const completedM1A19 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A19.id,
  );
  if (!completedM1A19) {
    errors.push("completed M1A19 packet is missing");
  } else {
    if (completedM1A19.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A19 selectors remain in legacy CSS: ${completedM1A19.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A19.selectorRowsRemoved !== 9
        || completedM1A19.touchedRuleGroups !== 8
        || completedM1A19.fullyRemovedRuleGroups !== 6
        || completedM1A19.partiallyShrunkRuleGroups !== 2) {
      errors.push("completed M1A19 structural delta does not match the approved 9/8/6/2 packet");
    }
    if (completedM1A19.actualAfter.cssRuleGroups !== 2703
        || completedM1A19.actualAfter.selectorRows !== 3378
        || completedM1A19.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A19 actual delta is ${JSON.stringify(completedM1A19.actualAfter)}`);
    }
  }
  const completedM1A20 = inventory.migrationPlan.completedBoundedUnits.find(
    (unit) => unit.id === COMPLETED_M1A20.id,
  );
  if (!completedM1A20) {
    errors.push("completed M1A20 packet is missing");
  } else {
    if (completedM1A20.residualExactSelectorRows.length !== 0) {
      errors.push(`completed M1A20 selectors remain in legacy CSS: ${completedM1A20.residualExactSelectorRows.join(", ")}`);
    }
    if (completedM1A20.selectorRowsRemoved !== 4
        || completedM1A20.touchedRuleGroups !== 4
        || completedM1A20.fullyRemovedRuleGroups !== 4
        || completedM1A20.partiallyShrunkRuleGroups !== 0) {
      errors.push("completed M1A20 structural delta does not match the approved 4/4/4/0 packet");
    }
    if (completedM1A20.actualAfter.cssRuleGroups !== 2699
        || completedM1A20.actualAfter.selectorRows !== 3374
        || completedM1A20.actualAfter.crossCssDuplicateRows !== 14) {
      errors.push(`completed M1A20 actual delta is ${JSON.stringify(completedM1A20.actualAfter)}`);
    }
  }
  const checkpointByUnit = new Map((inventory.migrationPlan.checkpoints ?? []).map((checkpoint) => [checkpoint.unit, checkpoint]));
  for (const checkpoint of OWNERSHIP_CHECKPOINTS) {
    const actual = checkpointByUnit.get(checkpoint.unit);
    if (!actual) errors.push(`ownership checkpoint ${checkpoint.unit} is missing`);
    else if (actual.sourceCommit !== checkpoint.sourceCommit || actual.frozenBase !== FROZEN_BASE || actual.disposition !== "APPROVE") {
      errors.push(`ownership checkpoint ${checkpoint.unit} provenance/disposition changed`);
    }
  }
  const combined = inventory.migrationPlan.combinedB4;
  if (!combined || combined.frozenBase !== FROZEN_BASE || combined.status !== "MAIN-REQUIRED") {
    errors.push("combined B4 checkpoint is missing or claims live acceptance");
  } else {
    const expectedResiduals = {
      "M1A-modeling-data": 9,
      "M1B-modeling-process": 29,
      "M1E-modeling-shell-and-family": 383,
      "HOLD-owner-or-cross-feature-split": 504,
      "M4-shared-cleanup": 314,
      "M6-zero-consumer-removal-candidate": 533,
    };
    for (const [batch, count] of Object.entries(expectedResiduals)) {
      if (combined.current.byMigrationBatch[batch] !== count || combined.residualRouting[batch] !== count) {
        errors.push(`combined B4 residual ${batch} is ${combined.current.byMigrationBatch[batch] ?? "missing"}/${combined.residualRouting[batch] ?? "missing"}, expected ${count}`);
      }
    }
    if (combined.current.selectorRows !== 1772 || combined.current.cssRuleGroups !== 1473 || combined.current.crossCssDuplicateRows !== 7) {
      errors.push(`combined B4 current totals are ${JSON.stringify(combined.current)}`);
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

function isAncestorCommit(sourceSha, currentHead) {
  if (!/^[0-9a-f]{40}$/.test(sourceSha) || !/^[0-9a-f]{40}$/.test(currentHead)) {
    return false;
  }
  try {
    execFileSync(
      "git",
      ["merge-base", "--is-ancestor", sourceSha, currentHead],
      { cwd: ROOT, stdio: "ignore" },
    );
    return true;
  } catch {
    return false;
  }
}

export function reconcileInventorySourceSha(currentText, renderedText) {
  let current;
  let rendered;
  try {
    current = JSON.parse(currentText);
    rendered = JSON.parse(renderedText);
  } catch {
    return null;
  }
  if (!isAncestorCommit(current.sourceSha, rendered.sourceSha)) return null;
  if (current.migrationPlan?.combinedB4?.sourceCommit !== current.sourceSha
      || rendered.migrationPlan?.combinedB4?.sourceCommit !== rendered.sourceSha) {
    return null;
  }

  const sourceShaFields = [...currentText.matchAll(
    /("sourceSha"\s*:\s*")([0-9a-f]{40})(")/g,
  )];
  if (sourceShaFields.length !== 1 || sourceShaFields[0][2] !== current.sourceSha) {
    return null;
  }
  const combinedOffset = currentText.indexOf('"combinedB4"');
  if (combinedOffset < 0) return null;
  const combinedFields = [...currentText.slice(combinedOffset).matchAll(
    /("sourceCommit"\s*:\s*")([0-9a-f]{40})(")/g,
  )];
  if (combinedFields.length !== 1 || combinedFields[0][2] !== current.sourceSha) {
    return null;
  }

  const replacements = [
    sourceShaFields[0],
    { ...combinedFields[0], index: combinedOffset + combinedFields[0].index },
  ].sort((left, right) => right.index - left.index);
  let reconciled = currentText;
  for (const field of replacements) {
    const replacement = `${field[1]}${rendered.sourceSha}${field[3]}`;
    reconciled = `${reconciled.slice(0, field.index)}${replacement}${reconciled.slice(
      field.index + field[0].length,
    )}`;
  }
  return reconciled;
}

export function inventoryMatchesRendered(currentText, renderedText) {
  return reconcileInventorySourceSha(currentText, renderedText) === renderedText;
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
  if (!inventoryMatchesRendered(current, rendered)) {
    throw new Error(`STALE ${posix(relative(ROOT, OUTPUT))}; rerun with --write and inspect the source/candidate delta`);
  }
  console.log(`PASS ${posix(relative(ROOT, OUTPUT))}`);
  console.log(JSON.stringify(inventory.summary, null, 2));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  runCli();
}

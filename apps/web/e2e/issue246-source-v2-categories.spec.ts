import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page, type Route } from "@playwright/test";

const evidenceDirectory = process.env.CMP_ISSUE246_EVIDENCE_DIR;
const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const sourceRoot = join(repositoryRoot, "fixtures/schema-definition-bundle/source-v2");
const canonicalTestData = JSON.parse(
  readFileSync(
    join(repositoryRoot, "contracts/examples/positive/canonical-test-data.json"),
    "utf8",
  ),
);
const sourceFiles = [
  join(sourceRoot, "catalog-schema-bundle.manifest.json"),
  ...readdirSync(join(sourceRoot, "record-schemas"))
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => join(sourceRoot, "record-schemas", name)),
];

const organizationId = "24600000-0000-4000-8000-000000000001";
const projectId = "24600000-0000-4000-8000-000000000002";
const actorId = "24600000-0000-4000-8000-000000000003";

function id(value: number): string {
  return `24600000-0000-4000-8000-${String(value).padStart(12, "0")}`;
}

function revision<T>(revisionId: string, aggregateId: string, content: T) {
  return {
    id: revisionId,
    aggregate_id: aggregateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:issue-246-browser:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-08-14T00:00:00Z",
    created_by: actorId,
    change_reason: "Issue #246 deterministic browser evidence",
    organization_id: organizationId,
    project_id: projectId,
    classification: "internal",
    lifecycle_state: "published",
    content,
  };
}

const technicalTable = {
  table_id: id(10),
  current_revision: revision(id(11), id(10), {
    key: "demo_material_records",
    name: "Technical Data",
    description: "Reviewed material facts",
    data_category: "technical_data",
  }),
};
const testTable = {
  table_id: id(20),
  current_revision: revision(id(21), id(20), {
    key: "test_data",
    name: "Test Data",
    description: "Measured experiments",
    data_category: "test_data",
  }),
};
const simulationTable = {
  table_id: id(30),
  current_revision: revision(id(31), id(30), {
    key: "simulation_data",
    name: "Simulation Data",
    description: "Selected models and derived results",
    data_category: "simulation_data",
  }),
};
const solverCardTable = {
  table_id: id(40),
  current_revision: revision(id(41), id(40), {
    key: "solver_cards",
    name: "Solver Cards",
    description: "Released solver-ready cards",
    data_category: "solver_cards",
  }),
};
const tables = [technicalTable, testTable, simulationTable, solverCardTable];

function record(
  sequence: number,
  table: typeof technicalTable,
  name: string,
  externalKey: string,
  kind:
    | "material"
    | "test_data"
    | "material_model"
    | "solver_card",
  workbenchPath: string,
) {
  const recordId = id(sequence);
  const recordRevisionId = id(sequence + 1);
  const domainBinding = {
    binding_id: id(sequence + 2),
    record_id: recordId,
    record_revision_id: recordRevisionId,
    kind,
    object_id: id(sequence + 3),
    revision_id: id(sequence + 4),
    workbench_path: workbenchPath,
  };
  return {
    record_id: recordId,
    table_id: table.table_id,
    current_revision: revision(recordRevisionId, recordId, {
      table_revision_id: table.current_revision.id,
      name,
      external_key: externalKey,
      description: "Bounded synthetic non-production evidence",
      folder_id: null,
      folder_revision_id: null,
      values: [],
    }),
    domain_binding: domainBinding,
    domain_bindings: [domainBinding],
  };
}

const technicalBase = record(
  100,
  technicalTable,
  "PA66-GF30 Technical Data",
  "TECH-PA66-GF30",
  "material",
  "/materials/synthetic-pa66",
);
const technicalGradeAttributeId = id(290);
const technicalGradeAttributeRevisionId = id(291);
const technicalDensityAttributeId = id(292);
const technicalDensityAttributeRevisionId = id(293);
const tensileTemperatureAttributeId = id(294);
const tensileTemperatureAttributeRevisionId = id(295);
const tensileForceAttributeId = id(296);
const tensileForceAttributeRevisionId = id(297);
const technical = {
  ...technicalBase,
  current_revision: {
    ...technicalBase.current_revision,
    content: {
      ...technicalBase.current_revision.content,
      values: [{
        attribute_definition_id: technicalGradeAttributeId,
        attribute_definition_revision_id: technicalGradeAttributeRevisionId,
        data_type: "text" as const,
        value: "PA66-GF30",
      }, {
        attribute_definition_id: technicalDensityAttributeId,
        attribute_definition_revision_id: technicalDensityAttributeRevisionId,
        data_type: "number" as const,
        original_value: "1.36e-9",
        original_unit_string: "tonne/mm3",
        normalized_value: "1360",
        normalized_unit: "kg/m3",
        quantity_semantics: "physics.density",
      }],
    },
  },
};
const technical2 = record(400, technicalTable, "DP780 Technical Data", "TECH-DP780", "material", "/materials/synthetic-dp780");
const technical3 = record(410, technicalTable, "EPDM Technical Data", "TECH-EPDM", "material", "/materials/synthetic-epdm");
const tensileBase = record(
  110,
  testTable,
  "Room-temperature tensile test",
  "TEST-TENSILE-001",
  "test_data",
  "/datasets/test-json?document_id=tensile",
);
const tensileTechnicalReferenceAttributeId = id(300);
const tensileTechnicalReferenceAttributeRevisionId = id(301);
const tensile = {
  ...tensileBase,
  current_revision: {
    ...tensileBase.current_revision,
    content: {
      ...tensileBase.current_revision.content,
      values: [{
        attribute_definition_id: tensileTechnicalReferenceAttributeId,
        attribute_definition_revision_id: tensileTechnicalReferenceAttributeRevisionId,
        data_type: "record_reference" as const,
        target_record_id: technical.record_id,
        target_record_revision_id: technical.current_revision.id,
      }, {
        attribute_definition_id: tensileTemperatureAttributeId,
        attribute_definition_revision_id: tensileTemperatureAttributeRevisionId,
        data_type: "number" as const,
        original_value: "23",
        original_unit_string: "degC",
        normalized_value: "296.15",
        normalized_unit: "K",
        quantity_semantics: "temperature",
      }, {
        attribute_definition_id: tensileForceAttributeId,
        attribute_definition_revision_id: tensileForceAttributeRevisionId,
        data_type: "number" as const,
        original_value: "182.4",
        original_unit_string: "MPa",
        normalized_value: "182400000",
        normalized_unit: "Pa",
        quantity_semantics: "mechanics.stress",
      }],
    },
  },
};
const dma = record(
  120,
  testTable,
  "DMA frequency-temperature sweep",
  "TEST-DMA-001",
  "test_data",
  "/datasets/test-json?document_id=dma",
);
const tensile2 = record(420, testTable, "High-temperature tensile test", "TEST-TENSILE-002", "test_data", "/datasets/test-json?document_id=tensile-2");
const tensile3 = record(430, testTable, "Low-rate tensile test", "TEST-TENSILE-003", "test_data", "/datasets/test-json?document_id=tensile-3");
const tensile4 = record(440, testTable, "High-rate tensile test", "TEST-TENSILE-004", "test_data", "/datasets/test-json?document_id=tensile-4");
const dma2 = record(450, testTable, "DMA temperature sweep", "TEST-DMA-002", "test_data", "/datasets/test-json?document_id=dma-2");
const dma3 = record(460, testTable, "DMA frequency sweep", "TEST-DMA-003", "test_data", "/datasets/test-json?document_id=dma-3");
const fld1 = record(470, testTable, "Forming limit test A", "TEST-FLD-001", "test_data", "/datasets/test-json?document_id=fld-1");
const fld2 = record(480, testTable, "Forming limit test B", "TEST-FLD-002", "test_data", "/datasets/test-json?document_id=fld-2");
const elastoplasticityBase = record(
  130,
  simulationTable,
  "Selected elastoplastic model",
  "MODEL-EP-001",
  "material_model",
  "/modeling?stage=fit&model=ep",
);
const elastoplasticity = {
  ...elastoplasticityBase,
  domain_binding: null,
  domain_bindings: [],
};
const elastoplasticity2 = record(490, simulationTable, "Selected elastoplastic model B", "MODEL-EP-002", "material_model", "/modeling?stage=fit&model=ep-2");
const statistics = record(500, simulationTable, "Tensile statistics", "STAT-TENSILE-001", "material_model", "/modeling?stage=statistics");
const viscoelasticity = record(
  140,
  simulationTable,
  "Selected linear viscoelastic model",
  "MODEL-VE-001",
  "material_model",
  "/modeling?stage=fit&model=ve",
);
const mat024 = record(
  150,
  solverCardTable,
  "LS-DYNA MAT_024 card",
  "CARD-MAT024-001",
  "solver_card",
  "/modeling?stage=export&card=mat024",
);
const pronyCard = record(
  160,
  simulationTable,
  "Abaqus Prony card",
  "CARD-PRONY-001",
  "solver_card",
  "/modeling?stage=export&card=prony",
);
const records = [
  technical, technical2, technical3,
  tensile, tensile2, tensile3, tensile4,
  dma, dma2, dma3,
  fld1, fld2,
  elastoplasticity, elastoplasticity2, statistics,
  mat024,
];
const tensileTechnicalReferenceAttribute = {
  attribute_definition_id: tensileTechnicalReferenceAttributeId,
  table_id: testTable.table_id,
  current_revision: revision(
    tensileTechnicalReferenceAttributeRevisionId,
    tensileTechnicalReferenceAttributeId,
    {
      table_revision_id: testTable.current_revision.id,
      key: "technical_data_ref",
      name: "Technical Data",
      data_type: "record_reference",
      required: true,
      quantity_semantics: null,
      normalized_unit: null,
      minimum_number: null,
      maximum_number: null,
      minimum_length: null,
      maximum_length: null,
      pattern: null,
      allowed_values: [],
      reference_table_id: technicalTable.table_id,
      help_text: "Exact Technical Data item",
      business_key: false,
    },
  ),
};
function scalarAttribute(
  attributeId: string,
  attributeRevisionId: string,
  table: typeof technicalTable,
  key: string,
  name: string,
  dataType: "text" | "number",
  quantitySemantics: string | null = null,
  normalizedUnit: string | null = null,
) {
  return {
    attribute_definition_id: attributeId,
    table_id: table.table_id,
    current_revision: revision(attributeRevisionId, attributeId, {
      table_revision_id: table.current_revision.id,
      key,
      name,
      data_type: dataType,
      required: true,
      quantity_semantics: quantitySemantics,
      normalized_unit: normalizedUnit,
      minimum_number: null,
      maximum_number: null,
      minimum_length: null,
      maximum_length: null,
      pattern: null,
      allowed_values: [],
      reference_table_id: null,
      help_text: null,
      business_key: false,
    }),
  };
}
const technicalAttributes = [
  scalarAttribute(technicalGradeAttributeId, technicalGradeAttributeRevisionId, technicalTable, "grade", "Grade", "text"),
  scalarAttribute(technicalDensityAttributeId, technicalDensityAttributeRevisionId, technicalTable, "density", "Density", "number", "physics.density", "kg/m3"),
];
const tensileAttributes = [
  tensileTechnicalReferenceAttribute,
  scalarAttribute(tensileTemperatureAttributeId, tensileTemperatureAttributeRevisionId, testTable, "temperature", "Temperature", "number", "temperature", "K"),
  scalarAttribute(tensileForceAttributeId, tensileForceAttributeRevisionId, testTable, "force_maximum", "Force maximum", "number", "mechanics.stress", "Pa"),
];
const tensileLayout = {
  layout_id: id(302),
  table_id: testTable.table_id,
  revision: revision(id(303), id(302), {}),
  name: "Test Data overview",
  description: null,
  items: [{
    attribute_definition_id: tensileTechnicalReferenceAttributeId,
    attribute_definition_revision_id: tensileTechnicalReferenceAttributeRevisionId,
    section: "Relationships",
    ordinal: 0,
  }, {
    attribute_definition_id: tensileTemperatureAttributeId,
    attribute_definition_revision_id: tensileTemperatureAttributeRevisionId,
    section: "Test condition",
    ordinal: 1,
  }, {
    attribute_definition_id: tensileForceAttributeId,
    attribute_definition_revision_id: tensileForceAttributeRevisionId,
    section: "Test result",
    ordinal: 2,
  }],
};
const technicalLayout = {
  layout_id: id(304),
  table_id: technicalTable.table_id,
  revision: revision(id(305), id(304), {}),
  name: "Technical Data overview",
  description: null,
  items: technicalAttributes.map((attribute, ordinal) => ({
    attribute_definition_id: attribute.attribute_definition_id,
    attribute_definition_revision_id: attribute.current_revision.id,
    section: ordinal === 0 ? "Material information" : "Sample information",
    ordinal,
  })),
};

function endpoint(value: (typeof records)[number]) {
  const table = tables.find((item) => item.table_id === value.table_id);
  return {
    record_id: value.record_id,
    record_revision_id: value.current_revision.id,
    revision_no: value.current_revision.revision_no,
    table_id: value.table_id,
    name: value.current_revision.content.name,
    external_key: value.current_revision.content.external_key,
    data_category: table?.current_revision.content.data_category ?? null,
    domain_binding: value.domain_binding,
    domain_bindings: value.domain_bindings,
  };
}

function link(
  sequence: number,
  source: (typeof records)[number],
  target: (typeof records)[number],
  key: string,
  forwardLabel: string,
  reverseLabel: string,
) {
  const linkId = id(sequence);
  const linkRevisionId = id(sequence + 1);
  const typeId = id(sequence + 2);
  const typeRevisionId = id(sequence + 3);
  return {
    record_link_id: linkId,
    current_revision: revision(linkRevisionId, linkId, {
      link_type_id: typeId,
      link_type_revision_id: typeRevisionId,
      source_record_id: source.record_id,
      source_record_revision_id: source.current_revision.id,
      target_record_id: target.record_id,
      target_record_revision_id: target.current_revision.id,
      active: true,
      note: null,
    }),
    link_type_revision: revision(typeRevisionId, typeId, {
      key,
      name: key.replaceAll("_", " "),
      source_table_id: source.table_id,
      source_table_revision_id: source.current_revision.content.table_revision_id,
      target_table_id: target.table_id,
      target_table_revision_id: target.current_revision.content.table_revision_id,
      forward_label: forwardLabel,
      reverse_label: reverseLabel,
      source_cardinality: "many",
      target_cardinality: "one",
      description: null,
    }),
    source: endpoint(source),
    target: endpoint(target),
  };
}

const links = [
  link(200, technical, tensile, "technical_to_tensile", "has tensile test", "uses Technical Data"),
  link(210, technical, dma, "technical_to_dma", "has DMA test", "uses Technical Data"),
  link(220, tensile, elastoplasticity, "tensile_to_ep", "produces selected model", "uses tensile test"),
  link(230, elastoplasticity, mat024, "ep_to_card", "generates solver card", "uses selected model"),
  link(520, technical, tensile2, "technical_to_tensile", "has tensile test", "uses Technical Data"),
  link(530, technical, tensile3, "technical_to_tensile", "has tensile test", "uses Technical Data"),
  link(540, technical, tensile4, "technical_to_tensile", "has tensile test", "uses Technical Data"),
  link(550, technical, dma2, "technical_to_dma", "has DMA test", "uses Technical Data"),
  link(560, technical, dma3, "technical_to_dma", "has DMA test", "uses Technical Data"),
  link(570, technical, fld1, "technical_to_fld", "has FLD test", "uses Technical Data"),
  link(580, technical, fld2, "technical_to_fld", "has FLD test", "uses Technical Data"),
  link(590, tensile2, elastoplasticity2, "tensile_to_ep", "produces selected model", "uses tensile test"),
  link(600, tensile3, statistics, "tensile_to_statistics", "produces statistics", "uses tensile test"),
];

function fulfillJson(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    headers: { "x-request-id": "issue-246-browser" },
    body: JSON.stringify(body),
  });
}

async function installAccess(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: "issue-246-browser-token" }),
    );
    window.sessionStorage.clear();
  });
}

async function captureState(
  page: Page,
  state: "categories" | "detail" | "source-plan",
  ready: () => Promise<void>,
): Promise<void> {
  if (!evidenceDirectory) return;
  const originalDirectory = join(evidenceDirectory, "after", "originals");
  const cropDirectory = join(evidenceDirectory, "after", "crops");
  const measurementDirectory = join(evidenceDirectory, "after", "measurements");
  await Promise.all([
    mkdir(originalDirectory, { recursive: true }),
    mkdir(cropDirectory, { recursive: true }),
    mkdir(measurementDirectory, { recursive: true }),
  ]);
  for (const [width, height] of [
    [1366, 768],
    [1440, 900],
    [1920, 1080],
    [2560, 1440],
    [3840, 2160],
  ] as const) {
    if (state !== "source-plan") {
      const captureUrl = page.url();
      await page.goto("about:blank");
      await page.setViewportSize({ width, height });
      await page.goto(captureUrl);
    } else {
      await page.setViewportSize({ width, height });
    }
    await ready();
    if (state !== "source-plan") {
      await page.waitForFunction(() => {
        const workspace = document.querySelector(".materials-page");
        const text = workspace?.textContent ?? "";
        return !workspace?.querySelector('[aria-busy="true"]')
          && !text.includes("Loading configured datasheet")
          && !text.includes("Loading Technical Data")
          && !text.includes("Finding Materials");
      });
      await page.waitForTimeout(150);
      await ready();
      const expandNavigator = page.getByRole("button", { name: "Expand navigator pane" });
      if (await expandNavigator.isVisible().catch(() => false)) {
        await expandNavigator.click();
        await expect(page.locator(".materials-left-pane")).toBeVisible();
      }
      await page.getByRole("separator", { name: "Resize navigator" }).dblclick();
      await page.waitForTimeout(50);
    }
    const stem = `issue246-${state}-${width}x${height}`;
    await page.screenshot({ path: join(originalDirectory, `${stem}.png`) });
    await page.locator(".application-menu-bar").screenshot({
      path: join(cropDirectory, `${stem}-header-crop.png`),
    });
    if (state === "source-plan") {
      await page.locator(".administration-taskbar").screenshot({
        path: join(cropDirectory, `${stem}-navigator-crop.png`),
      });
      await page.locator(".schema-bundle-source").screenshot({
        path: join(cropDirectory, `${stem}-source-crop.png`),
      });
      await page.locator(".schema-bundle-plan").screenshot({
        path: join(cropDirectory, `${stem}-plan-crop.png`),
      });
    } else {
      await page.locator(".materials-left-pane").screenshot({
        path: join(cropDirectory, `${stem}-navigator-crop.png`),
      });
      await page.locator(state === "categories" ? ".materials-results" : ".exact-record-datasheet").screenshot({
        path: join(cropDirectory, `${stem}-record-crop.png`),
      });
      const detailSurface = state === "categories"
        ? page.locator(".materials-results-header")
        : page.locator(".exact-record-related");
      await expect(detailSurface).toBeVisible();
      await detailSurface.screenshot({
        path: join(cropDirectory, `${stem}-detail-crop.png`),
      });
    }
    const measurements = await page.evaluate((captureStateName) => {
      const rect = (selector: string) => {
        const value = document.querySelector(selector)?.getBoundingClientRect();
        return value
          ? { x: value.x, y: value.y, width: value.width, height: value.height }
          : null;
      };
      return {
        state: captureStateName,
        viewport: { width: innerWidth, height: innerHeight },
        devicePixelRatio,
        visualViewportScale: visualViewport?.scale ?? null,
        document: {
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          clientHeight: document.documentElement.clientHeight,
          scrollHeight: document.documentElement.scrollHeight,
        },
        shell: rect(".application-shell"),
        workspace: rect(
          captureStateName === "source-plan"
            ? ".administration-workspace"
            : ".resizable-workspace",
        ),
        navigator: rect(
          captureStateName === "source-plan"
            ? ".administration-taskbar"
            : ".materials-left-pane",
        ),
        central: rect(
          captureStateName === "source-plan"
            ? ".schema-bundle-plan"
            : captureStateName === "categories"
              ? ".materials-results"
              : ".exact-record-datasheet",
        ),
        detail: rect(
          captureStateName === "source-plan"
            ? ".schema-bundle-source"
            : captureStateName === "categories"
              ? ".materials-results-header"
              : ".exact-record-related",
        ),
      };
    }, state);
    expect(measurements.visualViewportScale).toBe(1);
    expect(measurements.devicePixelRatio).toBe(1);
    expect(measurements.document.scrollWidth).toBe(measurements.document.clientWidth);
    expect(measurements.workspace).not.toBeNull();
    expect(measurements.central?.width ?? 0).toBeGreaterThan(320);
    if (state !== "source-plan") {
      expect(measurements.navigator?.width ?? 0).toBeGreaterThanOrEqual(280);
    }
    await writeFile(
      join(measurementDirectory, `${stem}.json`),
      `${JSON.stringify(measurements, null, 2)}\n`,
      "utf8",
    );
  }
}

test("Materials keeps four peer categories in its established tree and exact direct links", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await installAccess(page);
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/v1/product-access/me") {
      return fulfillJson(route, {
        product_role: "administrator",
        feature_grants: ["catalog_edit", "schema_configuration"],
        legacy_compatible: false,
      });
    }
    if (path === "/api/v1/catalog/explorer/tables") {
      return fulfillJson(route, { items: tables });
    }
    const tableResource = path.match(
      /\/api\/v1\/catalog\/tables\/([^/]+)\/(subsets|attributes|layouts|folders)$/,
    );
    if (tableResource) {
      const [, requestedTableId, resource] = tableResource;
      const items = requestedTableId === technicalTable.table_id && resource === "attributes"
        ? technicalAttributes
        : requestedTableId === technicalTable.table_id && resource === "layouts"
          ? [technicalLayout]
        : requestedTableId === testTable.table_id && resource === "attributes"
        ? tensileAttributes
        : requestedTableId === testTable.table_id && resource === "layouts"
          ? [tensileLayout]
          : [];
      return fulfillJson(route, { items });
    }
    if (/\/api\/v1\/catalog\/explorer\/tables\/[^/]+\/children$/.test(path)) {
      const tableId = path.split("/").at(-2);
      const table = tables.find((item) => item.table_id === tableId) ?? technicalTable;
      return fulfillJson(route, {
        table,
        folders: [],
        records: table.table_id === technicalTable.table_id ? [technical] : [],
      });
    }
    if (path === "/api/v1/catalog/records:search") {
      const body = request.postDataJSON() as {
        data_category?: string | null;
        table_id?: string | null;
      };
      const byCategory = {
        technical_data: [technical],
        test_data: [tensile, dma],
        simulation_data: [elastoplasticity, viscoelasticity],
        solver_cards: [mat024, pronyCard],
      }[body.data_category ?? ""] ?? [];
      const items = body.data_category
        ? byCategory
        : body.table_id === technicalTable.table_id
          ? [technical]
          : [];
      return fulfillJson(route, {
        items,
        total_count: items.length,
        offset: 0,
        limit: 100,
        facets: [],
      });
    }
    if (
      path ===
      `/api/v1/test-data-documents/${tensile.domain_binding.object_id}/revisions/${tensile.domain_binding.revision_id}/content`
    ) {
      return fulfillJson(route, canonicalTestData);
    }
    const selectedRecord = path.match(/\/api\/v1\/catalog\/records\/([^/]+)$/);
    if (selectedRecord) {
      const selected = records.find((item) => item.record_id === selectedRecord[1]) ?? technical;
      return fulfillJson(route, selected);
    }
    const workflow = path.match(
      /\/api\/v1\/catalog\/workflow-explorer\/([^/]+)\/revisions\/([^/]+)/,
    );
    if (workflow) {
      const root = records.find((item) => item.record_id === workflow[1]) ?? technical;
      return fulfillJson(route, {
        root: endpoint(root),
        nodes: records.map(endpoint),
        links,
      });
    }
    const revisions = path.match(/\/api\/v1\/catalog\/records\/([^/]+)\/revisions$/);
    if (revisions) {
      const selected = records.find((item) => item.record_id === revisions[1]) ?? technical;
      return fulfillJson(route, { items: [selected.current_revision] });
    }
    return fulfillJson(route, { detail: `Unhandled issue #246 route ${path}` }, 501);
  });

  await page.goto("/materials");
  await expect(page.getByRole("heading", { name: "Materials", level: 1 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Materials navigator modes" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Browse" })).toHaveAttribute("aria-current", "page");
  await expect(page.locator(".material-database-workspace")).toHaveCount(0);

  const categories = page.getByRole("tree", { name: "Database contents" });
  for (const label of ["Technical Data", "Test Data", "Simulation Data", "Solver Cards"]) {
    await expect(categories.getByRole("treeitem", { name: label, exact: true })).toBeVisible();
  }
  await expect(categories.getByRole("treeitem", { name: "Technical Data", exact: true })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await expect(categories.getByRole("treeitem", { name: /PA66-GF30 Technical Data/ })).toBeVisible();
  await expect(categories.getByRole("treeitem", { name: "Catalog placement", exact: true })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Database" })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Profile" })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Browse table" })).toHaveCount(0);
  await expect(page.locator(".materials-results")).toBeVisible();
  await expect(page.getByRole("row", { name: /PA66-GF30 Technical Data/ })).toBeVisible();
  await captureState(page, "categories", async () => {
    await expect(categories.getByRole("treeitem", { name: /PA66-GF30 Technical Data/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Materials", level: 1 })).toBeVisible();
    await expect(page.getByRole("row", { name: /PA66-GF30 Technical Data/ })).toBeVisible();
  });

  await categories.getByRole("treeitem", { name: "Test Data", exact: true }).click();
  await expect(categories.getByRole("treeitem", { name: "Test Data", exact: true })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await expect(categories.getByRole("treeitem", { name: "Technical Data", exact: true })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await expect(categories.getByRole("treeitem", { name: /Room-temperature tensile test/ })).toBeVisible();
  await expect(categories.getByRole("treeitem", { name: /DMA frequency-temperature sweep/ })).toBeVisible();
  await page.getByRole("row", { name: /Room-temperature tensile test/ }).click();

  await expect(page).toHaveURL(new RegExp(`/materials/records/${tensile.record_id}/revisions/${tensile.current_revision.id}$`));
  await expect(page.getByRole("heading", { name: "Test Data", level: 1 })).toBeVisible();
  await expect(
    categories.getByRole("treeitem", { name: /Room-temperature tensile test/ }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("23", { exact: true })).toBeVisible();
  await expect(page.getByText("degC", { exact: true })).toBeVisible();
  await expect(page.getByText("182.4", { exact: true })).toBeVisible();
  await expect(page.getByText("MPa", { exact: true })).toBeVisible();
  const related = page.locator(".exact-record-related");
  await expect(related).toBeVisible();
  await expect(related.getByText("Technical Data 1", { exact: true })).toBeVisible();
  await expect(related.getByText("PA66-GF30 Technical Data", { exact: true })).toBeVisible();
  await expect(related.getByText("Simulation Data 1", { exact: true })).toBeVisible();
  await expect(related.getByText("Selected elastoplastic model", { exact: true })).toBeVisible();
  await expect(related.getByText("Selected linear viscoelastic model", { exact: true })).toHaveCount(0);
  await expect(related.getByText("LS-DYNA MAT_024 card", { exact: true })).toHaveCount(0);
  await expect(related.getByRole("button", { name: /PA66-GF30 Technical Data.*r1/ })).toBeVisible();
  await captureState(page, "detail", async () => {
    await expect(page.getByRole("heading", { name: "Test Data", level: 1 })).toBeVisible();
  });
});

test("Administrator assembles source-v2 and sees the exact Task 2 unit boundary", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await installAccess(page);
  let uploadedSource: Buffer | null = null;
  let expectedSha256 = "";
  const artifactId = id(900);
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/product-access/me") {
      return fulfillJson(route, {
        product_role: "administrator",
        feature_grants: ["schema_configuration", "catalog_edit"],
        legacy_compatible: false,
      });
    }
    if (path === "/api/v1/uploads" && request.method() === "POST") {
      const body = request.postDataJSON() as {
        expected_sha256: string;
        expected_size_bytes: number;
        media_type: string;
      };
      expectedSha256 = body.expected_sha256;
      expect(body.media_type).toBe("application/vnd.cmp.catalog-schema-source-set+json");
      return fulfillJson(route, {
        upload: {
          upload_id: id(901),
          organization_id: organizationId,
          project_id: projectId,
          classification: "internal",
          state: "open",
          original_filename: "smx_material_db-source-set.json",
          media_type: body.media_type,
          expected_size_bytes: body.expected_size_bytes,
          expected_sha256: body.expected_sha256,
          part_size_bytes: body.expected_size_bytes,
          expected_part_count: 1,
          test_run_revision_id: null,
          raw_asset_id: null,
        },
        upload_capability: "x".repeat(32),
      }, 201);
    }
    if (/\/api\/v1\/uploads\/[^/]+\/parts\/1$/.test(path)) {
      uploadedSource = request.postDataBuffer();
      return fulfillJson(route, { state: "open" });
    }
    if (/\/api\/v1\/uploads\/[^/]+:complete$/.test(path)) {
      return fulfillJson(route, {
        upload: { state: "completed" },
        raw_asset: {
          raw_asset_id: id(902),
          organization_id: organizationId,
          project_id: projectId,
          classification: "internal",
          sha256: expectedSha256,
          size_bytes: uploadedSource?.length ?? 0,
          media_type: "application/vnd.cmp.catalog-schema-source-set+json",
          original_filename: "smx_material_db-source-set.json",
          storage_state: "staged_verified",
        },
        available_artifact_id: artifactId,
      });
    }
    if (path === "/api/v1/catalog/schema-definition-bundles:plan") {
      const unitLocations = [
        "/record_schemas/technical_data/schema/properties/material_properties/properties/density/x-unit",
        "/record_schemas/tensile_test/schema/properties/test_condition/properties/speed_elastic/x-unit",
        "/record_schemas/tensile_test/schema/properties/test_condition/properties/speed_plastic/x-unit",
        "/record_schemas/dma_test/schema/properties/test_condition/properties/oscillation_frequency/x-unit",
        "/record_schemas/dma_test/schema/properties/test_result/properties/storage_modulus_curve/x-curve/series_unit",
        "/record_schemas/dma_test/schema/properties/test_result/properties/loss_modulus_curve/x-curve/series_unit",
        "/record_schemas/dma_test/schema/properties/test_result/properties/master_curve/x-curve/x_unit",
        "/record_schemas/fld_test/schema/properties/test_condition/properties/punch_speed/x-unit",
        "/unit_profiles/0/units/mass",
        "/unit_profiles/0/units/density",
      ];
      return fulfillJson(route, {
        $schema: "https://cmp.example/contracts/catalog/schema-definition-plan.schema.json",
        contract_version: "1.0.0",
        source_artifact: {
          artifact_id: artifactId,
          organization_id: organizationId,
          project_id: projectId,
          classification: "internal",
          media_type: "application/vnd.cmp.catalog-schema-source-set+json",
          size_bytes: uploadedSource?.length ?? 0,
          sha256: expectedSha256,
        },
        bundle: {
          bundle_key: "smx_material_db",
          bundle_version: "2.0.0",
          scope: {
            organization_id: organizationId,
            project_id: projectId,
            classification: "internal",
          },
          database_key: "smx_material_db",
          profile_key: "smx_material_profile",
          record_schema_count: 6,
          unit_profile_count: 2,
          dependency_order: ["technical_data", "tensile_test", "dma_test", "fld_test", "elastoplasticity_data", "statistics_data"],
        },
        catalog_snapshot_fingerprint: "c".repeat(64),
        plan_fingerprint: "d".repeat(64),
        valid: false,
        action_counts: { create: 0, update: 0, "no-op": 0, conflict: 0, error: 10 },
        actions: [],
        diagnostics: unitLocations.map((location) => ({
          severity: "error",
          code: "CMP-SCHEMA-BUNDLE-0002",
          location,
          message: "The original unit is not in the current closed common-unit contract.",
          remediation: "Complete issue #246 Task 2 common-unit support, then request a fresh plan.",
        })),
        mutations_applied: false,
        delete_missing: false,
        write_set: [],
      });
    }
    return fulfillJson(route, { detail: `Unhandled issue #246 route ${path}` }, 501);
  });

  await page.goto("/administration/schema-bundles");
  await page.getByLabel("Definition bundle").setInputFiles(sourceFiles);
  await expect(page.getByText("source file set · 7 files", { exact: true })).toBeVisible();
  const sourceSummary = page.locator(".schema-bundle-summary");
  await expect(sourceSummary.getByText("6", { exact: true })).toBeVisible();
  await expect(sourceSummary.getByText("2", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Upload and plan" }).click();
  await expect(page.getByText("Plan diagnostics (10)", { exact: true })).toBeVisible();
  await expect(page.getByText("Apply is blocked until the server returns a valid plan with no conflicts or errors.", { exact: true })).toBeVisible();
  expect(uploadedSource).not.toBeNull();
  expect(createHash("sha256").update(uploadedSource!).digest("hex")).toBe(expectedSha256);
  const envelope = JSON.parse(uploadedSource!.toString("utf8")) as {
    $schema: string;
    files: Array<{ path: string; sha256: string; content: string }>;
  };
  expect(envelope.$schema).toBe(
    "https://cmp.example/contracts/catalog/schema-definition-source-set.schema.json",
  );
  expect(envelope.files).toHaveLength(7);
  expect(envelope.files.map((item) => item.path)).toEqual(
    [...envelope.files.map((item) => item.path)].sort(),
  );
  for (const item of envelope.files) {
    expect(createHash("sha256").update(item.content).digest("hex")).toBe(item.sha256);
  }
  await captureState(page, "source-plan", async () => {
    await expect(page.getByText("Plan diagnostics (10)", { exact: true })).toBeVisible();
  });
});

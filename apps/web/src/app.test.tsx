import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./app";
import { MaterialDetailPage } from "./material-library";

vi.mock("./materials-browse-tree", async () => {
  const React = await import("react");
  return {
    MaterialsBrowseTree: ({ subsetMode, onScopeChange }: { subsetMode: boolean; onScopeChange?: (scope: { tableId: string }) => void }) => {
      React.useEffect(() => {
        const timer = window.setTimeout(() => onScopeChange?.({ tableId: "demo-material-records" }), 0);
        return () => window.clearTimeout(timer);
      }, [onScopeChange]);
      return <div><form role="search"><input aria-label="Find in tree" /></form>{subsetMode ? "Saved subsets" : "Browse tree"}</div>;
    },
  };
});

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

function textResponse(body: string, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "text/plain" }),
    text: async () => body,
  } as Response;
}

const visibleMaterial = {
  material_id: "00000000-0000-0000-0000-000000000001",
  current_revision: {
    id: "00000000-0000-0000-0000-000000000002",
    aggregate_id: "00000000-0000-0000-0000-000000000001",
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:material:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-13T00:00:00Z",
    created_by: "00000000-0000-0000-0000-000000000003",
    change_reason: "demo",
    organization_id: "00000000-0000-0000-0000-000000000004",
    project_id: "00000000-0000-0000-0000-000000000005",
    classification: "internal",
    lifecycle_state: "draft",
    content: {
      name: "Demo DP780 Steel",
      material_code: "DP780",
      material_family: "steel",
      description: null,
      material_class: "metal",
    },
    provenance: {
      entity_type: "catalog.material.revision",
      reference_type: "catalog.material.revision",
      revision_id: "00000000-0000-0000-0000-000000000002",
      content_sha256: "a".repeat(64),
      based_on_revision_id: null,
      recorded_at: "2026-07-13T00:00:00Z",
      recorded_by: "00000000-0000-0000-0000-000000000003",
    },
  },
  links: { self: "/api/v1/materials/1", revisions: "/api/v1/materials/1/revisions", states: "/api/v1/materials/1/states" },
};

const materialCatalogTableId = "demo-material-records";
const materialCatalogAttributes = [
  { attribute_definition_id: "material-class", current_revision: { content: { key: "material_class" } } },
  { attribute_definition_id: "provider", current_revision: { content: { key: "provider" } } },
  { attribute_definition_id: "evidence-source", current_revision: { content: { key: "evidence_source" } } },
  { attribute_definition_id: "material-family", current_revision: { content: { key: "material_family" } } },
];

function materialCatalogRecord(material: typeof visibleMaterial) {
  const content = material.current_revision.content;
  return {
    record_id: `record-${material.material_id}`,
    table_id: materialCatalogTableId,
    domain_binding: { kind: "material", object_id: material.material_id, revision_id: material.current_revision.id },
    current_revision: {
      ...material.current_revision,
      content: {
        table_revision_id: "demo-material-records-r1",
        name: content.name,
        external_key: content.material_code,
        description: content.description,
        folder_id: null,
        folder_revision_id: null,
        values: [
          { data_type: "discrete", attribute_definition_id: "material-class", value: content.material_class },
          { data_type: "text", attribute_definition_id: "material-family", value: content.material_family ?? "" },
          { data_type: "text", attribute_definition_id: "provider", value: "Demo provider" },
          { data_type: "text", attribute_definition_id: "evidence-source", value: "Synthetic reference" },
        ],
      },
    },
  };
}

function materialCatalogResponse(materials: typeof visibleMaterial[], totalCount = materials.length, offset = 0) {
  return {
    items: materials.map(materialCatalogRecord),
    total_count: totalCount,
    offset,
    limit: 50,
    facets: [
      ...new Map(materials.map((material) => [material.current_revision.content.material_class, material])).values(),
    ].map((material) => ({ attribute_definition_id: "material-class", value: material.current_revision.content.material_class, count: totalCount })),
  };
}

function materialCatalogFetch(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  materials: typeof visibleMaterial[],
  totalCount = materials.length,
): Response | null {
  const url = String(input);
  if (url.endsWith("/catalog/tables")) return jsonResponse({ items: [{ table_id: materialCatalogTableId }] });
  if (url.endsWith(`/catalog/tables/${materialCatalogTableId}/attributes`)) return jsonResponse({ items: materialCatalogAttributes });
  if (url.endsWith("/catalog/records:search")) {
    const request = JSON.parse(String(init?.body ?? "{}")) as { offset?: number };
    return jsonResponse(materialCatalogResponse(materials, totalCount, request.offset ?? 0));
  }
  return null;
}

const demoSession = {
  access_token: "demo-token",
  token_type: "Bearer",
  expires_in_seconds: 900,
  organization_id: "d0000000-0000-4000-8000-000000000001",
  project_id: "d0000000-0000-4000-8000-000000000002",
  group: "cmp-demo-material-team",
};

const generatedCardCandidate = {
  source: {
    kind: "neutral_solver_card_native",
    neutral_solver_card_id: "00000000-0000-4000-8000-000000000010",
    neutral_solver_card_revision_id: "00000000-0000-4000-8000-000000000011",
  },
  classification: "internal",
  source_sha256: "b".repeat(64),
  source_size_bytes: 256,
  media_type: "text/plain",
  default_archive_path: "solver-cards/METAL_REFERENCE.rad",
  label: "Neutral openradioss native card · METAL_REFERENCE",
};

const neutralCardRevisionId = "00000000-0000-4000-8000-000000000023";

function exactNeutralCardPath(cardId: string, suffix = ""): string {
  return `/neutral-solver-cards/${cardId}${suffix}?revision_id=${neutralCardRevisionId}`;
}

function rejectUnpinnedNeutralCardRequest(url: string, cardId: string): void {
  if (url.includes(`/neutral-solver-cards/${cardId}`)) {
    throw new Error(`Neutral graph card request must pin ${neutralCardRevisionId}: ${url}`);
  }
}

function neutralSolverCard(cardId: string) {
  return {
    solver_card_id: cardId,
    neutral_material_id: "00000000-0000-4000-8000-000000000030",
    target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
    current_revision: {
      id: neutralCardRevisionId,
      revision_no: 1,
      lifecycle_state: "draft",
      content: {
        solver_material_id: 301,
        material_name: "DP780",
        card_sha256: "c".repeat(64),
        mapping_statuses: { density: "exact", elasticity: "transformed" },
      },
    },
  };
}

function neutralSolverMappingReport(review = false) {
  return {
    mapping_report_sha256: "d".repeat(64),
    exportable: true,
    report: {
      items: [
        ...(review ? [
          { name: "hardening", ir_path: "hardening", target_representation: "*PLASTIC", status: "approximated", detail: "The bounded extension needs a delivery review." },
        ] : [
          { name: "density", ir_path: "density", target_representation: "RHO_I", status: "exact", detail: "Mapped without approximation." },
          { name: "elasticity", ir_path: "elasticity", target_representation: "E, NU", status: "transformed", detail: "Converted to the target unit system." },
        ]),
      ],
    },
  };
}

function mockProductFetch(
  handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response> | Response,
) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    if (String(input).endsWith("/demo-identity/token")) return jsonResponse(demoSession);
    return handler(input, init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Material Catalog workbench", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows a product sign-in boundary when the workspace session cannot start", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({}, 404)));
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Sign in to continue" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/bearer|API base|tenant|RLS/i);
  });

  it("renders Material data returned by the real Catalog API contract", async () => {
    mockProductFetch((input, init) => {
      const url = String(input);
      const catalog = materialCatalogFetch(input, init, [visibleMaterial], 10_000);
      if (catalog) return catalog;
      if (url.endsWith(`/materials/${visibleMaterial.material_id}`)) {
        return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
      }
      if (url.includes("/catalog/domain-bindings:resolve")) return jsonResponse(null);
      if (url.includes("/bulk-export-candidates?")) return jsonResponse({ items: [generatedCardCandidate] });
      return jsonResponse({});
    });

    render(<App />);

    expect((await screen.findAllByText("Demo DP780 Steel")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("DP780").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/10,000 matches/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Materials", level: 1 })).toBeTruthy();
    expect(screen.getAllByRole("search")).toHaveLength(2);
    expect(screen.getByRole("complementary", { name: "Materials navigator" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Browse" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("textbox", { name: "Search materials" })).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "Find in tree" })).toBeTruthy();
    expect(screen.getByRole("table", { name: "Material results" })).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: "Material class" })).toBeNull();
    expect(screen.getByRole("columnheader", { name: /Family/ })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: /Status/ })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: /Form \/ condition|Release/ })).toBeNull();
    expect(screen.queryByText("Provider")).toBeNull();
    expect(screen.queryByText("Evidence source")).toBeNull();
    expect(screen.getByRole("navigation", { name: "Materials navigator modes" })).toBeTruthy();
    const materialHeader = screen.getAllByRole("columnheader").find((header) =>
      within(header).queryByRole("button", { name: "Material / grade" }),
    );
    expect(materialHeader).toBeTruthy();
    expect(materialHeader?.getAttribute("aria-sort")).toBe("ascending");
    expect(within(materialHeader!).getByRole("button", { name: "Material / grade" }).hasAttribute("aria-sort")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Family" }));
    await waitFor(() => expect(window.location.search).toContain("sort=material_class"));
    expect(screen.getByRole("columnheader", { name: /Family/ }).getAttribute("aria-sort")).toBe("ascending");
    fireEvent.click(screen.getByRole("button", { name: "Collapse navigator pane" }));
    expect(screen.queryByRole("complementary", { name: "Materials navigator" })).toBe(null);
    expect(screen.getByRole("button", { name: "Expand navigator pane" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Expand navigator pane" }));
    fireEvent.click(screen.getByRole("button", { name: "Expand details pane" }));
    expect(screen.getByRole("button", { name: "Open datasheet" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Materials" }).getAttribute("aria-busy")).toBe("false");
    fireEvent.change(screen.getByRole("textbox", { name: "Search materials" }), { target: { value: "DP780" } });
    fireEvent.submit(screen.getByRole("textbox", { name: "Search materials" }).closest("form")!);
    fireEvent.click(screen.getByRole("button", { name: "Filters" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Material class" }), { target: { value: "metal" } });
    await waitFor(() => expect(window.location.search).toContain("q=DP780"));
    expect(window.location.search).toContain("family=metal");
    fireEvent.click(screen.getByRole("button", { name: "Open datasheet" }));
    await waitFor(() => expect(window.location.pathname).toBe(`/materials/${visibleMaterial.material_id}`));
    expect(window.sessionStorage.getItem("cmp.materials.return-path")).toContain(`selected=${visibleMaterial.material_id}`);
    fireEvent.click(await screen.findByRole("button", { name: "Back to results" }));
    expect(await screen.findByRole("textbox", { name: "Search materials" })).toHaveProperty("value", "DP780");
    expect(window.location.search).toContain("q=DP780");
  });

  it("does not replace a URL-selected Material while the result list is still loading", async () => {
    const alphabeticFirst = {
      ...visibleMaterial,
      material_id: "10000000-0000-4000-8000-000000000099",
      current_revision: {
        ...visibleMaterial.current_revision,
        id: "20000000-0000-4000-8000-000000000099",
        content: { ...visibleMaterial.current_revision.content, name: "AAA reference material", material_code: "AAA-001" },
      },
    };
    window.history.pushState({}, "", `/materials?selected=${visibleMaterial.material_id}`);
    mockProductFetch((input, init) => {
      const url = String(input);
      const catalog = materialCatalogFetch(input, init, [alphabeticFirst, visibleMaterial]);
      if (catalog) return catalog;
      if (url.endsWith(`/materials/${visibleMaterial.material_id}`)) return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
      if (url.endsWith(`/materials/${alphabeticFirst.material_id}`)) return jsonResponse({ material: alphabeticFirst, states: [], property_sets: [] });
      if (url.includes("/catalog/domain-bindings:resolve")) return jsonResponse(null);
      if (url.includes("/bulk-export-candidates?")) return jsonResponse({ items: [] });
      return jsonResponse({});
    });

    render(<App />);

    expect((await screen.findAllByText("Demo DP780 Steel")).length).toBeGreaterThanOrEqual(1);
    await waitFor(() => expect(window.location.search).toContain(`selected=${visibleMaterial.material_id}`));
  });

  it("uses one server-scoped request per 10,000-record page without row enrichment", async () => {
    const pageItems = Array.from({ length: 50 }, (_, index) => ({
      ...visibleMaterial,
      material_id: `00000000-0000-4000-8000-${String(index + 100).padStart(12, "0")}`,
      current_revision: {
        ...visibleMaterial.current_revision,
        id: `00000000-0000-4000-8000-${String(index + 200).padStart(12, "0")}`,
        content: { ...visibleMaterial.current_revision.content, name: `Synthetic material ${index + 1}` },
      },
    }));
    const fetchMock = mockProductFetch((input, init) => {
      const url = String(input);
      const catalog = materialCatalogFetch(input, init, pageItems, 10_000);
      if (catalog) return catalog;
      return jsonResponse({});
    });

    render(<App />);

    expect(await screen.findByText("Synthetic material 1")).toBeTruthy();
    expect(screen.queryByText("Yield")).toBeNull();
    expect(screen.getByText(/10,000 matches/)).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/catalog/records:search")).length).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/catalog/records:search")).length).toBe(2));
    const materialRequests = fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/catalog/records:search"));
    expect(JSON.parse(String(materialRequests[1]?.[1]?.body))).toMatchObject({ offset: 50, domain_binding_kind: "material" });
    expect(fetchMock.mock.calls.some(([input]) => /\/materials\/[0-9]/.test(String(input)))).toBe(false);
  });

  it("does not pin an unsupported material family to the metal Modeling workflow", async () => {
    const composite = {
      ...visibleMaterial,
      current_revision: { ...visibleMaterial.current_revision, content: { ...visibleMaterial.current_revision.content, name: "Synthetic composite", material_class: "composite", material_family: "laminate" } },
    };
    mockProductFetch((input, init) => materialCatalogFetch(input, init, [composite]) ?? jsonResponse({}));

    render(<App />);

    expect(await screen.findByText("Synthetic composite")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Expand details pane" }));
    expect(screen.queryByRole("button", { name: "Start Modeling" })).toBeNull();
    expect(screen.queryByText("Modeling is not supported for this family.")).toBeNull();
    expect(screen.getByRole("button", { name: "Open datasheet" })).toBeTruthy();
  });

  it("shows an actionable problem code and trace ID without exposing the bearer token", async () => {
    mockProductFetch(() =>
      jsonResponse(
          {
            detail: "Reload the Material and select its current revision before retrying.",
            code: "CMP-REVISION-409",
            trace_id: "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
          },
          409,
        ),
    );

    render(<App />);

    const alerts = await screen.findAllByRole("alert");
    const alert = alerts.find((candidate) => candidate.textContent?.includes("CMP-REVISION-409"));
    expect(alert).toBeTruthy();
    const alertText = alert?.textContent ?? "";
    expect(alertText).toContain("Reload the Material");
    expect(alertText).toContain("CMP-REVISION-409");
    expect(alertText).toContain(
      "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
    );
    expect(document.body.textContent).not.toMatch(/bearer|API base|tenant|RLS/i);
  });

  it("starts the demo workspace automatically without technical connection controls", async () => {
    const fetchMock = mockProductFetch(() => jsonResponse({ items: [], total_count: 0 }));
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Materials", level: 1 })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/demo-identity/token",
      expect.objectContaining({ headers: expect.anything() }),
    );
    for (const label of ["Materials", "Modeling", "Activity"]) {
      expect(screen.getByRole("button", { name: label })).toBeTruthy();
    }
    expect(window.location.pathname).toBe("/materials");
    expect(screen.getByRole("button", { name: "Browse" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("textbox", { name: "Find in tree" })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/bearer|API base|tenant|RLS/i);
  });

  it("routes the legacy review deep link to the compact Activity queue without raw review inputs", async () => {
    window.history.pushState({}, "", "/jobs-reviews?candidate_id=candidate-1");
    const pendingReview = {
      review_request_id: "review-legacy-route-1",
      classification: "internal",
      aggregate_type: "modeling.material_model",
      aggregate_id: "material-1",
      revision_id: "material-r1",
      manifest_sha256: "a".repeat(64),
      required_role: "domain_reviewer",
      requested_by: "user-1",
      requested_at: "2026-07-27T00:00:00Z",
      reason: "Review the synthetic material data",
      lifecycle_state: "review",
      decision: null,
      links: {},
    };
    const fetchMock = mockProductFetch((input) => {
      const url = String(input);
      if (url.endsWith("/product-access/me")) return jsonResponse({ product_role: "reviewer", feature_grants: ["model_approval"], legacy_compatible: false });
      if (url.endsWith("/me")) return jsonResponse({ principal_id: "reviewer-1", principal_type: "user", display_name: "Reviewer", organization_id: "organization-1", project_id: "project-1", groups: [], scopes: [], request_id: "request-1", trace_id: "trace-1" });
      if (url.includes("/review-requests?")) return jsonResponse({ items: [pendingReview] });
      return jsonResponse({});
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Activity", level: 1 })).toBeTruthy();
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/review-requests?"))).toBe(true));
    expect(screen.getByRole("heading", { name: "Needs attention" })).toBeTruthy();
    expect(await screen.findByText("Selected model review")).toBeTruthy();
    expect(screen.getByText(/Review the synthetic material data/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Review" })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Aggregate type|Aggregate ID|Revision ID|Manifest SHA-256|Record decision/);
    expect(screen.queryByRole("heading", { name: "Evidence, Review & Release" })).toBeNull();
  });

  it("opens task-oriented Administration without infrastructure or policy vocabulary", async () => {
    window.history.pushState({}, "", "/administration");
    mockProductFetch(() => jsonResponse({}));

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Configure the material workspace" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Design the database/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Manage access/ })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/bearer|API base|tenant|RLS|principal ID|group issuer/i);
  });

  it("opens a connected Tests hub that routes work through a Material context", async () => {
    window.history.pushState({}, "", "/tests");
    mockProductFetch(() => jsonResponse({ items: [visibleMaterial], total_count: 1 }));

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Test data" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Open test workspace" })).toBeTruthy();
    expect(within(screen.getByRole("navigation", { name: "Primary navigation" })).getByRole("button", { name: "Materials" }).getAttribute("aria-current")).toBe(null);
  });

  it("restores the exact Modeling Material State for governed CSV and XLSX import", async () => {
    const materialStateId = "00000000-0000-4000-8000-000000000031";
    const materialStateRevisionId = "00000000-0000-4000-8000-000000000032";
    const materialState = {
      material_state_id: materialStateId,
      material_id: visibleMaterial.material_id,
      current_revision: {
        ...visibleMaterial.current_revision,
        id: materialStateRevisionId,
        aggregate_id: materialStateId,
        schema_id: "urn:cmp:catalog:material-state:1.0.0",
        content: {
          material_id: visibleMaterial.material_id,
          material_revision_id: visibleMaterial.current_revision.id,
          name: "Room-temperature state",
          manufacturing_route: null,
          heat_treatment: null,
          lot_or_batch: null,
          description: null,
        },
      },
      property_sets_url: `/api/v1/material-states/${materialStateId}/property-sets`,
    };
    window.history.pushState({}, "", "/datasets/import");
    window.sessionStorage.setItem("cmp.modeling.recent-session.v1", JSON.stringify({
      version: 1,
      updatedAt: "2026-07-21T00:00:00Z",
      materialFamily: "metal",
      objective: "Create a simulation-ready material card",
      material: {
        id: visibleMaterial.material_id,
        revisionId: visibleMaterial.current_revision.id,
        label: "Demo DP780 Steel",
        revisionNo: 1,
      },
      materialState: {
        id: materialStateId,
        revisionId: materialStateRevisionId,
        label: "Room-temperature state",
        revisionNo: 1,
      },
    }));
    mockProductFetch((input) => {
      const url = String(input);
      if (url.endsWith(`/materials/${visibleMaterial.material_id}`)) {
        return jsonResponse({ material: visibleMaterial, states: [materialState], property_sets: [] });
      }
      if (url.endsWith(`/material-states/${materialStateId}/test-runs`)) return jsonResponse({ items: [] });
      if (url.endsWith("/import-profiles")) return jsonResponse({ items: [] });
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    const routeHeading = await screen.findByRole("heading", { name: "Map tabular test data" });
    expect(routeHeading.nextElementSibling?.textContent).toContain("Demo DP780 Steel · DP780 · Room-temperature state · r1");
    expect(await screen.findByRole("heading", { name: "Governed CSV / TSV / XLSX import" })).toBeTruthy();
    expect(screen.getByLabelText("Format")).toBeTruthy();
    expect(screen.getByLabelText("Source file")).toBeTruthy();
    expect(screen.getByRole("button", { name: "← Modeling Data" })).toBeTruthy();
  });

  it("keeps a contextual Material model deep link addressable and selected", async () => {
    const materialId = visibleMaterial.material_id;
    window.history.pushState({}, "", `/materials/${materialId}/models`);
    mockProductFetch((input) => {
      const url = String(input);
      if (url.includes("/catalog/domain-bindings:resolve")) return jsonResponse({
        binding_id: "00000000-0000-0000-0000-000000000013",
        record_id: "00000000-0000-0000-0000-000000000020",
        record_revision_id: "00000000-0000-0000-0000-000000000021",
        kind: "material",
        object_id: materialId,
        revision_id: visibleMaterial.current_revision.id,
        workbench_path: `/materials/${materialId}`,
      });
      if (url.includes("/catalog/workflow-explorer/")) {
        const root = {
          record_id: "00000000-0000-0000-0000-000000000020",
          record_revision_id: "00000000-0000-0000-0000-000000000021",
          revision_no: 1,
          table_id: materialCatalogTableId,
          name: "Demo DP780 Steel",
          external_key: "DP780",
          domain_binding: {
            binding_id: "00000000-0000-0000-0000-000000000013",
            record_id: "00000000-0000-0000-0000-000000000020",
            record_revision_id: "00000000-0000-0000-0000-000000000021",
            kind: "material",
            object_id: materialId,
            revision_id: visibleMaterial.current_revision.id,
            workbench_path: `/materials/${materialId}`,
          },
        };
        return jsonResponse({ root, nodes: [root], links: [] });
      }
      return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Demo DP780 Steel" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "CAE Cards" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("button", { name: "Materials" }).getAttribute("aria-current")).toBe("page");
  });

  it("renders the Overview response plot and normalized response-point table", async () => {
    const materialId = visibleMaterial.material_id;
    const cardId = "00000000-0000-4000-8000-000000000099";
    const recordId = "00000000-0000-4000-8000-000000000010";
    const recordRevisionId = "00000000-0000-4000-8000-000000000011";
    const fetchMock = mockProductFetch((input) => {
      const url = String(input);
      if (url.endsWith(`/materials/${materialId}`)) return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
      if (url.includes("/catalog/domain-bindings:resolve")) return jsonResponse({
        binding_id: "00000000-0000-4000-8000-000000000013",
        record_id: recordId,
        record_revision_id: recordRevisionId,
        kind: "material",
        object_id: materialId,
        revision_id: visibleMaterial.current_revision.id,
        workbench_path: `/materials/${materialId}`,
      });
      if (url.includes("/catalog/workflow-explorer/")) {
        const root = { record_id: recordId, record_revision_id: recordRevisionId, revision_no: 1, table_id: materialCatalogTableId, name: "Demo DP780 Steel", external_key: "DP780", domain_binding: { binding_id: "00000000-0000-4000-8000-000000000013", record_id: recordId, record_revision_id: recordRevisionId, kind: "material", object_id: materialId, revision_id: visibleMaterial.current_revision.id, workbench_path: `/materials/${materialId}` } };
        return jsonResponse({ root, nodes: [root, {
          ...root,
          record_id: "00000000-0000-4000-8000-000000000020",
          record_revision_id: "00000000-0000-4000-8000-000000000021",
          name: "DP780 OpenRadioss native material card",
          domain_binding: { binding_id: "00000000-0000-4000-8000-000000000022", record_id: "00000000-0000-4000-8000-000000000020", record_revision_id: "00000000-0000-4000-8000-000000000021", kind: "neutral_solver_card", object_id: cardId, revision_id: "00000000-0000-4000-8000-000000000023", workbench_path: "/exports" },
        }], links: [] });
      }
      if (url.includes("/bulk-export-candidates?")) throw new Error("Neutral graph card must not use bulk candidate fallback");
      if (url.endsWith(exactNeutralCardPath(cardId, "/preview"))) return textResponse("/FUNCT/1\n0 450000000\n0.01 500000000\n0.02 550000000\n0.04 600000000\n0.08 620000000\n/END");
      rejectUnpinnedNeutralCardRequest(url, cardId);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<MaterialDetailPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} materialId={materialId} activeTab="overview" onNavigate={vi.fn()} />);

    const graph = await screen.findByRole("img", { name: "Representative material response showing true stress in MPa versus true plastic strain" });
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith(exactNeutralCardPath(cardId, "/preview")))).toBe(true);
    expect(graph.getAttribute("data-series-rows")).toBe("5");
    expect(graph.getAttribute("data-x-label")).toBe("True plastic strain [1]");
    expect(graph.getAttribute("data-y-label")).toBe("True stress (MPa)");
    const table = screen.getByRole("table", { name: "Representative response points" });
    expect(within(table).getByRole("columnheader", { name: "Point" })).toBeTruthy();
    expect(within(table).getByRole("columnheader", { name: "True plastic strain" })).toBeTruthy();
    expect(within(table).getByRole("columnheader", { name: "True stress (MPa)" })).toBeTruthy();
    expect(table.querySelectorAll("tbody tr")).toHaveLength(5);
    expect(table.querySelector("tbody tr")?.getAttribute("data-y-value")).toBe("450");
    const responseRegion = screen.getByRole("region", { name: "Scrollable representative response points" });
    expect(responseRegion.getAttribute("tabindex")).toBe("0");
    expect(screen.getByText("Exact ordered series · 5 points")).toBeTruthy();
  });

  it("opens a material-owned native solver card preview without routing through bulk export", async () => {
    const materialId = visibleMaterial.material_id;
    const cardId = "00000000-0000-4000-8000-000000000099";
    const recordId = "00000000-0000-4000-8000-000000000010";
    const recordRevisionId = "00000000-0000-4000-8000-000000000011";
    window.history.pushState({}, "", `/materials/${materialId}/cards/${cardId}`);
    mockProductFetch((input) => {
      const url = String(input);
      if (url.endsWith(`/materials/${materialId}`)) {
        return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
      }
      if (url.includes("/catalog/domain-bindings:resolve")) {
        return jsonResponse({
          binding_id: "00000000-0000-4000-8000-000000000013",
          record_id: recordId,
          record_revision_id: recordRevisionId,
          kind: "material",
          object_id: materialId,
          revision_id: visibleMaterial.current_revision.id,
          workbench_path: `/materials/${materialId}`,
        });
      }
      if (url.includes("/catalog/workflow-explorer/")) {
        const root = {
          record_id: recordId,
          record_revision_id: recordRevisionId,
          revision_no: 1,
          table_id: "00000000-0000-4000-8000-000000000012",
          name: "Demo DP780 Steel",
          external_key: "DP780",
          domain_binding: { binding_id: "00000000-0000-4000-8000-000000000013", record_id: recordId, record_revision_id: recordRevisionId, kind: "material", object_id: materialId, revision_id: visibleMaterial.current_revision.id, workbench_path: `/materials/${materialId}` },
        };
        return jsonResponse({ root, nodes: [root, {
          ...root,
          record_id: "00000000-0000-4000-8000-000000000020",
          record_revision_id: "00000000-0000-4000-8000-000000000021",
          name: "DP780 OpenRadioss native material card",
          domain_binding: {
            binding_id: "00000000-0000-4000-8000-000000000022",
            record_id: "00000000-0000-4000-8000-000000000020",
            record_revision_id: "00000000-0000-4000-8000-000000000021",
            kind: "neutral_solver_card",
            object_id: cardId,
            revision_id: "00000000-0000-4000-8000-000000000023",
            workbench_path: "/exports",
          },
        }], links: [] });
      }
      if (url.endsWith(exactNeutralCardPath(cardId, "/preview"))) {
        return textResponse("** CMP material-model-revision card-r1\n** CMP mapping-report-sha256 abc123\n/MAT/LAW36/1\nDP780\n/FUNCT/1\n0 450000000\n0.01 500000000\n0.05 620000000\n/END");
      }
      if (url.endsWith(exactNeutralCardPath(cardId, "/mapping-report"))) return jsonResponse(neutralSolverMappingReport());
      if (url.endsWith(exactNeutralCardPath(cardId))) return jsonResponse(neutralSolverCard(cardId));
      rejectUnpinnedNeutralCardRequest(url, cardId);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "DP780 OpenRadioss native material card" })).toBeTruthy();
    const nativePreview = screen.getByLabelText("Native solver card preview");
    expect(nativePreview.textContent).toContain("/MAT/LAW36/1");
    expect(nativePreview.textContent).not.toMatch(/material-model-revision|mapping-report-sha|abc123/i);
    const download = screen.getByRole("button", { name: "Download .rad" });
    expect(download.closest(".card-preview-actions")).not.toBeNull();
    expect(download.closest(".card-preview-header")).toBeNull();
    expect(nativePreview.className).toContain("native-card-preview");
    expect(nativePreview.tabIndex).toBe(0);
    expect(nativePreview.parentElement?.className).toContain("preview-scroll-shell");
    const scrollRail = nativePreview.parentElement?.querySelector<HTMLElement>(".preview-scroll-rail");
    const scrollThumb = scrollRail?.querySelector<HTMLElement>(".preview-scroll-thumb");
    expect(scrollRail).not.toBeNull();
    Object.defineProperties(nativePreview, {
      clientHeight: { configurable: true, value: 100 },
      scrollHeight: { configurable: true, value: 600 },
      scrollTop: { configurable: true, writable: true, value: 0 },
    });
    if (scrollRail) Object.defineProperty(scrollRail, "clientHeight", { configurable: true, value: 90 });
    fireEvent.scroll(nativePreview);
    expect(scrollRail?.dataset.scrollable).toBe("true");
    expect(scrollThumb?.style.height).toBe("22px");
    fireEvent.keyDown(nativePreview, { key: "PageDown" });
    expect(nativePreview.scrollTop).toBe(100);
    fireEvent.keyDown(nativePreview, { key: "End" });
    expect(nativePreview.scrollTop).toBe(600);
    const linkedResponse = screen.getByRole("img", { name: "Linked response chart showing true stress in MPa versus true plastic strain" });
    expect(linkedResponse).toBeTruthy();
    expect(linkedResponse.getAttribute("data-series-rows")).toBe("3");
    expect(linkedResponse.getAttribute("data-y-domain")?.startsWith("0,")).toBe(false);
    expect(screen.getByText("True plastic strain [1]")).toBeTruthy();
    expect(screen.getByText("True stress (MPa)")).toBeTruthy();
    expect(screen.getByText("Delivery checks pass for this target, so this download is ready.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Delivery check" })).toBeTruthy();
    expect(screen.getByText("Values unchanged")).toBeTruthy();
    expect(screen.getByText("Converted")).toBeTruthy();
    expect(screen.queryByText("exact")).toBeNull();
    expect(screen.queryByText("transformed")).toBeNull();
    expect(window.location.pathname).toBe(`/materials/${materialId}/cards/${cardId}`);
  });

  it("keeps review delivery disabled until the adjacent acknowledgement is checked", async () => {
    const materialId = visibleMaterial.material_id;
    const cardId = "00000000-0000-4000-8000-000000000099";
    const recordId = "00000000-0000-4000-8000-000000000010";
    const recordRevisionId = "00000000-0000-4000-8000-000000000011";
    window.history.pushState({}, "", `/materials/${materialId}/cards/${cardId}`);
    const createObjectUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:cmp-review-card");
    const revokeObjectUrl = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const fetchMock = mockProductFetch((input) => {
      const url = String(input);
      if (url.endsWith(`/materials/${materialId}`)) return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
      if (url.includes("/catalog/domain-bindings:resolve")) return jsonResponse({
        binding_id: "00000000-0000-4000-8000-000000000013",
        record_id: recordId,
        record_revision_id: recordRevisionId,
        kind: "material",
        object_id: materialId,
        revision_id: visibleMaterial.current_revision.id,
        workbench_path: `/materials/${materialId}`,
      });
      if (url.includes("/catalog/workflow-explorer/")) {
        const root = { record_id: recordId, record_revision_id: recordRevisionId, revision_no: 1, table_id: "00000000-0000-4000-8000-000000000012", name: "Demo DP780 Steel", external_key: "DP780", domain_binding: { binding_id: "00000000-0000-4000-8000-000000000013", record_id: recordId, record_revision_id: recordRevisionId, kind: "material", object_id: materialId, revision_id: visibleMaterial.current_revision.id, workbench_path: `/materials/${materialId}` } };
        return jsonResponse({ root, nodes: [root, {
          ...root,
          record_id: "00000000-0000-4000-8000-000000000020",
          record_revision_id: "00000000-0000-4000-8000-000000000021",
          name: "DP780 OpenRadioss native material card",
          domain_binding: {
            binding_id: "00000000-0000-4000-8000-000000000022",
            record_id: "00000000-0000-4000-8000-000000000020",
            record_revision_id: "00000000-0000-4000-8000-000000000021",
            kind: "neutral_solver_card",
            object_id: cardId,
            revision_id: "00000000-0000-4000-8000-000000000023",
            workbench_path: "/exports",
          },
        }], links: [] });
      }
      if (url.endsWith(exactNeutralCardPath(cardId, "/preview"))) return textResponse("/MAT/LAW36/1\nDP780");
      if (url.endsWith(exactNeutralCardPath(cardId, "/mapping-report"))) return jsonResponse(neutralSolverMappingReport(true));
      if (url.endsWith(exactNeutralCardPath(cardId))) return jsonResponse(neutralSolverCard(cardId));
      if (url.endsWith(exactNeutralCardPath(cardId, "/download"))) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-disposition": "attachment; filename=DP780.rad" }),
        blob: async () => new Blob(["/MAT/LAW36/1\nDP780"], { type: "text/plain" }),
      } as Response;
      rejectUnpinnedNeutralCardRequest(url, cardId);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    const download = await screen.findByRole("button", { name: "Download .rad" });
    expect((download as HTMLButtonElement).disabled).toBe(true);
    const acknowledgement = screen.getByRole("checkbox", { name: "I reviewed the delivery notes before downloading this card." });
    expect(acknowledgement.closest("li")).not.toBeNull();
    expect(acknowledgement.closest("li")?.textContent).toContain("Review required");
    expect(screen.queryByRole("img", { name: "Linked response chart showing true stress in MPa versus true plastic strain" })).toBeNull();
    fireEvent.click(acknowledgement);
    expect((download as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(download);

    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith(exactNeutralCardPath(cardId, "/download")))).toBe(true));
    expect(createObjectUrl).toHaveBeenCalled();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:cmp-review-card");
    expect(anchorClick).toHaveBeenCalled();
  });

  it("downloads the preferred native OpenRadioss card directly from Material Detail", async () => {
    const materialId = visibleMaterial.material_id;
    const cardId = "00000000-0000-4000-8000-000000000099";
    const recordId = "00000000-0000-4000-8000-000000000010";
    const recordRevisionId = "00000000-0000-4000-8000-000000000011";
    window.history.pushState({}, "", `/materials/${materialId}`);
    const createObjectUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:cmp-card");
    const revokeObjectUrl = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const fetchMock = mockProductFetch((input) => {
      const url = String(input);
      if (url.endsWith(`/materials/${materialId}`)) return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
      if (url.includes("/catalog/domain-bindings:resolve")) return jsonResponse({
        binding_id: "00000000-0000-4000-8000-000000000013",
        record_id: recordId,
        record_revision_id: recordRevisionId,
        kind: "material",
        object_id: materialId,
        revision_id: visibleMaterial.current_revision.id,
        workbench_path: `/materials/${materialId}`,
      });
      if (url.includes("/catalog/workflow-explorer/")) {
        const root = { record_id: recordId, record_revision_id: recordRevisionId, revision_no: 1, table_id: "00000000-0000-4000-8000-000000000012", name: "Demo DP780 Steel", external_key: "DP780", domain_binding: { binding_id: "00000000-0000-4000-8000-000000000013", record_id: recordId, record_revision_id: recordRevisionId, kind: "material", object_id: materialId, revision_id: visibleMaterial.current_revision.id, workbench_path: `/materials/${materialId}` } };
        return jsonResponse({ root, nodes: [root, { ...root, record_id: "00000000-0000-4000-8000-000000000020", record_revision_id: "00000000-0000-4000-8000-000000000021", name: "DP780 OpenRadioss native material card", domain_binding: { binding_id: "00000000-0000-4000-8000-000000000022", record_id: "00000000-0000-4000-8000-000000000020", record_revision_id: "00000000-0000-4000-8000-000000000021", kind: "neutral_solver_card", object_id: cardId, revision_id: "00000000-0000-4000-8000-000000000023", workbench_path: "/exports" } }], links: [] });
      }
      if (url.includes("/bulk-export-candidates?")) throw new Error("Neutral graph card must not use bulk candidate fallback");
      if (url.endsWith(exactNeutralCardPath(cardId, "/preview"))) return textResponse("/MAT/LAW36/1\nDP780");
      if (url.endsWith(exactNeutralCardPath(cardId, "/mapping-report"))) return jsonResponse(neutralSolverMappingReport());
      if (url.endsWith(exactNeutralCardPath(cardId))) return jsonResponse(neutralSolverCard(cardId));
      if (url.endsWith(exactNeutralCardPath(cardId, "/download"))) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-disposition": "attachment; filename=\"DP780.rad\"" }),
        blob: async () => new Blob(["/MAT/LAW36/1\nDP780"], { type: "text/plain" }),
      } as Response;
      rejectUnpinnedNeutralCardRequest(url, cardId);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Download .rad" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(exactNeutralCardPath(cardId, "/download")),
      expect.anything(),
    ));
    expect(createObjectUrl).toHaveBeenCalled();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:cmp-card");
    expect(anchorClick).toHaveBeenCalled();
  });

  it("opens a governed Material binding while preserving its exact revision query", async () => {
    const materialId = visibleMaterial.material_id;
    const materialRevisionId = visibleMaterial.current_revision.id;
    const recordId = "00000000-0000-4000-8000-000000000010";
    const recordRevisionId = "00000000-0000-4000-8000-000000000011";
    window.history.pushState(
      {},
      "",
      `/catalog/explorer/records/${recordId}/revisions/${recordRevisionId}`,
    );
    mockProductFetch(async (input) => {
        const url = String(input);
        if (url.endsWith("/catalog/explorer/tables") || url.endsWith("/catalog/link-types")) {
          return jsonResponse({ items: [] });
        }
        if (url.includes("/catalog/workflow-explorer/")) {
          const root = {
            record_id: recordId,
            record_revision_id: recordRevisionId,
            revision_no: 1,
            table_id: "00000000-0000-4000-8000-000000000012",
            name: "Demo DP780 Steel",
            external_key: "DP780",
            domain_binding: {
              binding_id: "00000000-0000-4000-8000-000000000013",
              record_id: recordId,
              record_revision_id: recordRevisionId,
              kind: "material",
              object_id: materialId,
              revision_id: materialRevisionId,
              workbench_path: `/materials/${materialId}?revision_id=${materialRevisionId}`,
            },
          };
          return jsonResponse({ root, nodes: [root], links: [] });
        }
        if (url.endsWith(`/materials/${materialId}/revisions`)) {
          return jsonResponse({ material_id: materialId, revisions: [visibleMaterial.current_revision] });
        }
        if (url.endsWith(`/materials/${materialId}`)) {
          return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
        }
        if (url.includes("/catalog/domain-bindings:resolve")) {
          return jsonResponse({
            binding_id: "00000000-0000-0000-0000-000000000013",
            record_id: recordId,
            record_revision_id: recordRevisionId,
            kind: "material",
            object_id: materialId,
            revision_id: materialRevisionId,
            workbench_path: `/materials/${materialId}`,
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      });

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Open governed object" }));

    expect(await screen.findByRole("heading", { name: "Demo DP780 Steel" })).toBeTruthy();
    expect(window.location.pathname).toBe(`/materials/${materialId}`);
    expect(new URLSearchParams(window.location.search).get("revision_id")).toBe(materialRevisionId);
  });
});

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./app";

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

function neutralSolverCard(cardId: string) {
  return {
    solver_card_id: cardId,
    neutral_material_id: "00000000-0000-4000-8000-000000000030",
    target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
    current_revision: {
      id: "00000000-0000-4000-8000-000000000023",
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

function neutralSolverMappingReport() {
  return {
    mapping_report_sha256: "d".repeat(64),
    exportable: true,
    report: {
      items: [
        { name: "density", ir_path: "density", target_representation: "RHO_I", status: "exact", detail: "Mapped without approximation." },
        { name: "elasticity", ir_path: "elasticity", target_representation: "E, NU", status: "transformed", detail: "Converted to the target unit system." },
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
    mockProductFetch((input) => {
      const url = String(input);
      if (url.includes("/materials?")) return jsonResponse({ items: [visibleMaterial], total_count: 10_000, offset: 0, limit: 50, facets: { material_classes: [{ material_class: "metal", count: 10_000 }] } });
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
    expect(screen.getByRole("search")).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "Material filters" })).toBeTruthy();
    expect(screen.getByRole("table", { name: "Material results" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Material class" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: /Material class/ })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: /Revision status/ })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: /Form \/ condition|Release/ })).toBeNull();
    expect(screen.getByText("Provider")).toBeTruthy();
    expect(screen.getByText("Evidence source")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Browse Tree" })).toHaveLength(1);
    expect(screen.queryByRole("navigation", { name: "Materials navigator" })).toBe(null);
    const materialHeader = screen.getAllByRole("columnheader").find((header) =>
      within(header).queryByRole("button", { name: "Material" }),
    );
    expect(materialHeader).toBeTruthy();
    expect(materialHeader?.getAttribute("aria-sort")).toBe("ascending");
    expect(within(materialHeader!).getByRole("button", { name: "Material" }).hasAttribute("aria-sort")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Material class" }));
    await waitFor(() => expect(window.location.search).toContain("sort=material_class"));
    expect(screen.getByRole("columnheader", { name: /Material class/ }).getAttribute("aria-sort")).toBe("ascending");
    fireEvent.click(screen.getByRole("button", { name: "Collapse filters pane" }));
    expect(screen.queryByRole("complementary", { name: "Material filters" })).toBe(null);
    expect(screen.getByRole("button", { name: "Expand filters pane" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Expand details pane" }));
    expect(screen.getByRole("button", { name: "Open material" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Materials" }).getAttribute("aria-busy")).toBe("false");
    fireEvent.change(screen.getByRole("textbox", { name: "Search materials" }), { target: { value: "DP780" } });
    fireEvent.submit(screen.getByRole("search"));
    fireEvent.click(screen.getByRole("button", { name: "Expand filters pane" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Material class" }), { target: { value: "metal" } });
    await waitFor(() => expect(window.location.search).toContain("q=DP780"));
    expect(window.location.search).toContain("family=metal");
    fireEvent.click(screen.getByRole("button", { name: "Open material" }));
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
    mockProductFetch((input) => {
      const url = String(input);
      if (url.includes("/materials?")) return jsonResponse({ items: [alphabeticFirst, visibleMaterial], total_count: 2, offset: 0, limit: 50, facets: { material_classes: [] } });
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
    const fetchMock = mockProductFetch((input) => {
      const url = String(input);
      if (url.includes("/materials?")) return jsonResponse({ items: pageItems, total_count: 10_000, offset: url.includes("offset=50") ? 50 : 0, limit: 50, facets: { material_classes: [{ material_class: "metal", count: 10_000 }] } });
      return jsonResponse({});
    });

    render(<App />);

    expect(await screen.findByText("Synthetic material 1")).toBeTruthy();
    expect(screen.queryByText("Yield")).toBeNull();
    expect(screen.getByText(/10,000 matches/)).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/materials?")).length).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/materials?")).length).toBe(2));
    const materialRequests = fetchMock.mock.calls.filter(([input]) => String(input).includes("/materials?"));
    expect(String(materialRequests[1]?.[0])).toContain("offset=50");
    expect(fetchMock.mock.calls.some(([input]) => /\/materials\/[0-9]/.test(String(input)))).toBe(false);
  });

  it("does not pin an unsupported material family to the metal Modeling workflow", async () => {
    const composite = {
      ...visibleMaterial,
      current_revision: { ...visibleMaterial.current_revision, content: { ...visibleMaterial.current_revision.content, name: "Synthetic composite", material_class: "composite", material_family: "laminate" } },
    };
    mockProductFetch((input) => String(input).includes("/materials?")
      ? jsonResponse({ items: [composite], total_count: 1, offset: 0, limit: 50, facets: { material_classes: [{ material_class: "composite", count: 1 }] } })
      : jsonResponse({}));

    render(<App />);

    expect(await screen.findByText("Synthetic composite")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Expand details pane" }));
    expect(screen.queryByRole("button", { name: "Start Modeling" })).toBeNull();
    expect(screen.getByText("Modeling is not supported for this family.")).toBeTruthy();
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

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Reload the Material");
    expect(alert.textContent).toContain("CMP-REVISION-409");
    expect(alert.textContent).toContain(
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
    expect(screen.getAllByRole("button", { name: "Browse Tree" })).toHaveLength(1);
    expect(document.body.textContent).not.toMatch(/bearer|API base|tenant|RLS/i);
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
      if (url.includes("/catalog/domain-bindings:resolve")) return jsonResponse(null);
      return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Demo DP780 Steel" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "CAE Cards" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("button", { name: "Materials" }).getAttribute("aria-current")).toBe("page");
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
          domain_binding: null,
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
      if (url.endsWith(`/neutral-solver-cards/${cardId}/preview`)) {
        return textResponse("/MAT/LAW36/1\nDP780");
      }
      if (url.endsWith(`/neutral-solver-cards/${cardId}/mapping-report`)) return jsonResponse(neutralSolverMappingReport());
      if (url.endsWith(`/neutral-solver-cards/${cardId}`)) return jsonResponse(neutralSolverCard(cardId));
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "DP780 OpenRadioss native material card" })).toBeTruthy();
    expect(screen.getByLabelText("Native solver card preview").textContent).toContain("/MAT/LAW36/1");
    expect(screen.getByRole("button", { name: "Download .rad" })).toBeTruthy();
    expect(window.location.pathname).toBe(`/materials/${materialId}/cards/${cardId}`);
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
        const root = { record_id: recordId, record_revision_id: recordRevisionId, revision_no: 1, table_id: "00000000-0000-4000-8000-000000000012", name: "Demo DP780 Steel", external_key: "DP780", domain_binding: null };
        return jsonResponse({ root, nodes: [root, { ...root, record_id: "00000000-0000-4000-8000-000000000020", record_revision_id: "00000000-0000-4000-8000-000000000021", name: "DP780 OpenRadioss native material card", domain_binding: { binding_id: "00000000-0000-4000-8000-000000000022", record_id: "00000000-0000-4000-8000-000000000020", record_revision_id: "00000000-0000-4000-8000-000000000021", kind: "neutral_solver_card", object_id: cardId, revision_id: "00000000-0000-4000-8000-000000000023", workbench_path: "/exports" } }], links: [] });
      }
      if (url.includes("/bulk-export-candidates?")) return jsonResponse({ items: [] });
      if (url.endsWith(`/neutral-solver-cards/${cardId}/preview`)) return textResponse("/MAT/LAW36/1\nDP780");
      if (url.endsWith(`/neutral-solver-cards/${cardId}/mapping-report`)) return jsonResponse(neutralSolverMappingReport());
      if (url.endsWith(`/neutral-solver-cards/${cardId}`)) return jsonResponse(neutralSolverCard(cardId));
      if (url.endsWith(`/neutral-solver-cards/${cardId}/download`)) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-disposition": "attachment; filename=\"DP780.rad\"" }),
        blob: async () => new Blob(["/MAT/LAW36/1\nDP780"], { type: "text/plain" }),
      } as Response;
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Download .rad" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/neutral-solver-cards/${cardId}/download`),
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
          return jsonResponse(null);
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

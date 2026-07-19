import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
    mockProductFetch(() => jsonResponse({ items: [visibleMaterial], total_count: 10_000 }));

    render(<App />);

    expect(await screen.findByText("Demo DP780 Steel")).toBeTruthy();
    expect(screen.getByText("DP780")).toBeTruthy();
    expect(screen.getAllByText(/10,000 records/)).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Material data to solver-ready models" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Find and inspect material data" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Process test curves and create cards" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Start with an engineering example" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open metal journey" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open polymer journey" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open elastomer journey" })).toBeTruthy();
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

    expect(await screen.findByRole("heading", { name: "Material data to solver-ready models" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/demo-identity/token",
      expect.objectContaining({ headers: expect.anything() }),
    );
    for (const label of ["Dashboard", "Material Database", "Material Modeling", "Jobs & Reviews", "Administration"]) {
      expect(screen.getByRole("button", { name: label })).toBeTruthy();
    }
    expect(screen.getByRole("button", { name: "Open Contents Tree and Datasheets ›" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Continue modeling" })).toBeTruthy();
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
    expect(screen.getByRole("button", { name: "Material Database" }).getAttribute("aria-current")).toBe(null);
  });

  it("keeps a contextual Material model deep link addressable and selected", async () => {
    const materialId = visibleMaterial.material_id;
    window.history.pushState({}, "", `/materials/${materialId}/models`);
    mockProductFetch(async (input) => {
      const url = String(input);
      if (url.endsWith("/revisions")) {
        return jsonResponse({ material_id: materialId, revisions: [visibleMaterial.current_revision] });
      }
      return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Demo DP780 Steel" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Models & Cards" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "Material Database" }).getAttribute("aria-current")).toBe("page");
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
        throw new Error(`Unexpected request: ${url}`);
      });

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Open governed object" }));

    expect(await screen.findByRole("heading", { name: "Demo DP780 Steel" })).toBeTruthy();
    expect(window.location.pathname).toBe(`/materials/${materialId}`);
    expect(new URLSearchParams(window.location.search).get("revision_id")).toBe(materialRevisionId);
  });
});

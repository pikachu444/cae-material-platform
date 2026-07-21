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
    mockProductFetch((input) => {
      const url = String(input);
      if (url.includes("/materials?")) return jsonResponse({ items: [visibleMaterial], total_count: 10_000 });
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
    expect(screen.getByText(/10,000 total/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Find material data ready for CAE" })).toBeTruthy();
    expect(screen.getByRole("search")).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "Material filters" })).toBeTruthy();
    expect(screen.getByRole("table", { name: "Material results" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Manufacturer / source" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Validation / release status" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Browse Tree" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Hide filters" }));
    expect(screen.queryByRole("complementary", { name: "Material filters" })).toBe(null);
    expect(screen.getByRole("button", { name: "Show filters" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Show details" }));
    expect(screen.getByRole("button", { name: "Open material" })).toBeTruthy();
    expect(await screen.findByText("1 cards")).toBeTruthy();
    expect(screen.getAllByText("OpenRadioss").length).toBeGreaterThanOrEqual(1);
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

    expect(await screen.findByRole("heading", { name: "Find material data ready for CAE" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/demo-identity/token",
      expect.objectContaining({ headers: expect.anything() }),
    );
    for (const label of ["Materials", "Modeling", "Activity"]) {
      expect(screen.getByRole("button", { name: label })).toBeTruthy();
    }
    expect(window.location.pathname).toBe("/materials");
    expect(screen.getByRole("button", { name: "Browse Tree" })).toBeTruthy();
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
    expect(screen.getByRole("button", { name: "Materials" }).getAttribute("aria-current")).toBe(null);
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
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "DP780 OpenRadioss native material card" })).toBeTruthy();
    expect(screen.getByLabelText("Native solver card preview").textContent).toContain("/MAT/LAW36/1");
    expect(screen.getByRole("button", { name: "Download .rad" })).toBeTruthy();
    expect(window.location.pathname).toBe(`/materials/${materialId}/cards/${cardId}`);
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

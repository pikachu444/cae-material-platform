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

describe("Material Catalog workbench", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("requires an explicit protected API connection before catalog data is requested", () => {
    render(<App />);

    expect(screen.getByText("Connect this workbench to the protected Material Catalog.")).toBeTruthy();
    for (const label of ["Dashboard", "Materials", "Tests", "Datasets", "Models", "Exports", "Governance"]) {
      expect(screen.getByRole("button", { name: label })).toBeTruthy();
    }
  });

  it("renders Material data returned by the real Catalog API contract", async () => {
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: "catalog-token" }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse({ items: [visibleMaterial], total_count: 10_000 }),
      ),
    );

    render(<App />);

    expect(await screen.findByText("Demo DP780 Steel")).toBeTruthy();
    expect(screen.getByText("DP780")).toBeTruthy();
    expect(screen.getByText("10,000")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Choose a material family and follow the evidence." })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open metal journey" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open polymer journey" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open elastomer journey" })).toBeTruthy();
  });

  it("shows an actionable problem code and trace ID without exposing the bearer token", async () => {
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: "catalog-token-must-not-render" }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse(
          {
            detail: "Reload the Material and select its current revision before retrying.",
            code: "CMP-REVISION-409",
            trace_id: "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
          },
          409,
        ),
      ),
    );

    render(<App />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Reload the Material");
    expect(alert.textContent).toContain("CMP-REVISION-409");
    expect(alert.textContent).toContain(
      "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
    );
    expect(alert.textContent).not.toContain("catalog-token-must-not-render");
  });

  it("can request an explicitly enabled local demo token without treating it as a normal fallback", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        access_token: "demo-token",
        token_type: "Bearer",
        expires_in_seconds: 900,
        organization_id: "d0000000-0000-4000-8000-000000000001",
        project_id: "d0000000-0000-4000-8000-000000000002",
        group: "cmp-demo-material-team",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByText("Connection"));
    fireEvent.click(screen.getByRole("button", { name: "Use local demo identity" }));

    expect(await screen.findByDisplayValue("demo-token")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/demo-identity/token",
      expect.objectContaining({ headers: expect.anything() }),
    );
  });

  it("opens a connected Tests hub that routes work through a Material context", async () => {
    window.history.pushState({}, "", "/tests");
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: "catalog-token" }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse({ items: [visibleMaterial], total_count: 1 }),
      ),
    );

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Test data" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open test workspace" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Tests" }).getAttribute("aria-current")).toBe("page");
  });

  it("keeps a contextual Material model deep link addressable and selected", async () => {
    const materialId = visibleMaterial.material_id;
    window.history.pushState({}, "", `/materials/${materialId}/models`);
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: "catalog-token" }),
    );
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/revisions")) {
        return jsonResponse({ material_id: materialId, revisions: [visibleMaterial.current_revision] });
      }
      return jsonResponse({ material: visibleMaterial, states: [], property_sets: [] });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Demo DP780 Steel" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Models & Cards" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "Models" }).getAttribute("aria-current")).toBe("page");
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
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: "catalog-token" }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockImplementation(async (input) => {
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
      }),
    );

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Open governed object" }));

    expect(await screen.findByRole("heading", { name: "Demo DP780 Steel" })).toBeTruthy();
    expect(window.location.pathname).toBe(`/materials/${materialId}`);
    expect(new URLSearchParams(window.location.search).get("revision_id")).toBe(materialRevisionId);
  });
});

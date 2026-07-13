import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./app";

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
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
  });

  it("renders Material data returned by the real Catalog API contract", async () => {
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: "catalog-token" }),
    );
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ items: [visibleMaterial] })));

    render(<App />);

    expect(await screen.findByText("Demo DP780 Steel")).toBeTruthy();
    expect(screen.getByText("DP780")).toBeTruthy();
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
});

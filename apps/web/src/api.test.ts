import { describe, expect, it, vi } from "vitest";
import {
  ApiError,
  preflightSolverCardMapping,
  previewSolverCard,
  listMaterials,
} from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json", etag: "\"revision\"" }),
    json: async () => body,
  } as Response;
}

describe("Catalog API client", () => {
  it("sends the tenant-scoped bearer token to the configured Material endpoint", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await listMaterials(
      { baseUrl: "http://localhost:8000/api/v1", accessToken: "short-lived-token" },
      "DP780 steel",
    );

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/materials?limit=50&q=DP780+steel");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer short-lived-token");
    expect(new Headers(init?.headers).get("accept")).toBe("application/json");
  });

  it("does not make a catalog request without an explicit bearer token", async () => {
    try {
      await listMaterials({ baseUrl: "/api/v1", accessToken: "" }, "");
      throw new Error("Expected a missing-token request to fail");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(401);
    }
  });

  it("acknowledges an explicit solver target before any Solver Card is created", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        material_model_id: "00000000-0000-0000-0000-000000000001",
        material_model_revision_id: "00000000-0000-0000-0000-000000000002",
        model_schema_digest: "a".repeat(64),
        target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
        items: [],
        exporter_id: "cmp.reference.openradioss-elast",
        exporter_version: "1.0.0",
        exporter_digest: "b".repeat(64),
        mapping_report_sha256: "c".repeat(64),
        exportable: true,
        non_production: true,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await preflightSolverCardMapping(
      { baseUrl: "http://localhost:8000/api/v1", accessToken: "short-lived-token" },
      "00000000-0000-0000-0000-000000000001",
      { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(
      "http://localhost:8000/api/v1/material-models/00000000-0000-0000-0000-000000000001/mapping-preflight",
    );
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
    });
  });

  it("requests the immutable card preview as authenticated plain text", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "text/plain" }),
      text: async () => "/MAT/ELAST/17/1\n",
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const result = await previewSolverCard(
      { baseUrl: "/api/v1", accessToken: "short-lived-token" },
      "00000000-0000-0000-0000-000000000001",
    );

    expect(result.data).toBe("/MAT/ELAST/17/1\n");
    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init?.headers).get("accept")).toBe("text/plain");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer short-lived-token");
  });
});

import { describe, expect, it, vi } from "vitest";
import { ApiError, listMaterials } from "./api";

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
});
